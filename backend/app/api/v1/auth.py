"""Auth API: login, refresh, me."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.problem_details import unauthorized
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models import User
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPair, UserMe

router = APIRouter(prefix="/auth", tags=["auth"])


def _make_token_pair(user_id: uuid.UUID) -> TokenPair:
    settings = get_settings()
    return TokenPair(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
        expires_in=settings.jwt_access_token_ttl_minutes * 60,
    )


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, db: DbSession) -> TokenPair:
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        # Same message for missing user vs wrong password — no email enumeration.
        raise unauthorized("Invalid email or password.")
    return _make_token_pair(user.id)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: DbSession) -> TokenPair:
    try:
        claims = decode_token(payload.refresh_token, expected_type="refresh")
    except InvalidTokenError as e:
        raise unauthorized(str(e)) from e
    try:
        user_id = uuid.UUID(claims["sub"])
    except (KeyError, ValueError) as e:
        raise unauthorized("Refresh token has an invalid 'sub' claim.") from e

    result = await db.execute(select(User).where(User.id == user_id))
    if result.scalar_one_or_none() is None:
        raise unauthorized("User no longer exists.")
    return _make_token_pair(user_id)


@router.get("/me", response_model=UserMe)
async def me(user: CurrentUser) -> UserMe:
    return UserMe.model_validate(user)
