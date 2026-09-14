"""Password hashing and opaque session-token helpers."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from pwdlib import PasswordHash

from src.config import get_settings

_password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hasher.verify(password, password_hash)


def generate_session_token() -> str:
    """A random, high-entropy token. Only its hash is ever stored."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """Session tokens are hashed with plain SHA-256 (not argon2): they're already
    high-entropy random values, not human-chosen passwords, so we don't need a
    slow, salted KDF -- we need a fast, deterministic lookup key for the DB.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_expiry() -> datetime:
    settings = get_settings()
    return datetime.now(UTC) + timedelta(days=settings.session_ttl_days)
