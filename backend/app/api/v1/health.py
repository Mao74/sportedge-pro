"""Health endpoint — verifies API liveness and DB connectivity."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    api: str
    database: str
    version: str


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness + DB connectivity probe",
)
async def health(db: Annotated[AsyncSession, Depends(get_db)]) -> HealthResponse:
    db_state = "ok"
    try:
        result = await db.execute(text("SELECT 1"))
        if result.scalar_one() != 1:
            db_state = "degraded"
    except Exception:  # noqa: BLE001 — surface any DB failure as a degraded probe
        db_state = "unreachable"

    from app import __version__

    return HealthResponse(
        status="ok" if db_state == "ok" else "degraded",
        api="ok",
        database=db_state,
        version=__version__,
    )
