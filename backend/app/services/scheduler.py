"""Lightweight in-process scheduler for daily bankroll snapshots.

Runs as an asyncio task spawned by the FastAPI lifespan. Sleeps until the
next 23:59 UTC, takes a snapshot, and loops. Cancellation on shutdown is
handled by the lifespan.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, time, timedelta

from app.core.database import get_session_factory
from app.core.logging import get_logger
from app.services.bankroll_service import take_snapshot

_log = get_logger("app.scheduler")

DAILY_SNAPSHOT_TIME = time(hour=23, minute=59, tzinfo=UTC)


def _seconds_until(target_time: time, now: datetime | None = None) -> float:
    base = now or datetime.now(UTC)
    target = base.replace(
        hour=target_time.hour, minute=target_time.minute, second=0, microsecond=0
    )
    if target <= base:
        target += timedelta(days=1)
    return (target - base).total_seconds()


async def _snapshot_once() -> None:
    factory = get_session_factory()
    async with factory() as db:
        snap = await take_snapshot(db, notes="daily auto-snapshot")
        await db.commit()
        _log.info(
            "snapshot_taken",
            balance_eur=str(snap.balance_eur),
            taken_at=snap.taken_at.isoformat(),
        )


async def daily_snapshot_loop() -> None:
    """Forever loop: sleep until DAILY_SNAPSHOT_TIME, snapshot, repeat.
    Logs and continues on errors so a single bad night doesn't kill scheduling.
    """
    while True:
        try:
            delay = _seconds_until(DAILY_SNAPSHOT_TIME)
            await asyncio.sleep(delay)
            await _snapshot_once()
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 — schedule must not die on a transient DB blip
            _log.error("snapshot_failed", error=str(e), error_type=type(e).__name__)
            await asyncio.sleep(60)
