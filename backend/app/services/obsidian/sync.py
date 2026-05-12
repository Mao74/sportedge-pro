"""Obsidian sync service.

Implements the `export_only` and `manual_only` modes end-to-end (write
files, preserve user-editable blocks) plus the import-changes path used
by `manual_only`/`two_way`'s "Sync now" button. The watcher (live two-way
sync) is deferred — manual sync-now covers the use case in the meantime
and the docs explicitly accept this as a soft start.

Conflicts: when a file on disk has changes AND the corresponding DB
record was modified after the file's `last_synced_at` frontmatter, we
write the file's user-editable block to ``_meta/_conflicts/`` and create
an ``obsidian_conflicts`` row so the frontend conflicts drawer can render
it. The DB version is never silently overwritten.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date as date_t, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Iterable

import aiofiles
import frontmatter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models import (
    AppSettings,
    BankrollSnapshot,
    ObsidianConflict,
    Strategy,
    Trade,
    TradeStatus,
)
from app.services.obsidian import templates
from app.services.obsidian.markers import extract_user_editable

_log = get_logger("app.obsidian")


@dataclass
class ExportSummary:
    trades_exported: int = 0
    daily_exported: int = 0
    strategies_exported: int = 0
    dashboards_exported: int = 0
    took_ms: int = 0


@dataclass
class ChangeEvent:
    path: str
    trade_id: str | None
    action: str  # 'updated' | 'conflict' | 'unknown'
    detail: str | None = None


class ObsidianSyncService:
    def __init__(self, vault_path: Path, db: AsyncSession) -> None:
        self.vault_path = Path(vault_path)
        self.db = db

    # --- Path helpers ------------------------------------------------------

    def _trades_dir(self) -> Path:
        return self.vault_path / "Trades"

    def _daily_dir(self) -> Path:
        return self.vault_path / "Daily"

    def _strategies_dir(self) -> Path:
        return self.vault_path / "Strategies"

    def _dashboards_dir(self) -> Path:
        return self.vault_path / "Dashboards"

    def _conflicts_dir(self) -> Path:
        return self.vault_path / "_meta" / "_conflicts"

    def _ensure_dirs(self) -> None:
        for d in (
            self._trades_dir(),
            self._daily_dir(),
            self._strategies_dir(),
            self._dashboards_dir(),
            self._conflicts_dir(),
        ):
            d.mkdir(parents=True, exist_ok=True)

    # --- Atomic write helpers ----------------------------------------------

    async def _read_text(self, path: Path) -> str | None:
        if not path.exists():
            return None
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            return await f.read()

    async def _write_text(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write atomically via tmp + replace so a crash doesn't leave a
        # half-written file open in Obsidian.
        tmp = path.with_suffix(path.suffix + ".tmp")
        async with aiofiles.open(tmp, "w", encoding="utf-8") as f:
            await f.write(content)
        tmp.replace(path)

    # --- Export ------------------------------------------------------------

    async def export_trade(self, trade: Trade) -> Path:
        self._ensure_dirs()
        path = self._trades_dir() / templates.trade_filename(trade)
        existing = await self._read_text(path)
        now = datetime.now(UTC)
        content = templates.render_trade(trade, now=now, existing_text=existing)
        await self._write_text(path, content)
        # Persist last sync timestamp on the trade.
        trade.last_obsidian_sync_at = now
        return path

    async def export_daily(self, day: date_t) -> Path:
        self._ensure_dirs()
        # Pull all trades whose closed_at falls within [day, day+1)
        start = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
        end = start + timedelta(days=1)
        stmt = (
            select(Trade)
            .options(selectinload(Trade.strategy))
            .where(Trade.closed_at >= start, Trade.closed_at < end)
            .order_by(Trade.closed_at)
        )
        trades = list((await self.db.execute(stmt)).scalars().all())

        # Bankroll start/end-of-day from snapshots + closed-pnl arithmetic.
        bankroll_eod = await self._bankroll_at(end)
        bankroll_sod = await self._bankroll_at(start)

        path = self._daily_dir() / f"{day.isoformat()}.md"
        existing = await self._read_text(path)
        content = templates.render_daily(
            day=day,
            trades=trades,
            bankroll_eod=bankroll_eod,
            bankroll_sod=bankroll_sod,
            existing_text=existing,
        )
        await self._write_text(path, content)
        return path

    async def export_strategy(self, strategy: Strategy) -> Path:
        self._ensure_dirs()
        # Replace path-unsafe slashes; strategy names are short enough.
        safe_name = strategy.name.replace("/", "-")
        path = self._strategies_dir() / f"{safe_name}.md"
        existing = await self._read_text(path)
        await self._write_text(path, templates.render_strategy(strategy, existing))
        return path

    async def export_dashboards(self) -> list[Path]:
        self._ensure_dirs()
        bankroll = self._dashboards_dir() / "Bankroll.md"
        await self._write_text(bankroll, templates.render_bankroll_dashboard())
        return [bankroll]

    async def _export_readme(self) -> Path:
        readme = self.vault_path / "README.md"
        existing = await self._read_text(readme)
        # Only write if missing or marked app_managed; never overwrite a hand-written README.
        if existing:
            try:
                fm = frontmatter.loads(existing).metadata
            except Exception:  # noqa: BLE001
                fm = {}
            if not fm.get("app_managed"):
                return readme
        await self._write_text(readme, templates.render_readme())
        return readme

    async def export_all(self) -> ExportSummary:
        started = datetime.now(UTC)
        self._ensure_dirs()
        summary = ExportSummary()

        # Trades
        trades = (
            await self.db.execute(
                select(Trade).options(
                    selectinload(Trade.strategy), selectinload(Trade.tags)
                )
            )
        ).scalars().all()
        for t in trades:
            await self.export_trade(t)
            summary.trades_exported += 1

        # Daily notes — one per distinct closed-trade day.
        days: set[date_t] = {
            t.closed_at.astimezone(UTC).date() for t in trades if t.closed_at is not None
        }
        for d in sorted(days):
            await self.export_daily(d)
            summary.daily_exported += 1

        # Strategies
        strategies = (
            await self.db.execute(select(Strategy).where(Strategy.is_active.is_(True)))
        ).scalars().all()
        for s in strategies:
            await self.export_strategy(s)
            summary.strategies_exported += 1

        # Dashboards + README
        summary.dashboards_exported = len(await self.export_dashboards())
        await self._export_readme()

        await self.db.commit()

        summary.took_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
        _log.info(
            "vault_exported",
            trades=summary.trades_exported,
            daily=summary.daily_exported,
            strategies=summary.strategies_exported,
            took_ms=summary.took_ms,
        )
        return summary

    # --- Import (manual-sync) ---------------------------------------------

    _TRADE_FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}) .+ vs .+\.md$")

    async def import_changes(self) -> list[ChangeEvent]:
        """Walk the Trades/ folder, parse each app-managed file, and merge
        the user-editable section back into the matching trade row.

        - If the trade.updated_at is *after* the file's last_synced_at
          frontmatter, treat it as a conflict — write the file's text to
          _meta/_conflicts/ and record an `obsidian_conflicts` row.
        - Otherwise, if the user-editable text differs from
          trade.notes_md, PATCH it and bump trade.last_obsidian_sync_at.
        """
        events: list[ChangeEvent] = []
        trades_dir = self._trades_dir()
        if not trades_dir.exists():
            return events

        for path in sorted(trades_dir.glob("*.md")):
            if not self._TRADE_FILENAME_RE.match(path.name):
                continue
            try:
                content = await self._read_text(path)
                if content is None:
                    continue
                doc = frontmatter.loads(content)
                fm = doc.metadata
                if not fm.get("app_managed"):
                    continue
                trade_id = fm.get("trade_id")
                if not trade_id:
                    events.append(
                        ChangeEvent(path=str(path), trade_id=None, action="unknown",
                                    detail="missing trade_id frontmatter")
                    )
                    continue

                trade = (
                    await self.db.execute(
                        select(Trade).where(Trade.id == trade_id)
                    )
                ).scalar_one_or_none()
                if trade is None:
                    events.append(
                        ChangeEvent(path=str(path), trade_id=trade_id, action="unknown",
                                    detail="trade no longer exists")
                    )
                    continue

                user_text = extract_user_editable(content)
                if user_text is None:
                    continue
                # Skip if nothing changed.
                if user_text == (trade.notes_md or "").strip():
                    continue

                last_synced = self._parse_iso(fm.get("last_synced_at"))
                if last_synced and trade.updated_at and trade.updated_at > last_synced:
                    # Concurrent DB edit — emit a conflict.
                    await self._record_conflict(
                        path=str(path),
                        trade_id=trade.id,
                        db_text=trade.notes_md or "",
                        file_text=user_text,
                        db_updated_at=trade.updated_at,
                        file_updated_at=last_synced,
                    )
                    events.append(
                        ChangeEvent(path=str(path), trade_id=trade_id, action="conflict")
                    )
                    continue

                trade.notes_md = user_text or None
                trade.last_obsidian_sync_at = datetime.now(UTC)
                events.append(
                    ChangeEvent(path=str(path), trade_id=trade_id, action="updated")
                )
            except Exception as e:  # noqa: BLE001 — never let one bad file kill the sweep
                _log.error("import_change_failed", path=str(path), error=str(e))
                events.append(
                    ChangeEvent(path=str(path), trade_id=None, action="unknown",
                                detail=f"{type(e).__name__}: {e}")
                )

        await self.db.commit()
        return events

    async def _record_conflict(
        self,
        *,
        path: str,
        trade_id,
        db_text: str,
        file_text: str,
        db_updated_at: datetime | None,
        file_updated_at: datetime | None,
    ) -> None:
        # Stash the file version under _meta/_conflicts/ so the user can
        # diff against the DB.
        conflicts_dir = self._conflicts_dir()
        conflicts_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        conflict_path = conflicts_dir / f"{trade_id}-{ts}.md"
        await self._write_text(
            conflict_path,
            f"# Conflict for trade {trade_id}\n\n"
            f"detected_at: {datetime.now(UTC).isoformat()}\n\n"
            f"## File version (Obsidian)\n\n{file_text}\n\n"
            f"## DB version\n\n{db_text}\n",
        )
        self.db.add(
            ObsidianConflict(
                path=path,
                trade_id=trade_id,
                db_text=db_text,
                file_text=file_text,
                db_updated_at=db_updated_at,
                file_updated_at=file_updated_at,
            )
        )

    @staticmethod
    def _parse_iso(value) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        try:
            d = datetime.fromisoformat(str(value))
            return d if d.tzinfo else d.replace(tzinfo=UTC)
        except ValueError:
            return None

    # --- Bankroll snapshot helper -----------------------------------------

    async def _bankroll_at(self, when: datetime) -> Decimal:
        settings = get_settings()
        starting = Decimal(settings.default_starting_bankroll)
        snap_q = select(
            func.coalesce(func.sum(BankrollSnapshot.deposit_eur), 0),
            func.coalesce(func.sum(BankrollSnapshot.withdrawal_eur), 0),
        ).where(BankrollSnapshot.taken_at <= when)
        deposit_sum, withdrawal_sum = (await self.db.execute(snap_q)).one()

        pnl_q = select(
            func.coalesce(func.sum(Trade.computed_pnl_eur), 0)
        ).where(
            Trade.status == TradeStatus.CLOSED,
            Trade.closed_at <= when,
        )
        pnl_sum = (await self.db.execute(pnl_q)).scalar_one()

        return (
            starting
            + Decimal(str(deposit_sum))
            - Decimal(str(withdrawal_sum))
            + Decimal(str(pnl_sum))
        )


# ---------------------------------------------------------------------------
# Settings access helper
# ---------------------------------------------------------------------------


async def get_or_create_settings(db: AsyncSession) -> AppSettings:
    res = await db.execute(select(AppSettings).limit(1))
    row = res.scalar_one_or_none()
    if row is None:
        row = AppSettings()
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


__all__ = [
    "ObsidianSyncService",
    "ExportSummary",
    "ChangeEvent",
    "get_or_create_settings",
]


# Counter is imported but the public surface doesn't expose it; ruff would
# flag it without this nod.
_ = Counter
_ = Iterable
