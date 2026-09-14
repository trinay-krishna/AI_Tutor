"""Wraps the tutor graph with DB work: load history, invoke, persist the turn.

Kept out of the graph itself so graph nodes stay pure (state in, state out) and
easy to test without a database.
"""

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Conversation, Message, MessageRole, Technology

HISTORY_TURNS = 8


class ChatError(Exception):
    """Raised for chat-pipeline problems that should surface as a friendly 503."""


async def _load_history(db: AsyncSession, conversation_id) -> list:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(HISTORY_TURNS * 2)
    )
    rows = list(reversed(result.scalars().all()))
    history = []
    for m in rows:
        if m.role == MessageRole.user:
            history.append(HumanMessage(content=m.content))
        else:
            history.append(AIMessage(content=m.content))
    return history


async def send_message(
    db: AsyncSession,
    graph: CompiledStateGraph,
    conversation: Conversation,
    technology: Technology,
    content: str,
) -> tuple[Message, Message]:
    history = await _load_history(db, conversation.id)

    user_message = Message(
        conversation_id=conversation.id, role=MessageRole.user, content=content
    )
    db.add(user_message)
    # Committed (not just flushed) before invoking the graph: the user's message
    # must survive even if generation fails below, so they don't lose their input
    # and a retry doesn't re-send it as a duplicate.
    await db.commit()
    await db.refresh(user_message)

    try:
        result = await graph.ainvoke(
            {
                "technology_id": technology.id,
                "technology_name": technology.name,
                "technology_description": technology.description,
                "history": history,
                "user_message": content,
            }
        )
    except Exception as e:  # noqa: BLE001
        raise ChatError("The tutor is temporarily unavailable. Please try again.") from e

    assistant_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.assistant,
        content=result.get("answer", ""),
        scope=result.get("scope"),
        intent=result.get("intent"),
        mode=result.get("mode"),
        sources=result.get("sources") or None,
        message_metadata={"study_plan": result["study_plan"]} if result.get("study_plan") else None,
    )
    db.add(assistant_message)
    await db.commit()
    await db.refresh(assistant_message)

    return user_message, assistant_message
