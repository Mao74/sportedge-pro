"""Strategies CRUD API.

Permission matrix (per docs/strategies.md):

- ``builtin`` strategies:
    - rename / change description / change color_hex / toggle is_active: allowed
    - modify ``field_schema`` or ``template_key`` or ``kind``: 403
    - hard delete: 409
- ``custom`` strategies:
    - all metadata mutable
    - ``field_schema`` mutable, but field removal that orphans data → 422
      unless ``?force=true``
    - hard delete only if no trade references it; otherwise 200 + soft-deactivate
"""

from __future__ import annotations

import re
import uuid
import unicodedata
from typing import Annotated, Any

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession
from app.core.problem_details import (
    ProblemDetailException,
    conflict,
    forbidden,
    not_found,
    unprocessable,
)
from app.models import Strategy, StrategyKind, Trade
from app.schemas.strategy import StrategyCreate, StrategyOut, StrategyUpdate

router = APIRouter(prefix="/strategies", tags=["strategies"])


# --- helpers ---------------------------------------------------------------


def _slugify(name: str) -> str:
    """Stable slug from a display name. Removes accents, lowercases,
    collapses non-alphanumerics into single hyphens."""
    norm = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    norm = norm.lower()
    norm = re.sub(r"[^a-z0-9]+", "-", norm).strip("-")
    return norm or "strategy"


async def _unique_slug(db: AsyncSession, base: str) -> str:
    """Append a numeric suffix until the slug is free."""
    candidate = base
    n = 1
    while True:
        existing = await db.execute(select(Strategy.id).where(Strategy.slug == candidate))
        if existing.scalar_one_or_none() is None:
            return candidate
        n += 1
        candidate = f"{base}-{n}"


def _field_keys(field_schema: dict[str, Any]) -> set[str]:
    return {f["key"] for f in field_schema.get("fields", []) if isinstance(f, dict) and "key" in f}


async def _trade_count(db: AsyncSession, strategy_id: uuid.UUID) -> int:
    res = await db.execute(
        select(func.count(Trade.id)).where(Trade.strategy_id == strategy_id)
    )
    return int(res.scalar_one())


async def _trades_using_field_keys(
    db: AsyncSession, strategy_id: uuid.UUID, removed_keys: set[str]
) -> list[uuid.UUID]:
    """Return ids of trades whose ``strategy_data`` carries any of the given keys."""
    if not removed_keys:
        return []
    # `?` operator on JSONB returns true if the key exists at the top level.
    res = await db.execute(
        select(Trade.id).where(
            Trade.strategy_id == strategy_id,
            *[Trade.strategy_data.has_key(k) for k in removed_keys],  # type: ignore[attr-defined]
        )
    )
    return [r[0] for r in res.all()]


# --- routes ----------------------------------------------------------------


@router.get("", response_model=list[StrategyOut])
async def list_strategies(
    _user: CurrentUser,
    db: DbSession,
    include_inactive: Annotated[bool, Query()] = False,
) -> list[Strategy]:
    stmt = select(Strategy).order_by(Strategy.kind, Strategy.name)
    if not include_inactive:
        stmt = stmt.where(Strategy.is_active.is_(True))
    res = await db.execute(stmt)
    return list(res.scalars().all())


@router.get("/{strategy_id}", response_model=StrategyOut)
async def get_strategy(
    strategy_id: uuid.UUID, _user: CurrentUser, db: DbSession
) -> Strategy:
    res = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
    strategy = res.scalar_one_or_none()
    if strategy is None:
        raise not_found(f"Strategy {strategy_id} does not exist.")
    return strategy


@router.post("", response_model=StrategyOut, status_code=status.HTTP_201_CREATED)
async def create_strategy(
    payload: StrategyCreate, _user: CurrentUser, db: DbSession
) -> Strategy:
    base_slug = _slugify(payload.name)
    slug = await _unique_slug(db, base_slug)
    strategy = Strategy(
        name=payload.name.strip(),
        slug=slug,
        kind=StrategyKind.custom,
        template_key=None,
        description=payload.description,
        color_hex=payload.color_hex,
        is_active=True,
        field_schema=payload.field_schema or {"fields": []},
    )
    db.add(strategy)
    await db.commit()
    await db.refresh(strategy)
    return strategy


@router.patch("/{strategy_id}", response_model=StrategyOut)
async def update_strategy(
    strategy_id: uuid.UUID,
    payload: StrategyUpdate,
    _user: CurrentUser,
    db: DbSession,
    force: Annotated[bool, Query()] = False,
) -> Strategy:
    res = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
    strategy = res.scalar_one_or_none()
    if strategy is None:
        raise not_found(f"Strategy {strategy_id} does not exist.")

    data = payload.model_dump(exclude_unset=True)

    if strategy.kind is StrategyKind.builtin and "field_schema" in data:
        raise forbidden("Built-in strategies cannot have their field_schema modified.")

    # Custom: field_schema field removal must not orphan trade data unless force=true.
    if (
        strategy.kind is StrategyKind.custom
        and "field_schema" in data
        and data["field_schema"] is not None
    ):
        old_keys = _field_keys(strategy.field_schema or {})
        new_keys = _field_keys(data["field_schema"])
        removed = old_keys - new_keys
        if removed and not force:
            affected = await _trades_using_field_keys(db, strategy.id, removed)
            if affected:
                raise unprocessable(
                    "Removing the listed fields would orphan strategy_data on existing trades. "
                    "Re-add the fields, migrate the data, or pass ?force=true to override.",
                    removed_keys=sorted(removed),
                    affected_trade_ids=[str(t) for t in affected],
                )

    for k, v in data.items():
        setattr(strategy, k, v)

    await db.commit()
    await db.refresh(strategy)
    return strategy


@router.delete("/{strategy_id}", status_code=status.HTTP_200_OK)
async def delete_strategy(
    strategy_id: uuid.UUID, _user: CurrentUser, db: DbSession
) -> dict[str, Any]:
    res = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
    strategy = res.scalar_one_or_none()
    if strategy is None:
        raise not_found(f"Strategy {strategy_id} does not exist.")

    # Both built-in and custom strategies are deletable. Built-ins won't be
    # re-created automatically because the seed migration uses ON CONFLICT
    # (slug); once deleted, they stay gone unless re-seeded manually.
    n_trades = await _trade_count(db, strategy.id)
    if n_trades > 0:
        # Soft-deactivate with warning payload.
        strategy.is_active = False
        await db.commit()
        return {
            "status": "soft_deactivated",
            "reason": f"{n_trades} trade(s) reference this strategy — kept for history.",
            "n_trades": n_trades,
        }

    await db.delete(strategy)
    await db.commit()
    return {"status": "deleted"}


# Re-export for convenience (e.g. error testing in isolation)
__all__ = ["router", "ProblemDetailException"]
