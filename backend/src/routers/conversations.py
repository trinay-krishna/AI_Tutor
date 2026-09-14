import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db import get_db
from src.deps import get_current_user, get_tutor_graph
from src.models import Conversation, Message, User
from src.schemas import (
    ConversationCreate,
    ConversationDetailOut,
    ConversationOut,
    MessageCreate,
    MessageOut,
    SourceOut,
)
from src.services.chat import ChatError, send_message
from src.services.lookups import get_technology_or_404

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _message_to_out(m: Message) -> MessageOut:
    return MessageOut(
        id=str(m.id),
        role=m.role,
        content=m.content,
        scope=m.scope,
        intent=m.intent,
        mode=m.mode,
        sources=[SourceOut(**s) for s in m.sources] if m.sources else None,
        created_at=m.created_at,
    )


def _conversation_to_out(c: Conversation) -> ConversationOut:
    return ConversationOut(
        id=str(c.id),
        technology_id=c.technology_id,
        title=c.title,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


def _parse_conversation_id(conversation_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(conversation_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found") from e


async def _get_owned_conversation_or_404(
    db: AsyncSession, conversation_id: str, user_id: int, *, with_messages: bool = False
) -> Conversation:
    cid = _parse_conversation_id(conversation_id)
    query = select(Conversation).where(Conversation.id == cid)
    if with_messages:
        query = query.options(selectinload(Conversation.messages))
    result = await db.execute(query)
    conversation = result.scalar_one_or_none()
    if conversation is None or conversation.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conversation


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    technology_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ConversationOut]:
    query = select(Conversation).where(Conversation.user_id == user.id)
    if technology_id is not None:
        query = query.where(Conversation.technology_id == technology_id)
    result = await db.execute(query.order_by(Conversation.updated_at.desc()))
    return [_conversation_to_out(c) for c in result.scalars().all()]


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ConversationOut:
    await get_technology_or_404(db, body.technology_id)
    conversation = Conversation(user_id=user.id, technology_id=body.technology_id)
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return _conversation_to_out(conversation)


@router.get("/{conversation_id}", response_model=ConversationDetailOut)
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ConversationDetailOut:
    conversation = await _get_owned_conversation_or_404(db, conversation_id, user.id, with_messages=True)
    base = _conversation_to_out(conversation)
    return ConversationDetailOut(
        **base.model_dump(), messages=[_message_to_out(m) for m in conversation.messages]
    )


@router.post("/{conversation_id}/messages", response_model=dict)
async def post_message(
    conversation_id: str,
    body: MessageCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    graph: CompiledStateGraph = Depends(get_tutor_graph),
) -> dict:
    conversation = await _get_owned_conversation_or_404(db, conversation_id, user.id)
    technology = await get_technology_or_404(db, conversation.technology_id)

    try:
        user_msg, assistant_msg = await send_message(db, graph, conversation, technology, body.content)
    except ChatError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from e

    return {
        "user_message": _message_to_out(user_msg),
        "assistant_message": _message_to_out(assistant_msg),
    }


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    conversation = await _get_owned_conversation_or_404(db, conversation_id, user.id)
    await db.delete(conversation)
    await db.commit()
