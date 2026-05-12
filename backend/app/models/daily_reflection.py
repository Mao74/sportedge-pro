"""Daily reflections — user-written notes surfaced in the Obsidian daily note."""

from __future__ import annotations

import uuid
from datetime import date as date_t, datetime

from sqlalchemy import Date, DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DailyReflection(Base):
    __tablename__ = "daily_reflections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    date: Mapped[date_t] = mapped_column(Date, nullable=False, unique=True)
    reflection_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
