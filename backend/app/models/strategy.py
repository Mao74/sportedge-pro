"""Strategy model — covers both built-in templates and user-defined customs."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Boolean, CheckConstraint, Enum, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class StrategyKind(str, enum.Enum):
    builtin = "builtin"
    custom = "custom"


class Strategy(Base, TimestampMixin):
    __tablename__ = "strategies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    kind: Mapped[StrategyKind] = mapped_column(
        Enum(StrategyKind, name="strategy_kind", create_constraint=True),
        nullable=False,
    )
    template_key: Mapped[str | None] = mapped_column(String, nullable=True)
    sport: Mapped[str] = mapped_column(String, nullable=False, server_default="football")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    color_hex: Mapped[str | None] = mapped_column(String(9), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    field_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    trades: Mapped[list["Trade"]] = relationship(  # noqa: F821 — forward ref
        back_populates="strategy",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_strategies_kind_is_active", "kind", "is_active"),
        # Built-ins must always have a template_key; customs must not.
        CheckConstraint(
            "(kind = 'builtin' AND template_key IS NOT NULL) "
            "OR (kind = 'custom' AND template_key IS NULL)",
            name="strategies_template_key_kind",
        ),
    )

    def __repr__(self) -> str:
        return f"<Strategy {self.kind.value}:{self.slug}>"
