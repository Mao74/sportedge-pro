"""Obsidian export queue.

Trade lifecycle hooks (POST/PATCH/DELETE) call ``enqueue_trade(id)``; a
single background worker drains the queue and exports each trade. Pending
duplicates collapse so a flurry of edits to the same trade only triggers
one re-export.

Disabled in tests via the existing `enable_scheduler=False` flag (the
worker is started by the FastAPI lifespan only when scheduler is on AND
Obsidian is enabled).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date as date_t, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_session_factory
from app.core.logging import get_logger
from app.models import AppSettings, Trade
from app.services.obsidian.sync import ObsidianSyncService, get_or_create_settings

_log = get_logger("app.obsidian.queue")

_pending_trades: set[uuid.UUID] = set()
_pending_dailies: set[date_t] = set()
_lock = asyncio.Lock()
_signal: asyncio.Event | None = None


def _get_signal() -> asyncio.Event:
    global _signal
    if _signal is None:
        _signal = asyncio.Event()
    return _signal


async def enqueue_trade(trade_id: uuid.UUID, *, day: date_t | None = None) -> None:
    """Schedule a trade re-export. Coalesces duplicates."""
    async with _lock:
        _pending_trades.add(trade_id)
        if day is not None:
            _pending_dailies.add(day)
    _get_signal().set()


async def _process_one() -> None:
    async with _lock:
        if not _pending_trades and not _pending_dailies:
            return
        trades = list(_pending_trades)
        dailies = list(_pending_dailies)
        _pending_trades.clear()
        _pending_dailies.clear()

    factory = get_session_factory()
    async with factory() as db:
        settings: AppSettings = await get_or_create_settings(db)
        if not settings.obsidian_enabled:
            return
        svc = ObsidianSyncService(Path(settings.obsidian_vault_path), db)
        for trade_id in trades:
            trade = (
                await db.execute(
                    select(Trade)
                    .options(
                        selectinload(Trade.strategy),
                        selectinload(Trade.account),
                        selectinload(Trade.tags),
                    )
                    .where(Trade.id == trade_id)
                )
            ).scalar_one_or_none()
            if trade is None:
                # Deleted trade — best-effort: nothing to write, the file
                # stays in the vault but Obsidian shows it as orphaned.
                # Cleanup is a follow-up enhancement.
                continue
            try:
                await svc.export_trade(trade)
            except Exception as e:  # noqa: BLE001
                _log.error("export_trade_failed", trade_id=str(trade_id), error=str(e))
        for d in dailies:
            try:
                await svc.export_daily(d)
            except Exception as e:  # noqa: BLE001
                _log.error("export_daily_failed", day=d.isoformat(), error=str(e))
        try:
            await svc.export_dashboards()
        except Exception as e:  # noqa: BLE001
            _log.error("export_dashboards_failed", error=str(e))
        await db.commit()


async def queue_loop() -> None:
    """Main worker loop. Wakes on the signal, drains the queue, sleeps."""
    sig = _get_signal()
    while True:
        try:
            await sig.wait()
            sig.clear()
            await _process_one()
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 — keep the worker alive
            _log.error("queue_loop_failure", error=str(e), error_type=type(e).__name__)
            await asyncio.sleep(2)


def kickoff_day(when: datetime | None) -> date_t | None:
    if when is None:
        return None
    return when.date()
