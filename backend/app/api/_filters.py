"""Shared filter-building helpers. ``/trades`` and ``/analytics/*`` use the
same query parameters so the user can navigate from a filtered table view
into the corresponding analytics chart without re-typing filters."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import and_, func, select, text
from sqlalchemy.sql import ColumnElement

from app.models import PnLMode, Tag, Trade, TradeStatus, TradeTag


def build_trade_where(
    *,
    strategy_id: uuid.UUID | None = None,
    league: str | None = None,
    status: TradeStatus | None = None,
    outcome_label: str | None = None,
    pnl_mode: PnLMode | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    pnl_min: Decimal | None = None,
    pnl_max: Decimal | None = None,
    tag: list[str] | None = None,
    q: str | None = None,
    kickoff_dow: int | None = None,   # 0=Mon..6=Sun (Python convention)
    kickoff_hour: int | None = None,  # 0..23
) -> ColumnElement[bool]:
    conditions = []
    if strategy_id is not None:
        conditions.append(Trade.strategy_id == strategy_id)
    if league is not None:
        conditions.append(Trade.league == league)
    if status is not None:
        conditions.append(Trade.status == status)
    if outcome_label is not None:
        conditions.append(Trade.outcome_label == outcome_label)
    if pnl_mode is not None:
        conditions.append(Trade.pnl_mode == pnl_mode)
    if date_from is not None:
        conditions.append(Trade.kickoff_at >= date_from)
    if date_to is not None:
        conditions.append(Trade.kickoff_at <= date_to)
    if pnl_min is not None:
        conditions.append(Trade.computed_pnl_eur >= pnl_min)
    if pnl_max is not None:
        conditions.append(Trade.computed_pnl_eur <= pnl_max)
    if tag:
        for t in tag:
            sub = (
                select(TradeTag.trade_id)
                .join(Tag, Tag.id == TradeTag.tag_id)
                .where(Tag.name == t)
            )
            conditions.append(Trade.id.in_(sub))
    if q:
        ts = func.to_tsvector(
            "simple",
            Trade.home_team + text("' '") + Trade.away_team + text("' '")
            + func.coalesce(Trade.notes_md, ""),
        )
        conditions.append(ts.op("@@")(func.plainto_tsquery("simple", q)))
    if kickoff_dow is not None:
        # Postgres `isodow` is 1..7 (Mon..Sun); the API accepts 0..6 to match
        # Python's datetime.weekday() and the calendar-heatmap rendering.
        conditions.append(
            func.cast(func.extract("isodow", Trade.kickoff_at), int) - 1 == kickoff_dow
        )
    if kickoff_hour is not None:
        conditions.append(
            func.cast(func.extract("hour", Trade.kickoff_at), int) == kickoff_hour
        )
    return and_(*conditions) if conditions else and_(text("TRUE"))
