"""Bankroll computation + snapshot creation.

The current bankroll is *derived* every time it's queried:

    bankroll(account) = account.opening_balance
                     + sum(deposit_eur)    over snapshots of account
                     - sum(withdrawal_eur) over snapshots of account
                     + sum(computed_pnl_eur) over CLOSED trades of account

When called without an ``account_id`` the figure is aggregated across all
non-archived accounts (sum of opening balances + sum of adjustments + sum
of closed PnL).

The ``bankroll_snapshots`` table doubles as the manual-adjustments ledger
(deposits / withdrawals) AND the equity-curve sample store (the daily
auto-snapshot inserts a row with deposit=withdrawal=0 just to record the
balance at end of day).
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, date as date_t, datetime, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Account, AppSettings, BankrollSnapshot, Trade, TradeStatus

ZERO = Decimal("0")
HUNDRED = Decimal("100")
TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")


def _q(value: Decimal, places: Decimal = TWO_PLACES) -> Decimal:
    return value.quantize(places, rounding=ROUND_HALF_EVEN)


async def _opening_balance(
    db: AsyncSession, account_id: uuid.UUID | None
) -> Decimal:
    if account_id is not None:
        res = await db.execute(
            select(Account.opening_balance).where(Account.id == account_id)
        )
        val = res.scalar_one_or_none()
        return Decimal(str(val)) if val is not None else ZERO

    # Aggregate: sum opening_balance of all non-archived accounts.
    res = await db.execute(
        select(func.coalesce(func.sum(Account.opening_balance), 0)).where(
            Account.archived_at.is_(None)
        )
    )
    return Decimal(str(res.scalar_one()))


async def _sum_snapshot_adjustments(
    db: AsyncSession, account_id: uuid.UUID | None
) -> tuple[Decimal, Decimal]:
    q = select(
        func.coalesce(func.sum(BankrollSnapshot.deposit_eur), 0),
        func.coalesce(func.sum(BankrollSnapshot.withdrawal_eur), 0),
    )
    if account_id is not None:
        q = q.where(BankrollSnapshot.account_id == account_id)
    res = await db.execute(q)
    deposits, withdrawals = res.one()
    return Decimal(str(deposits)), Decimal(str(withdrawals))


async def _sum_closed_pnl(
    db: AsyncSession, account_id: uuid.UUID | None
) -> Decimal:
    q = select(func.coalesce(func.sum(Trade.computed_pnl_eur), 0)).where(
        Trade.status == TradeStatus.CLOSED
    )
    if account_id is not None:
        q = q.where(Trade.account_id == account_id)
    res = await db.execute(q)
    return Decimal(str(res.scalar_one()))


async def compute_current_bankroll(
    db: AsyncSession, account_id: uuid.UUID | None = None
) -> Decimal:
    starting = await _opening_balance(db, account_id)
    deposits, withdrawals = await _sum_snapshot_adjustments(db, account_id)
    closed_pnl = await _sum_closed_pnl(db, account_id)
    return starting + deposits - withdrawals + closed_pnl


async def get_last_snapshot(
    db: AsyncSession, account_id: uuid.UUID | None = None
) -> BankrollSnapshot | None:
    q = select(BankrollSnapshot).order_by(BankrollSnapshot.taken_at.desc()).limit(1)
    if account_id is not None:
        q = q.where(BankrollSnapshot.account_id == account_id)
    res = await db.execute(q)
    return res.scalar_one_or_none()


async def _resolve_default_account_id(db: AsyncSession) -> uuid.UUID | None:
    res = await db.execute(select(AppSettings.default_account_id).limit(1))
    return res.scalar_one_or_none()


async def take_snapshot(
    db: AsyncSession,
    *,
    account_id: uuid.UUID | None = None,
    deposit_eur: Decimal = ZERO,
    withdrawal_eur: Decimal = ZERO,
    notes: str | None = None,
    now: datetime | None = None,
) -> BankrollSnapshot:
    """Compute the current bankroll FOR THE GIVEN ACCOUNT after the given
    adjustment and persist a new snapshot row with the resulting balance.

    When ``account_id`` is None we fall back to
    ``app_settings.default_account_id`` for back-compat with pre-multi-account
    callers (tests, scheduler). Raises ValueError if neither is set.
    """
    if account_id is None:
        account_id = await _resolve_default_account_id(db)
        if account_id is None:
            raise ValueError(
                "take_snapshot requires account_id; no default account configured"
            )
    starting = await _opening_balance(db, account_id)
    prev_deposits, prev_withdrawals = await _sum_snapshot_adjustments(db, account_id)
    closed_pnl = await _sum_closed_pnl(db, account_id)
    balance = (
        starting
        + (prev_deposits + deposit_eur)
        - (prev_withdrawals + withdrawal_eur)
        + closed_pnl
    )
    snap = BankrollSnapshot(
        account_id=account_id,
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
    db: AsyncSession,
    range_: RangeKey = "all",
    account_id: uuid.UUID | None = None,
) -> list[dict]:
    """Returns one row per *day* with at least one event (closed trade or
    manual snapshot row). Each row carries:

    - ``taken_at`` (UTC midnight of that day)
    - ``balance_eur`` (cumulative end-of-day)
    - ``day_pnl_eur`` (closed-trade PnL summed for that day, excluding
      manual deposits/withdrawals)

    Scoped to a single account when ``account_id`` is given; otherwise
    aggregated across all non-archived accounts.
    """
    starting = await _opening_balance(db, account_id)
    cutoff = _range_to_cutoff(range_)

    # Closed trades grouped by day.
    trade_q = select(
        func.date(Trade.closed_at).label("day"),
        func.sum(Trade.computed_pnl_eur).label("pnl"),
    ).where(Trade.status == TradeStatus.CLOSED, Trade.closed_at.isnot(None))
    if account_id is not None:
        trade_q = trade_q.where(Trade.account_id == account_id)

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
    if account_id is not None:
        snap_q = snap_q.where(BankrollSnapshot.account_id == account_id)

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
    account_id: uuid.UUID | None = None,
) -> tuple[Decimal, Decimal, Decimal]:
    """Returns (closed_pnl, total_stake, roi_pct) for ALL closed trades
    since inception. Scoped to ``account_id`` when given."""
    q = select(
        func.coalesce(func.sum(Trade.computed_pnl_eur), 0),
        func.coalesce(func.sum(Trade.stake_total), 0),
    ).where(Trade.status == TradeStatus.CLOSED)
    if account_id is not None:
        q = q.where(Trade.account_id == account_id)
    res = await db.execute(q)
    pnl, stake = res.one()
    pnl_d = Decimal(str(pnl))
    stake_d = Decimal(str(stake))
    roi = (pnl_d / stake_d * HUNDRED) if stake_d > 0 else ZERO
    return _q(pnl_d), _q(stake_d), _q(roi, FOUR_PLACES)
