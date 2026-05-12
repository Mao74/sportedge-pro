"""Password hashing + JWT helpers.

- Bcrypt direct (passlib unmaintained / broken with bcrypt 5.x).
- python-jose for JWT (HS256). All token claims include ``sub`` (user UUID
  string), ``iat``, ``exp``, and a ``type`` discriminator
  (``access`` / ``refresh``) so refresh tokens can't be used as access tokens.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

# --- Password hashing ------------------------------------------------------

_BCRYPT_MAX_BYTES = 72


def _to_bytes(plain: str) -> bytes:
    return plain.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_to_bytes(plain), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_to_bytes(plain), hashed.encode("utf-8"))
    except ValueError:
        return False


# --- JWT --------------------------------------------------------------------

TokenType = Literal["access", "refresh"]


class InvalidTokenError(Exception):
    """Raised when a JWT fails decode/validation."""


def _create_token(subject: str, token_type: TokenType, ttl: timedelta) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str | uuid.UUID) -> str:
    settings = get_settings()
    return _create_token(
        str(subject),
        "access",
        timedelta(minutes=settings.jwt_access_token_ttl_minutes),
    )


def create_refresh_token(subject: str | uuid.UUID) -> str:
    settings = get_settings()
    return _create_token(
        str(subject),
        "refresh",
        timedelta(days=settings.jwt_refresh_token_ttl_days),
    )


def decode_token(token: str, *, expected_type: TokenType) -> dict[str, Any]:
    settings = get_settings()
    try:
        claims = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as e:
        raise InvalidTokenError(f"Invalid or expired token: {e}") from e
    if claims.get("type") != expected_type:
        raise InvalidTokenError(
            f"Wrong token type: expected {expected_type}, got {claims.get('type')!r}"
        )
    if "sub" not in claims:
        raise InvalidTokenError("Token missing 'sub' claim.")
    return claims
