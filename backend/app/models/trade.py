"""Trade model — universal columns + JSONB strategy-specific data."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class PnLMode(str, enum.Enum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"
    CASHOUT_ODDS = "CASHOUT_ODDS"


class TradeStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    VOID = "VOID"


class MarketType(str, enum.Enum):
    """How the trade venue treats commission.

    - ``exchange``: betting exchange (Betfair, Smarkets, etc.) — commission
      is applied to winning components (current default).
    - ``classic``: classic bookmaker (Snai, Bet365, etc.) — quoted odds are
      already net; the PnL calculator forces commission_factor to 1.0.
    """

    exchange = "exchange"
    classic = "classic"


class Trade(Base, TimestampMixin):
    __tablename__ = "trades"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("strategies.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Match metadata
    sport: Mapped[str] = mapped_column(String, nullable=False, server_default="football")
    home_team: Mapped[str] = mapped_column(String, nullable=False)
    away_team: Mapped[str] = mapped_column(String, nullable=False)
    league: Mapped[str] = mapped_column(String, nullable=False)
    kickoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Scores
    ht_score_home: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ht_score_away: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ft_score_home: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ft_score_away: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Money
    stake_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    avg_odds: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    commission_pct: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, server_default="5.00"
    )
    market_type: Mapped[MarketType] = mapped_column(
        Enum(MarketType, name="market_type", create_constraint=True),
        nullable=False,
        server_default=MarketType.exchange.value,
    )

    # PnL
    pnl_mode: Mapped[PnLMode] = mapped_column(
        Enum(PnLMode, name="pnl_mode", create_constraint=True),
        nullable=False,
    )
    cashout_odds: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    manual_pnl_eur: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    computed_pnl_eur: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Outcome / lifecycle
    outcome_label: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[TradeStatus] = mapped_column(
        Enum(TradeStatus, name="trade_status", create_constraint=True),
        nullable=False,
        server_default=TradeStatus.OPEN.value,
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_obsidian_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Strategy-specific dynamic fields, validated against strategy.field_schema
    strategy_data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    notes_md: Mapped[str | None] = mapped_column(Text, nullable=True)

    strategy: Mapped["Strategy"] = relationship(  # noqa: F821 — forward ref
        back_populates="trades", lazy="joined"
    )
    tags: Mapped[list["Tag"]] = relationship(  # noqa: F821 — forward ref
        secondary="trade_tags",
        back_populates="trades",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_trades_kickoff_at", text("kickoff_at DESC")),
        Index("ix_trades_strategy_kickoff", "strategy_id", text("kickoff_at DESC")),
        Index(
            "ix_trades_status_open",
            "status",
            postgresql_where=text("status = 'OPEN'"),
        ),
        Index("ix_trades_strategy_data_gin", "strategy_data", postgresql_using="gin"),
        Index(
            "ix_trades_search_gin",
            text(
                "to_tsvector('simple', "
                "home_team || ' ' || away_team || ' ' || coalesce(notes_md, ''))"
            ),
            postgresql_using="gin",
        ),
    )

    def __repr__(self) -> str:
        return f"<Trade {self.home_team} vs {self.away_team} {self.kickoff_at:%Y-%m-%d}>"
