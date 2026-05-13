"""Bankroll API: current balance, equity-curve series, manual adjustments, snapshot.

All endpoints accept an optional ``account_id`` query parameter (or body
field for /adjust). When provided, the figure is scoped to that account;
when omitted, the response aggregates across all non-archived accounts.
``/adjust`` and ``/snapshot`` require an explicit account_id since they
write to a specific bankroll thread.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models import Account, BankrollSnapshot
from app.schemas.bankroll import (
    BankrollAdjustRequest,
    BankrollCurrent,
    BankrollSeriesPoint,
    BankrollSnapshotOut,
)
from app.services.account_service import get_account
from app.services.bankroll_service import (
    compute_current_bankroll,
    compute_daily_series,
    compute_since_inception,
    get_last_snapshot,
    take_snapshot,
)
from app.services.obsidian.sync import get_or_create_settings

router = APIRouter(prefix="/bankroll", tags=["bankroll"])

ZERO = Decimal("0")


async def _require_account(db, account_id: uuid.UUID) -> Account:
    acc = await get_account(db, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail=f"account {account_id} not found")
    return acc


async def _resolve_account_id_or_default(
    db, account_id: uuid.UUID | None
) -> uuid.UUID:
    """Used by write endpoints (adjust, snapshot). When the caller omits
    ``account_id``, fall back to ``app_settings.default_account_id``. Raises
    HTTP 422 if neither is configured."""
    if account_id is not None:
        await _require_account(db, account_id)
        return account_id
    settings = await get_or_create_settings(db)
    if settings.default_account_id is None:
        raise HTTPException(
            status_code=422,
            detail="account_id required and no default account configured",
        )
    return settings.default_account_id


@router.get("/current", response_model=BankrollCurrent)
async def get_current(
    _user: CurrentUser,
    db: DbSession,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
) -> BankrollCurrent:
    if account_id is not None:
        await _require_account(db, account_id)
    balance = await compute_current_bankroll(db, account_id=account_id)
    last_snap = await get_last_snapshot(db, account_id=account_id)
    since_pnl, _, since_roi = await compute_since_inception(db, account_id=account_id)
    return BankrollCurrent(
        balance_eur=balance.quantize(Decimal("0.01")),
        last_snapshot_at=last_snap.taken_at if last_snap else None,
        since_inception_pnl_eur=since_pnl,
        since_inception_roi_pct=since_roi,
        account_id=account_id,
    )


@router.get("/series", response_model=list[BankrollSeriesPoint])
async def get_series(
    _user: CurrentUser,
    db: DbSession,
    range: Annotated[Literal["7d", "30d", "90d", "all"], Query()] = "all",
    account_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[BankrollSeriesPoint]:
    if account_id is not None:
        await _require_account(db, account_id)
    rows = await compute_daily_series(db, range_=range, account_id=account_id)
    return [BankrollSeriesPoint(**r) for r in rows]


@router.post(
    "/adjust",
    response_model=BankrollSnapshotOut,
    status_code=status.HTTP_201_CREATED,
)
async def adjust(
    payload: BankrollAdjustRequest, _user: CurrentUser, db: DbSession
) -> BankrollSnapshotOut:
    account_id = await _resolve_account_id_or_default(db, payload.account_id)
    deposit = payload.amount_eur if payload.kind == "deposit" else ZERO
    withdrawal = payload.amount_eur if payload.kind == "withdrawal" else ZERO
    snap = await take_snapshot(
        db,
        account_id=account_id,
        deposit_eur=deposit,
        withdrawal_eur=withdrawal,
        notes=payload.notes,
    )
    await db.commit()
    return BankrollSnapshotOut.model_validate(snap)


@router.post(
    "/snapshot",
    response_model=BankrollSnapshotOut,
    status_code=status.HTTP_201_CREATED,
)
async def snapshot_now(
    _user: CurrentUser,
    db: DbSession,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
) -> BankrollSnapshotOut:
    resolved = await _resolve_account_id_or_default(db, account_id)
    snap = await take_snapshot(db, account_id=resolved, notes="manual snapshot")
    await db.commit()
    return BankrollSnapshotOut.model_validate(snap)


@router.get("/snapshots", response_model=list[BankrollSnapshotOut])
async def list_snapshots(
    _user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 10,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[BankrollSnapshot]:
    """Most recent snapshot rows (manual adjustments + daily auto-saves).
    Default 10 — the Settings page renders only the latest events; the
    full equity curve lives on /bankroll/series."""
    q = select(BankrollSnapshot).order_by(BankrollSnapshot.taken_at.desc()).limit(limit)
    if account_id is not None:
        await _require_account(db, account_id)
        q = q.where(BankrollSnapshot.account_id == account_id)
    res = await db.execute(q)
    return list(res.scalars().all())
