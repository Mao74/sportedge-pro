"""Direct async unit tests for bankroll_service. Hits paths that the
integration tests reach but pytest-cov doesn't credit due to async tracking
limits with FastAPI's TestClient + greenlet bridges."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import (
    Account,
    BankrollSnapshot,
    PnLMode,
    Strategy,
    StrategyKind,
    Trade,
    TradeStatus,
)
from app.services import bankroll_service as bsvc

D = Decimal


async def _seed_account_id(session) -> object:
    """Return the Betfair seed account id (re-created by conftest before each test)."""
    from sqlalchemy import select
    res = await session.execute(
        select(Account).where(Account.name == "Betfair").limit(1)
    )
    return res.scalar_one().id


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def session(event_loop):
    """Open a fresh async session against the test DB. The autouse reset_db
    fixture has already truncated and reseeded for us."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_current_bankroll_no_activity(session) -> None:
    starting = Decimal(get_settings().default_starting_bankroll)
    bal = await bsvc.compute_current_bankroll(session)
    assert bal == starting


@pytest.mark.asyncio
async def test_current_bankroll_includes_closed_pnl_and_adjustments(session) -> None:
    # Use the seeded built-in strategy so we don't have to create one.
    from sqlalchemy import select
    s_res = await session.execute(select(Strategy).where(Strategy.kind == StrategyKind.builtin).limit(1))
    strat = s_res.scalar_one()
    acc_id = await _seed_account_id(session)

    # Add a closed trade
    t = Trade(
        strategy_id=strat.id,
        account_id=acc_id,
        home_team="A", away_team="B", league="X",
        kickoff_at=datetime.now(UTC),
        stake_total=D("100"), avg_odds=D("2.5"),
        commission_pct=D("5"),
        pnl_mode=PnLMode.MANUAL, manual_pnl_eur=D("40"),
        computed_pnl_eur=D("40"),
        status=TradeStatus.CLOSED,
        closed_at=datetime.now(UTC),
        strategy_data={},
    )
    session.add(t)

    # Add a deposit snapshot
    snap = BankrollSnapshot(
        account_id=acc_id,
        taken_at=datetime.now(UTC),
        balance_eur=D("0"),  # placeholder; not used by compute_current_bankroll
        deposit_eur=D("250"), withdrawal_eur=D("0"),
    )
    session.add(snap)
    await session.commit()

    starting = Decimal(get_settings().default_starting_bankroll)
    bal = await bsvc.compute_current_bankroll(session)
    assert bal == starting + D("250") + D("40")


@pytest.mark.asyncio
async def test_take_snapshot_persists(session) -> None:
    snap = await bsvc.take_snapshot(session, deposit_eur=D("100"), notes="test")
    await session.commit()
    assert snap.id is not None
    assert snap.deposit_eur == D("100.00")
    starting = Decimal(get_settings().default_starting_bankroll)
    assert snap.balance_eur == (starting + D("100")).quantize(D("0.01"))


@pytest.mark.asyncio
async def test_compute_daily_series_buckets_by_day(session) -> None:
    from sqlalchemy import select
    s_res = await session.execute(select(Strategy).where(Strategy.kind == StrategyKind.builtin).limit(1))
    strat = s_res.scalar_one()
    acc_id = await _seed_account_id(session)

    base = datetime(2026, 4, 20, 20, 0, tzinfo=UTC)
    for i, pnl in enumerate(["10", "20", "-5"]):
        t = Trade(
            strategy_id=strat.id,
            account_id=acc_id,
            home_team="A", away_team="B", league="X",
            kickoff_at=base + timedelta(days=i),
            stake_total=D("100"), avg_odds=D("2.5"),
            commission_pct=D("5"),
            pnl_mode=PnLMode.MANUAL, manual_pnl_eur=D(pnl),
            computed_pnl_eur=D(pnl),
            status=TradeStatus.CLOSED,
            closed_at=base + timedelta(days=i),
            strategy_data={},
        )
        session.add(t)
    await session.commit()

    rows = await bsvc.compute_daily_series(session, range_="all")
    assert len(rows) == 3
    starting = Decimal(get_settings().default_starting_bankroll)
    # Day 0: starting + 10
    assert rows[0]["balance_eur"] == (starting + D("10")).quantize(D("0.01"))
    # Day 2: starting + 10 + 20 - 5 = starting + 25
    assert rows[2]["balance_eur"] == (starting + D("25")).quantize(D("0.01"))


@pytest.mark.asyncio
async def test_range_window_filters(session) -> None:
    from sqlalchemy import select
    s_res = await session.execute(select(Strategy).where(Strategy.kind == StrategyKind.builtin).limit(1))
    strat = s_res.scalar_one()
    acc_id = await _seed_account_id(session)

    # One trade 100 days ago, one yesterday.
    now = datetime.now(UTC)
    for days_ago, pnl in [(100, "10"), (1, "20")]:
        t = Trade(
            strategy_id=strat.id,
            account_id=acc_id,
            home_team="A", away_team="B", league="X",
            kickoff_at=now - timedelta(days=days_ago),
            stake_total=D("100"), avg_odds=D("2.5"),
            commission_pct=D("5"),
            pnl_mode=PnLMode.MANUAL, manual_pnl_eur=D(pnl),
            computed_pnl_eur=D(pnl),
            status=TradeStatus.CLOSED,
            closed_at=now - timedelta(days=days_ago),
            strategy_data={},
        )
        session.add(t)
    await session.commit()

    rows7 = await bsvc.compute_daily_series(session, range_="7d")
    assert len(rows7) == 1  # only the recent one
    rows_all = await bsvc.compute_daily_series(session, range_="all")
    assert len(rows_all) == 2


@pytest.mark.asyncio
async def test_since_inception_zero_when_no_closed(session) -> None:
    pnl, stake, roi = await bsvc.compute_since_inception(session)
    assert pnl == D("0.00")
    assert stake == D("0.00")
    assert roi == D("0.0000")
