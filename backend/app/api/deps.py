"""FastAPI dependencies. Re-exports session and adds auth resolution."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.problem_details import unauthorized
from app.core.security import InvalidTokenError, decode_token
from app.models import User

# Token URL is documentation-facing only — the real login route lives at
# settings.api_v1_prefix + "/auth/login".
_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{get_settings().api_v1_prefix}/auth/login",
    auto_error=False,
)

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    db: DbSession,
    token: Annotated[str | None, Depends(_oauth2_scheme)],
) -> User:
    if not token:
        raise unauthorized("Missing bearer token.")
    try:
        claims = decode_token(token, expected_type="access")
    except InvalidTokenError as e:
        raise unauthorized(str(e)) from e

    try:
        user_id = uuid.UUID(claims["sub"])
    except (KeyError, ValueError) as e:
        raise unauthorized("Token has an invalid 'sub' claim.") from e

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise unauthorized("User does not exist.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


__all__ = ["DbSession", "CurrentUser", "get_current_user", "get_db"]
