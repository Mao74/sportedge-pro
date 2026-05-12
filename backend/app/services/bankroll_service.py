"""Bankroll computation + snapshot creation.

The current bankroll is *derived* every time it's queried:

    bankroll = starting_bankroll
             + sum(deposit_eur)   over snapshots
             - sum(withdrawal_eur) over snapshots
             + sum(computed_pnl_eur) over CLOSED trades

The ``bankroll_snapshots`` table doubles as the manual-adjustments ledger
(deposits / withdrawals) AND the equity-curve sample store (the daily
auto-snapshot inserts a row with deposit=withdrawal=0 just to record the
balance at end of day).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date as date_t, datetime, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import BankrollSnapshot, Trade, TradeStatus

ZERO = Decimal("0")
HUNDRED = Decimal("100")
TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")


def _q(value: Decimal, places: Decimal = TWO_PLACES) -> Decimal:
    return value.quantize(places, rounding=ROUND_HALF_EVEN)


async def _sum_snapshot_adjustments(db: AsyncSession) -> tuple[Decimal, Decimal]:
    res = await db.execute(
        select(
            func.coalesce(func.sum(BankrollSnapshot.deposit_eur), 0),
            func.coalesce(func.sum(BankrollSnapshot.withdrawal_eur), 0),
        )
    )
    deposits, withdrawals = res.one()
    return Decimal(str(deposits)), Decimal(str(withdrawals))


async def _sum_closed_pnl(db: AsyncSession) -> Decimal:
    res = await db.execute(
        select(func.coalesce(func.sum(Trade.computed_pnl_eur), 0)).where(
            Trade.status == TradeStatus.CLOSED
        )
    )
    return Decimal(str(res.scalar_one()))


async def compute_current_bankroll(db: AsyncSession) -> Decimal:
    settings = get_settings()
    starting = Decimal(settings.default_starting_bankroll)
    deposits, withdrawals = await _sum_snapshot_adjustments(db)
    closed_pnl = await _sum_closed_pnl(db)
    return starting + deposits - withdrawals + closed_pnl


async def get_last_snapshot(db: AsyncSession) -> BankrollSnapshot | None:
    res = await db.execute(
        select(BankrollSnapshot).order_by(BankrollSnapshot.taken_at.desc()).limit(1)
    )
    return res.scalar_one_or_none()


async def take_snapshot(
    db: AsyncSession,
    *,
    deposit_eur: Decimal = ZERO,
    withdrawal_eur: Decimal = ZERO,
    notes: str | None = None,
    now: datetime | None = None,
) -> BankrollSnapshot:
    """Compute the current bankroll AFTER the given adjustment and persist
    a new snapshot row with the resulting balance.
    """
    settings = get_settings()
    starting = Decimal(settings.default_starting_bankroll)
    prev_deposits, prev_withdrawals = await _sum_snapshot_adjustments(db)
    closed_pnl = await _sum_closed_pnl(db)
    balance = (
        starting
        + (prev_deposits + deposit_eur)
        - (prev_withdrawals + withdrawal_eur)
        + closed_pnl
    )
    snap = BankrollSnapshot(
        taken_at=now or datetime.now(UTC),
        balance_eur=_q(balance),
        deposit_eur=_q(deposit_eur),
        withdrawal_eur=_q(withdrawal_eur),
        notes=notes,
    )
    db.add(snap)
    await db.flush()
    return snap


# ---------------------------------------------------------------------------
# Daily series — used by /bankroll/series and the equity-curve chart.
# ---------------------------------------------------------------------------


RangeKey = Literal["7d", "30d", "90d", "all"]


def _range_to_cutoff(range_: RangeKey, now: datetime | None = None) -> datetime | None:
    if range_ == "all":
        return None
    days = {"7d": 7, "30d": 30, "90d": 90}[range_]
    base = now or datetime.now(UTC)
    return base - timedelta(days=days)


async def compute_daily_series(
    db: AsyncSession, range_: RangeKey = "all"
) -> list[dict]:
    """Returns one row per *day* with at least one event (closed trade or
    manual snapshot row). Each row carries:

    - ``taken_at`` (UTC midnight of that day)
    - ``balance_eur`` (cumulative end-of-day)
    - ``day_pnl_eur`` (closed-trade PnL summed for that day, excluding
      manual deposits/withdrawals)
    """
    settings = get_settings()
    starting = Decimal(settings.default_starting_bankroll)
    cutoff = _range_to_cutoff(range_)

    # Closed trades grouped by day.
    trade_q = select(
        func.date(Trade.closed_at).label("day"),
        func.sum(Trade.computed_pnl_eur).label("pnl"),
    ).where(Trade.status == TradeStatus.CLOSED, Trade.closed_at.isnot(None))
    trades_per_day: dict[date_t, Decimal] = {}
    for row in (await db.execute(trade_q.group_by("day"))).all():
        if row.day is None:
            continue
        trades_per_day[row.day] = Decimal(str(row.pnl))

    # Snapshot deposits/withdrawals grouped by day.
    snap_q = select(
        func.date(BankrollSnapshot.taken_at).label("day"),
        func.sum(BankrollSnapshot.deposit_eur).label("dep"),
        func.sum(BankrollSnapshot.withdrawal_eur).label("wd"),
    )
    snap_per_day: dict[date_t, Decimal] = defaultdict(lambda: ZERO)
    for row in (await db.execute(snap_q.group_by("day"))).all():
        if row.day is None:
            continue
        snap_per_day[row.day] = Decimal(str(row.dep)) - Decimal(str(row.wd))

    all_days = sorted(set(trades_per_day) | set(snap_per_day))
    cum = starting
    out: list[dict] = []
    for day in all_days:
        day_pnl = trades_per_day.get(day, ZERO)
        cum += day_pnl + snap_per_day.get(day, ZERO)
        ts = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
        if cutoff is not None and ts < cutoff:
            continue
        out.append(
            {
                "taken_at": ts,
                "balance_eur": _q(cum),
                "day_pnl_eur": _q(day_pnl),
            }
        )
    return out


async def compute_since_inception(
    db: AsyncSession,
) -> tuple[Decimal, Decimal, Decimal]:
    """Returns (closed_pnl, total_stake, roi_pct) for ALL closed trades
    since inception."""
    res = await db.execute(
        select(
            func.coalesce(func.sum(Trade.computed_pnl_eur), 0),
            func.coalesce(func.sum(Trade.stake_total), 0),
        ).where(Trade.status == TradeStatus.CLOSED)
    )
    pnl, stake = res.one()
    pnl_d = Decimal(str(pnl))
    stake_d = Decimal(str(stake))
    roi = (pnl_d / stake_d * HUNDRED) if stake_d > 0 else ZERO
    return _q(pnl_d), _q(stake_d), _q(roi, FOUR_PLACES)
