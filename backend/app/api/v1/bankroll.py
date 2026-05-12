"""Bankroll API: current balance, equity-curve series, manual adjustments, snapshot."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models import BankrollSnapshot
from app.schemas.bankroll import (
    BankrollAdjustRequest,
    BankrollCurrent,
    BankrollSeriesPoint,
    BankrollSnapshotOut,
)
from app.services.bankroll_service import (
    compute_current_bankroll,
    compute_daily_series,
    compute_since_inception,
    get_last_snapshot,
    take_snapshot,
)

router = APIRouter(prefix="/bankroll", tags=["bankroll"])

ZERO = Decimal("0")


@router.get("/current", response_model=BankrollCurrent)
async def get_current(_user: CurrentUser, db: DbSession) -> BankrollCurrent:
    balance = await compute_current_bankroll(db)
    last_snap = await get_last_snapshot(db)
    since_pnl, _, since_roi = await compute_since_inception(db)
    return BankrollCurrent(
        balance_eur=balance.quantize(Decimal("0.01")),
        last_snapshot_at=last_snap.taken_at if last_snap else None,
        since_inception_pnl_eur=since_pnl,
        since_inception_roi_pct=since_roi,
    )


@router.get("/series", response_model=list[BankrollSeriesPoint])
async def get_series(
    _user: CurrentUser,
    db: DbSession,
    range: Annotated[Literal["7d", "30d", "90d", "all"], Query()] = "all",
) -> list[BankrollSeriesPoint]:
    rows = await compute_daily_series(db, range_=range)
    return [BankrollSeriesPoint(**r) for r in rows]


@router.post(
    "/adjust",
    response_model=BankrollSnapshotOut,
    status_code=status.HTTP_201_CREATED,
)
async def adjust(
    payload: BankrollAdjustRequest, _user: CurrentUser, db: DbSession
) -> BankrollSnapshotOut:
    deposit = payload.amount_eur if payload.kind == "deposit" else ZERO
    withdrawal = payload.amount_eur if payload.kind == "withdrawal" else ZERO
    snap = await take_snapshot(
        db, deposit_eur=deposit, withdrawal_eur=withdrawal, notes=payload.notes
    )
    await db.commit()
    return BankrollSnapshotOut.model_validate(snap)


@router.post(
    "/snapshot",
    response_model=BankrollSnapshotOut,
    status_code=status.HTTP_201_CREATED,
)
async def snapshot_now(_user: CurrentUser, db: DbSession) -> BankrollSnapshotOut:
    snap = await take_snapshot(db, notes="manual snapshot")
    await db.commit()
    return BankrollSnapshotOut.model_validate(snap)


@router.get("/snapshots", response_model=list[BankrollSnapshotOut])
async def list_snapshots(
    _user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 10,
) -> list[BankrollSnapshot]:
    """Most recent snapshot rows (manual adjustments + daily auto-saves).
    Default 10 — the Settings page renders only the latest events; the
    full equity curve lives on /bankroll/series."""
    res = await db.execute(
        select(BankrollSnapshot)
        .order_by(BankrollSnapshot.taken_at.desc())
        .limit(limit)
    )
    return list(res.scalars().all())
