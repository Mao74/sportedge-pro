"""Single-row app settings table. Holds Obsidian configuration today; future
runtime-toggleable settings can land here without migrations."""

from __future__ import annotations

import uuid
from datetime import datetime

from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.trade import MarketType


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    # --- Obsidian -----------------------------------------------------------
    obsidian_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    obsidian_vault_path: Mapped[str] = mapped_column(
        String, nullable=False, server_default="/vault"
    )
    obsidian_sync_mode: Mapped[str] = mapped_column(
        String, nullable=False, server_default="export_only"
    )  # export_only | two_way | manual_only
    obsidian_template_set: Mapped[str] = mapped_column(
        String, nullable=False, server_default="complete"
    )  # complete | minimal | tactical
    obsidian_last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    obsidian_last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Trading preferences ----------------------------------------------
    default_commission_pct: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, server_default="4.50"
    )
    # Venue name — generalised: betting exchange (Betfair/Smarkets/...) or
    # classic bookmaker (Snai/Bet365/...). The DB column keeps its legacy
    # name `betting_exchange` to avoid a rename migration.
    betting_exchange: Mapped[str] = mapped_column(
        String(length=32), nullable=False, server_default="betfair"
    )
    default_market_type: Mapped[MarketType] = mapped_column(
        Enum(MarketType, name="market_type", create_constraint=True),
        nullable=False,
        server_default=MarketType.exchange.value,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ObsidianConflict(Base):
    """Detected concurrent edits — populated by import_changes when the file
    on disk has been edited and the DB record was modified after the file's
    `last_synced_at`. The frontend's conflicts drawer renders these and
    POSTs a resolution back."""

    __tablename__ = "obsidian_conflicts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    path: Mapped[str] = mapped_column(String, nullable=False)
    trade_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    db_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    file_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    db_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution: Mapped[str | None] = mapped_column(String, nullable=True)
