from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db import get_db
from src.deps import get_current_user
from src.models import User, UserRole, UserSession
from src.schemas import LoginRequest, RegisterRequest, UserOut
from src.services.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    session_expiry,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_ttl_days * 24 * 3600,
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)) -> User:
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        role=UserRole.learner,
    )
    db.add(user)
    await db.flush()

    token = generate_session_token()
    db.add(UserSession(user_id=user.id, token_hash=hash_session_token(token), expires_at=session_expiry()))
    await db.commit()
    await db.refresh(user)

    _set_session_cookie(response, token)
    return user


@router.post("/login", response_model=UserOut)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)) -> User:
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    token = generate_session_token()
    db.add(UserSession(user_id=user.id, token_hash=hash_session_token(token), expires_at=session_expiry()))
    await db.commit()

    _set_session_cookie(response, token)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    session_token: str | None = Cookie(default=None, alias=settings.cookie_name),
) -> None:
    if session_token is not None:
        await db.execute(
            delete(UserSession).where(UserSession.token_hash == hash_session_token(session_token))
        )
        await db.commit()
    response.delete_cookie(settings.cookie_name, path="/")


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user
