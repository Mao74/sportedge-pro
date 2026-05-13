"""Trading account model.

A user maintains one or more accounts on different venues (Betfair, Smarkets,
Snai, Bet365, Betflag, ...). Each account has its own opening balance and
participates in its own bankroll thread: deposits, withdrawals, and the P/L
of trades booked against it.

Per-account fields like `commission_pct` and `market_type` become the defaults
prefilled on new trades; the trade itself still carries the canonical values
(so the PnL calculator stays strategy-agnostic and self-contained on `Trade`).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.trade import MarketType


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(String(length=64), nullable=False)
    venue: Mapped[str] = mapped_column(
        String(length=32), nullable=False, server_default="betfair"
    )
    market_type: Mapped[MarketType] = mapped_column(
        Enum(MarketType, name="market_type", create_constraint=True),
        nullable=False,
        server_default=MarketType.exchange.value,
    )
    commission_pct: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, server_default="5.00"
    )
    opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    opened_at: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index(
            "ix_accounts_name_unique",
            "name",
            unique=True,
            postgresql_where=text("archived_at IS NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Account {self.name} ({self.venue}/{self.market_type.value})>"
