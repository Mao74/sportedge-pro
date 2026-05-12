"""Filesystem watcher for the Obsidian vault (two_way sync mode).

When the trader edits a trade's notes inside Obsidian and saves, the watcher
re-imports the user-editable block back into the DB. Same path as
`ObsidianSyncService.import_changes`, just triggered automatically.

WSL2/DrvFs caveat
-----------------
When the host is Windows and the container runs under Docker Desktop with
the WSL2 backend, inotify events from a Windows-mounted volume (DrvFs path
like ``/c/Users/...`` or ``/mnt/c/...``) DO NOT propagate to the Linux
container. We detect that scenario via ``is_drvfs_path`` and switch
``watchfiles`` to polling mode (~2s) so updates still flow, at the cost
of slightly higher CPU.

The watcher is gated by ``AppSettings.obsidian_sync_mode == 'two_way'``
(and the integration being enabled). The lifespan reads the setting at
startup; a runtime change to sync_mode requires a backend restart.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from watchfiles import Change, awatch

from app.core.database import get_session_factory
from app.core.logging import get_logger
from app.services.obsidian.sync import ObsidianSyncService, get_or_create_settings

_log = get_logger("app.obsidian.watcher")


# ---------------------------------------------------------------------------
# DrvFs detection
# ---------------------------------------------------------------------------


_DRVFS_PREFIXES = ("/c/", "/d/", "/e/", "/f/", "/mnt/c/", "/mnt/d/", "/mnt/e/", "/mnt/f/")


def is_drvfs_path(path: str | Path) -> bool:
    """True if ``path`` looks like a Windows drive bind-mounted in WSL2.

    A heuristic, but good enough: any vault path under common DrvFs prefixes
    will trigger the polling fallback.
    """
    norm = str(path).replace("\\", "/").lower()
    return any(norm.startswith(p) or norm == p.rstrip("/") for p in _DRVFS_PREFIXES)


def _polling_kwargs(vault_path: Path) -> dict[str, object]:
    """Build the watchfiles kwargs adjusting for DrvFs."""
    if is_drvfs_path(vault_path):
        interval = float(os.environ.get("OBSIDIAN_WATCH_POLL_INTERVAL", "2.0"))
        _log.warning(
            "vault_path_is_drvfs_polling_fallback",
            vault=str(vault_path),
            poll_interval_s=interval,
        )
        return {"force_polling": True, "poll_delay_ms": int(interval * 1000)}
    return {}


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


# Debounce per file so an editor's atomic-save burst (write tmp → rename)
# doesn't trigger import twice.
_DEBOUNCE_SECONDS = 0.5


async def watch_loop() -> None:
    """Outer loop. Reads the current settings (and re-reads on each
    reconnect) so a backend restart picks up config changes.

    Exits silently when the integration is disabled or sync mode is not
    two_way; the supervisor (lifespan) is responsible for re-spawning on
    config changes if we add that capability later.
    """
    factory = get_session_factory()
    async with factory() as db:
        settings = await get_or_create_settings(db)
        if not settings.obsidian_enabled or settings.obsidian_sync_mode != "two_way":
            _log.info(
                "watcher_skipped",
                enabled=settings.obsidian_enabled,
                sync_mode=settings.obsidian_sync_mode,
            )
            return
        vault_path = Path(settings.obsidian_vault_path)

    if not vault_path.exists():
        _log.warning("vault_missing_skipping_watcher", vault=str(vault_path))
        return

    kwargs = _polling_kwargs(vault_path)
    _log.info("watcher_started", vault=str(vault_path), polling=bool(kwargs))

    debouncer: dict[str, asyncio.TimerHandle] = {}

    async def import_now() -> None:
        try:
            async with factory() as db:
                svc = ObsidianSyncService(vault_path, db)
                events = await svc.import_changes()
                if events:
                    _log.info("watcher_import_ran", n_events=len(events))
        except Exception as e:  # noqa: BLE001 — never let one bad import kill the watcher
            _log.error("watcher_import_failed", error=str(e), error_type=type(e).__name__)

    loop = asyncio.get_running_loop()

    try:
        async for changes in awatch(str(vault_path), **kwargs):  # type: ignore[arg-type]
            # We only care about *.md files inside Trades/.
            relevant = [
                p for change, p in changes
                if change in (Change.modified, Change.added)
                and p.endswith(".md")
                and "/Trades/" in p.replace("\\", "/")
            ]
            if not relevant:
                continue

            # Debounce by collapsing recent edits into a single import pass.
            key = "import"
            old = debouncer.get(key)
            if old is not None:
                old.cancel()
            debouncer[key] = loop.call_later(
                _DEBOUNCE_SECONDS,
                lambda: asyncio.create_task(import_now()),
            )
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001
        _log.error("watcher_crashed", error=str(e), error_type=type(e).__name__)
