"""FastAPI dependencies: DB session, current user, role guards."""

from datetime import UTC, datetime

from fastapi import Cookie, Depends, HTTPException, status
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db import get_db
from src.models import User, UserRole, UserSession
from src.services.security import hash_session_token

settings = get_settings()


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias=settings.cookie_name),
) -> User:
    if session_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    token_hash = hash_session_token(session_token)
    result = await db.execute(select(UserSession).where(UserSession.token_hash == token_hash))
    session = result.scalar_one_or_none()

    if session is None or session.expires_at < datetime.now(UTC):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired or invalid")

    user = await db.get(User, session.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user


def get_tutor_graph() -> CompiledStateGraph:
    from src.services.tutor_graph.graph import get_compiled_tutor_graph

    return get_compiled_tutor_graph()
