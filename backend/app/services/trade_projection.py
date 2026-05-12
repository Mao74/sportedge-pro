"""Project ORM ``Trade`` rows to the analytics-friendly ``TradeRow`` dataclass.

Centralised here so analytics endpoints don't drag SQLAlchemy types into the
strategy-agnostic services.
"""

from __future__ import annotations

from typing import Iterable, cast

from app.models import Trade, TradeStatus
from app.services.analytics_service import TradeRow, TradeStatusLiteral


def to_trade_row(trade: Trade) -> TradeRow:
    return TradeRow(
        id=str(trade.id),
        kickoff_at=trade.kickoff_at,
        closed_at=trade.closed_at,
        strategy_slug=trade.strategy.slug,
        strategy_name=trade.strategy.name,
        league=trade.league,
        outcome_label=trade.outcome_label,
        status=cast(TradeStatusLiteral, trade.status.value),
        stake_total=trade.stake_total,
        pnl_eur=trade.computed_pnl_eur,
    )


def to_trade_rows(trades: Iterable[Trade]) -> list[TradeRow]:
    return [to_trade_row(t) for t in trades]


__all__ = ["to_trade_row", "to_trade_rows", "TradeStatus"]
