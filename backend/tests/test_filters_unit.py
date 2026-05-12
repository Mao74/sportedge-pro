"""Unit tests for the shared trade-filter builder."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from app.api._filters import build_trade_where
from app.models import PnLMode, Trade, TradeStatus


def _compile(where) -> str:
    """Render the WHERE clause to a SQL string for inspection."""
    stmt = select(Trade).where(where)
    return str(stmt.compile(compile_kwargs={"literal_binds": False}))


def test_no_filters_yields_trivial_clause() -> None:
    sql = _compile(build_trade_where())
    # 'TRUE' shows up when no conditions are supplied.
    assert "TRUE" in sql.upper()


def test_strategy_id_in_clause() -> None:
    sid = uuid.uuid4()
    sql = _compile(build_trade_where(strategy_id=sid))
    assert "trades.strategy_id" in sql


def test_pnl_range_emitted() -> None:
    sql = _compile(
        build_trade_where(pnl_min=Decimal("10.00"), pnl_max=Decimal("100.00"))
    )
    assert "computed_pnl_eur" in sql


def test_date_range_emitted() -> None:
    sql = _compile(build_trade_where(
        date_from=datetime(2026, 4, 1, tzinfo=UTC),
        date_to=datetime(2026, 4, 30, tzinfo=UTC),
    ))
    assert "kickoff_at" in sql


def test_full_text_query_emits_tsvector_match() -> None:
    sql = _compile(build_trade_where(q="real madrid"))
    assert "to_tsvector" in sql.lower()


def test_tags_filter_emits_in_subquery_per_tag() -> None:
    sql = _compile(build_trade_where(tag=["live", "high-xg"]))
    # One IN subquery per tag (AND semantics)
    assert sql.lower().count("in (select") >= 2


def test_status_and_pnl_mode_combined() -> None:
    sql = _compile(build_trade_where(
        status=TradeStatus.CLOSED, pnl_mode=PnLMode.MANUAL,
    ))
    assert "status" in sql
    assert "pnl_mode" in sql


def test_outcome_label_and_league() -> None:
    sql = _compile(build_trade_where(
        outcome_label="WIN", league="Serie A",
    ))
    assert "outcome_label" in sql
    assert "league" in sql
