"""Trades CRUD + close shortcut + tag attach/detach + list with filters and aggregates."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, File, Form, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import Integer, Numeric, and_, cast, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.core.problem_details import not_found, unprocessable
from app.models import Account, PnLMode, Strategy, Tag, Trade, TradeStatus, TradeTag
from app.services.account_service import get_account
from app.services.obsidian.sync import get_or_create_settings
from app.schemas.csv_io import CsvImportResult
from app.schemas.trade import (
    TagAttachRequest,
    TradeAggregates,
    TradeClose,
    TradeCreate,
    TradeListResponse,
    TradeOut,
    TradeUpdate,
)
from app.services.csv_io import (
    all_trades_for_export,
    export_trades_csv,
    import_trades_csv,
)
from app.services.obsidian.queue import enqueue_trade, kickoff_day
from app.services.pnl_calculator import PnLInputs, compute_pnl
from app.services.strategy_data_validator import validate_strategy_data

router = APIRouter(prefix="/trades", tags=["trades"])

ZERO = Decimal("0")
HUNDRED = Decimal("100")

PNL_AFFECTING_FIELDS = {
    "stake_total", "avg_odds", "commission_pct", "market_type",
    "pnl_mode", "cashout_odds", "manual_pnl_eur",
    "outcome_label", "position_side", "strategy_data", "strategy_id",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _load_trade(db: AsyncSession, trade_id: uuid.UUID) -> Trade:
    res = await db.execute(
        select(Trade)
        .options(selectinload(Trade.strategy), selectinload(Trade.tags))
        .where(Trade.id == trade_id)
    )
    trade = res.scalar_one_or_none()
    if trade is None:
        raise not_found(f"Trade {trade_id} does not exist.")
    return trade


async def _load_strategy(db: AsyncSession, strategy_id: uuid.UUID) -> Strategy:
    res = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
    s = res.scalar_one_or_none()
    if s is None:
        raise not_found(f"Strategy {strategy_id} does not exist.")
    return s


async def _load_account(
    db: AsyncSession, account_id: uuid.UUID | None
) -> Account:
    """Resolve the account for a trade. Falls back to
    ``app_settings.default_account_id`` when ``account_id`` is None
    (back-compat with single-account clients)."""
    if account_id is None:
        settings = await get_or_create_settings(db)
        if settings.default_account_id is None:
            raise unprocessable(
                "No account_id supplied and no default account configured."
            )
        account_id = settings.default_account_id
    acc = await get_account(db, account_id)
    if acc is None:
        raise not_found(f"Account {account_id} does not exist.")
    return acc


def _validate_strategy_data_or_raise(
    strategy: Strategy, strategy_data: dict[str, Any], trade_status: str
) -> None:
    errs = validate_strategy_data(
        field_schema=strategy.field_schema or {},
        strategy_data=strategy_data,
        trade_status=trade_status,
    )
    if errs:
        raise unprocessable(
            f"strategy_data is invalid for strategy {strategy.slug!r}.",
            strategy_id=str(strategy.id),
            errors=errs,
        )


def _build_pnl_inputs(trade: Trade) -> PnLInputs:
    sd = trade.strategy_data or {}
    return PnLInputs(
        pnl_mode=trade.pnl_mode,
        stake_total=trade.stake_total,
        avg_odds=trade.avg_odds,
        commission_pct=trade.commission_pct,
        market_type=trade.market_type,
        cashout_odds=trade.cashout_odds,
        position_side=sd.get("position_side"),
        manual_pnl_eur=trade.manual_pnl_eur,
        outcome_label=trade.outcome_label,
        strategy_data=sd,
    )


def _recompute_pnl(trade: Trade) -> None:
    trade.computed_pnl_eur = compute_pnl(_build_pnl_inputs(trade))


def _trade_to_out(trade: Trade) -> TradeOut:
    """Build a TradeOut, lifting position_side from strategy_data to top-level."""
    sd = trade.strategy_data or {}
    out = TradeOut.model_validate({
        **{c.name: getattr(trade, c.name) for c in trade.__table__.columns},
        "strategy": trade.strategy,
        "position_side": sd.get("position_side"),
        "tags": list(trade.tags),
    })
    return out


async def _resolve_tags(db: AsyncSession, names: list[str]) -> list[Tag]:
    """Find-or-create tags by name. Returns Tag rows in input order (deduped)."""
    if not names:
        return []
    seen: dict[str, Tag] = {}
    res = await db.execute(select(Tag).where(Tag.name.in_(names)))
    for t in res.scalars():
        seen[t.name] = t
    out: list[Tag] = []
    visited: set[str] = set()
    for n in names:
        if n in visited:
            continue
        visited.add(n)
        if n in seen:
            out.append(seen[n])
        else:
            t = Tag(name=n)
            db.add(t)
            await db.flush()
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------


@router.post("", response_model=TradeOut, status_code=status.HTTP_201_CREATED)
async def create_trade(
    payload: TradeCreate, _user: CurrentUser, db: DbSession
) -> TradeOut:
    strategy = await _load_strategy(db, payload.strategy_id)
    account = await _load_account(db, payload.account_id)

    # Merge top-level position_side into strategy_data so PnL calc + DB persist see it.
    strategy_data = dict(payload.strategy_data or {})
    if payload.position_side is not None:
        strategy_data["position_side"] = payload.position_side

    _validate_strategy_data_or_raise(strategy, strategy_data, payload.status.value)

    trade = Trade(
        strategy_id=strategy.id,
        account_id=account.id,
        sport=payload.sport,
        home_team=payload.home_team,
        away_team=payload.away_team,
        league=payload.league,
        kickoff_at=payload.kickoff_at,
        ht_score_home=payload.ht_score_home,
        ht_score_away=payload.ht_score_away,
        ft_score_home=payload.ft_score_home,
        ft_score_away=payload.ft_score_away,
        stake_total=payload.stake_total,
        avg_odds=payload.avg_odds,
        commission_pct=payload.commission_pct,
        market_type=payload.market_type,
        pnl_mode=payload.pnl_mode,
        cashout_odds=payload.cashout_odds,
        manual_pnl_eur=payload.manual_pnl_eur,
        outcome_label=payload.outcome_label,
        status=payload.status,
        strategy_data=strategy_data,
        notes_md=payload.notes_md,
        computed_pnl_eur=ZERO,  # placeholder — recomputed below
        closed_at=(
            payload.closed_at
            if payload.closed_at is not None
            else (datetime.now(UTC) if payload.status is TradeStatus.CLOSED else None)
        ),
    )
    trade.strategy = strategy
    _recompute_pnl(trade)

    if payload.tags:
        trade.tags = await _resolve_tags(db, payload.tags)

    db.add(trade)
    await db.commit()
    fresh = await _load_trade(db, trade.id)
    await enqueue_trade(fresh.id, day=kickoff_day(fresh.closed_at))
    return _trade_to_out(fresh)


# ---------------------------------------------------------------------------
# READ — single
# ---------------------------------------------------------------------------


@router.get("/{trade_id}", response_model=TradeOut)
async def get_trade(trade_id: uuid.UUID, _user: CurrentUser, db: DbSession) -> TradeOut:
    return _trade_to_out(await _load_trade(db, trade_id))


# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------


@router.patch("/{trade_id}", response_model=TradeOut)
async def update_trade(
    trade_id: uuid.UUID, payload: TradeUpdate, _user: CurrentUser, db: DbSession
) -> TradeOut:
    trade = await _load_trade(db, trade_id)
    data = payload.model_dump(exclude_unset=True)

    # If strategy_id changes, validate new strategy exists.
    new_strategy = trade.strategy
    if "strategy_id" in data and data["strategy_id"] != trade.strategy_id:
        new_strategy = await _load_strategy(db, data["strategy_id"])

    # If account_id changes, validate new account exists.
    if "account_id" in data and data["account_id"] is not None:
        new_acc = await _load_account(db, data["account_id"])
        # accept; setattr below will write it
        data["account_id"] = new_acc.id

    # Merge position_side into strategy_data before validation. If the caller
    # replaces strategy_data without explicitly touching position_side, we
    # preserve the existing value (it's a universal field, not strategy-specific).
    old_sd = dict(trade.strategy_data or {})
    new_strategy_data = (
        dict(data["strategy_data"]) if data.get("strategy_data") is not None else old_sd
    )
    if "position_side" in data:
        if data["position_side"] is None:
            new_strategy_data.pop("position_side", None)
        else:
            new_strategy_data["position_side"] = data["position_side"]
    elif (
        data.get("strategy_data") is not None
        and "position_side" not in new_strategy_data
        and "position_side" in old_sd
    ):
        new_strategy_data["position_side"] = old_sd["position_side"]

    new_status = data.get("status", trade.status).value if isinstance(
        data.get("status", trade.status), TradeStatus
    ) else (trade.status.value if isinstance(trade.status, TradeStatus) else str(trade.status))

    _validate_strategy_data_or_raise(new_strategy, new_strategy_data, new_status)

    # Apply scalar field updates.
    for k, v in data.items():
        if k in {"strategy_data", "tags", "position_side"}:
            continue
        setattr(trade, k, v)
    trade.strategy = new_strategy
    trade.strategy_data = new_strategy_data

    if data.get("status") is TradeStatus.CLOSED and trade.closed_at is None:
        trade.closed_at = datetime.now(UTC)
    elif data.get("status") is not None and data["status"] is not TradeStatus.CLOSED:
        trade.closed_at = None

    if PNL_AFFECTING_FIELDS & data.keys() or "position_side" in data:
        _recompute_pnl(trade)

    if "tags" in data and data["tags"] is not None:
        trade.tags = await _resolve_tags(db, data["tags"])

    await db.commit()
    fresh = await _load_trade(db, trade.id)
    await enqueue_trade(fresh.id, day=kickoff_day(fresh.closed_at))
    return _trade_to_out(fresh)


# ---------------------------------------------------------------------------
# CLOSE shortcut
# ---------------------------------------------------------------------------


@router.post("/{trade_id}/close", response_model=TradeOut)
async def close_trade(
    trade_id: uuid.UUID, payload: TradeClose, _user: CurrentUser, db: DbSession
) -> TradeOut:
    trade = await _load_trade(db, trade_id)
    data = payload.model_dump(exclude_unset=True)

    new_strategy_data = (
        dict(data["strategy_data"]) if data.get("strategy_data") is not None
        else dict(trade.strategy_data or {})
    )
    if "position_side" in data:
        new_strategy_data["position_side"] = data["position_side"]

    _validate_strategy_data_or_raise(trade.strategy, new_strategy_data, "CLOSED")

    for k in ("pnl_mode", "cashout_odds", "manual_pnl_eur",
              "outcome_label", "ft_score_home", "ft_score_away", "notes_md"):
        if k in data:
            setattr(trade, k, data[k])
    trade.strategy_data = new_strategy_data
    trade.status = TradeStatus.CLOSED
    trade.closed_at = datetime.now(UTC)

    _recompute_pnl(trade)

    await db.commit()
    fresh = await _load_trade(db, trade.id)
    await enqueue_trade(fresh.id, day=kickoff_day(fresh.closed_at))
    return _trade_to_out(fresh)


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------


@router.delete("/{trade_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trade(trade_id: uuid.UUID, _user: CurrentUser, db: DbSession) -> None:
    trade = await _load_trade(db, trade_id)
    closed_day = kickoff_day(trade.closed_at)
    await db.delete(trade)
    await db.commit()
    if closed_day is not None:
        await enqueue_trade(uuid.uuid4(), day=closed_day)  # re-render daily


# ---------------------------------------------------------------------------
# Tag attach / detach
# ---------------------------------------------------------------------------


@router.post("/{trade_id}/tags", response_model=TradeOut)
async def attach_tag(
    trade_id: uuid.UUID, payload: TagAttachRequest, _user: CurrentUser, db: DbSession
) -> TradeOut:
    trade = await _load_trade(db, trade_id)

    if payload.tag_id is not None:
        res = await db.execute(select(Tag).where(Tag.id == payload.tag_id))
        tag = res.scalar_one_or_none()
        if tag is None:
            raise not_found(f"Tag {payload.tag_id} does not exist.")
    else:
        # find-or-create by name
        res = await db.execute(select(Tag).where(Tag.name == payload.name))
        tag = res.scalar_one_or_none()
        if tag is None:
            tag = Tag(name=payload.name, color_hex=payload.color_hex)
            db.add(tag)
            await db.flush()

    if tag not in trade.tags:
        trade.tags.append(tag)
        await db.commit()
        trade = await _load_trade(db, trade.id)
    return _trade_to_out(trade)


@router.delete("/{trade_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def detach_tag(
    trade_id: uuid.UUID, tag_id: uuid.UUID, _user: CurrentUser, db: DbSession
) -> None:
    trade = await _load_trade(db, trade_id)
    if not any(t.id == tag_id for t in trade.tags):
        raise not_found(f"Tag {tag_id} is not attached to trade {trade_id}.")
    trade.tags = [t for t in trade.tags if t.id != tag_id]
    await db.commit()


# ---------------------------------------------------------------------------
# CSV import / export
# ---------------------------------------------------------------------------


@router.get("/export.csv", include_in_schema=True)
async def export_csv(_user: CurrentUser, db: DbSession) -> Response:
    """Stream the full trade history as a CSV download.

    The endpoint reads the entire ``trades`` table (with strategy + tags
    eagerly loaded) and returns a single CSV blob. For huge journals we'd
    switch to chunked streaming, but realistically a single trader produces
    O(thousands) of rows per year — well within memory.
    """
    trades = await all_trades_for_export(db)
    body = export_trades_csv(trades)
    filename = f"sportedge-trades-{datetime.now(UTC).strftime('%Y%m%d')}.csv"
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import", response_model=CsvImportResult)
async def import_csv(
    _user: CurrentUser,
    db: DbSession,
    file: Annotated[UploadFile, File(description="CSV file with header row")],
    dry_run: Annotated[bool, Form(description="If true, only validate; do not write")] = True,
) -> CsvImportResult:
    """Parse a CSV file and either preview (dry-run) or commit the trades.

    Each row is validated independently — bad rows are collected, valid
    rows insert as a single transaction. Commit only when ``dry_run=false``.
    """
    raw = await file.read()
    try:
        csv_text = raw.decode("utf-8-sig")  # tolerate UTF-8 BOM from Excel
    except UnicodeDecodeError as e:
        raise unprocessable(f"CSV must be UTF-8 encoded: {e}") from e

    result = await import_trades_csv(db, csv_text, dry_run=dry_run)
    return CsvImportResult(
        parsed_rows=result.parsed_rows,
        valid_rows=result.valid_rows,
        errors=[
            {"row_index": e.row_index, "column": e.column, "detail": e.detail}
            for e in result.errors
        ],
        inserted=result.inserted,
        dry_run=result.dry_run,
    )


# ---------------------------------------------------------------------------
# LIST + filter + paginate + aggregates
# ---------------------------------------------------------------------------


SortField = Literal["kickoff_at", "-kickoff_at", "pnl", "-pnl", "stake", "-stake"]


@router.get("", response_model=TradeListResponse)
async def list_trades(
    _user: CurrentUser,
    db: DbSession,
    strategy_id: Annotated[uuid.UUID | None, Query()] = None,
    league: Annotated[str | None, Query()] = None,
    status_: Annotated[TradeStatus | None, Query(alias="status")] = None,
    outcome_label: Annotated[str | None, Query()] = None,
    pnl_mode: Annotated[PnLMode | None, Query()] = None,
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
    pnl_min: Annotated[Decimal | None, Query()] = None,
    pnl_max: Annotated[Decimal | None, Query()] = None,
    tag: Annotated[list[str] | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
    kickoff_dow: Annotated[int | None, Query(ge=0, le=6)] = None,
    kickoff_hour: Annotated[int | None, Query(ge=0, le=23)] = None,
    sort: Annotated[SortField, Query()] = "-kickoff_at",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 20,
) -> TradeListResponse:
    where = []
    if strategy_id is not None:
        where.append(Trade.strategy_id == strategy_id)
    if league is not None:
        where.append(Trade.league == league)
    if status_ is not None:
        where.append(Trade.status == status_)
    if outcome_label is not None:
        where.append(Trade.outcome_label == outcome_label)
    if pnl_mode is not None:
        where.append(Trade.pnl_mode == pnl_mode)
    if date_from is not None:
        where.append(Trade.kickoff_at >= date_from)
    if date_to is not None:
        where.append(Trade.kickoff_at <= date_to)
    if pnl_min is not None:
        where.append(Trade.computed_pnl_eur >= pnl_min)
    if pnl_max is not None:
        where.append(Trade.computed_pnl_eur <= pnl_max)
    if tag:
        # All requested tags must be present (AND across tags).
        for t in tag:
            sub = (
                select(TradeTag.trade_id)
                .join(Tag, Tag.id == TradeTag.tag_id)
                .where(Tag.name == t)
            )
            where.append(Trade.id.in_(sub))
    if q:
        ts = func.to_tsvector(
            "simple",
            Trade.home_team + text("' '") + Trade.away_team + text("' '")
            + func.coalesce(Trade.notes_md, ""),
        )
        where.append(ts.op("@@")(func.plainto_tsquery("simple", q)))
    if kickoff_dow is not None:
        where.append(
            func.cast(func.extract("isodow", Trade.kickoff_at), Integer) - 1 == kickoff_dow
        )
    if kickoff_hour is not None:
        where.append(
            func.cast(func.extract("hour", Trade.kickoff_at), Integer) == kickoff_hour
        )

    where_clause = and_(*where) if where else True

    # Aggregates over the FILTERED set (closed trades only contribute to PnL stats).
    closed_filter = and_(where_clause, Trade.status == TradeStatus.CLOSED)
    agg_res = await db.execute(
        select(
            func.count(Trade.id).filter(closed_filter),
            func.coalesce(func.sum(Trade.computed_pnl_eur).filter(closed_filter), 0),
            func.coalesce(func.sum(Trade.stake_total).filter(closed_filter), 0),
            func.count(Trade.id).filter(
                and_(closed_filter, Trade.computed_pnl_eur > 0)
            ),
        )
        .where(where_clause)
    )
    n_closed, sum_pnl, sum_stake, n_wins = agg_res.one()

    sum_pnl_dec = Decimal(str(sum_pnl)) if sum_pnl is not None else ZERO
    sum_stake_dec = Decimal(str(sum_stake)) if sum_stake is not None else ZERO
    roi = (sum_pnl_dec / sum_stake_dec * HUNDRED) if sum_stake_dec > 0 else ZERO
    win_rate = (Decimal(n_wins) / Decimal(n_closed) * HUNDRED) if n_closed > 0 else ZERO

    # Total count (any status) for pagination.
    total_res = await db.execute(select(func.count(Trade.id)).where(where_clause))
    total = int(total_res.scalar_one())

    # Sorting
    sort_map = {
        "kickoff_at": Trade.kickoff_at.asc(),
        "-kickoff_at": Trade.kickoff_at.desc(),
        "pnl": Trade.computed_pnl_eur.asc(),
        "-pnl": Trade.computed_pnl_eur.desc(),
        "stake": Trade.stake_total.asc(),
        "-stake": Trade.stake_total.desc(),
    }
    order_by = sort_map[sort]

    rows = await db.execute(
        select(Trade)
        .options(selectinload(Trade.strategy), selectinload(Trade.tags))
        .where(where_clause)
        .order_by(order_by, Trade.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [_trade_to_out(t) for t in rows.scalars().all()]

    return TradeListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        aggregates=TradeAggregates(
            n_trades=int(n_closed),
            sum_pnl_eur=sum_pnl_dec.quantize(Decimal("0.01")),
            sum_stake_eur=sum_stake_dec.quantize(Decimal("0.01")),
            roi_pct=roi.quantize(Decimal("0.0001")),
            win_rate_pct=win_rate.quantize(Decimal("0.0001")),
        ),
    )


# Silence unused import warnings for casts that may show up later.
_ = (cast, Numeric, or_)
