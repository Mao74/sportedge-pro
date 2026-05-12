"""Obsidian API: status, config, export-all, sync-now, conflicts, resolve."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.core.problem_details import bad_request, not_found, unprocessable
from app.models import ObsidianConflict, Trade
from app.schemas.obsidian import (
    ChangeEvent as ChangeEventSchema,
    ConflictOut,
    ConflictResolveRequest,
    ExportSummary as ExportSummarySchema,
    ObsidianConfigUpdate,
    ObsidianStatus,
)
from app.services.obsidian.sync import ObsidianSyncService, get_or_create_settings

router = APIRouter(prefix="/obsidian", tags=["obsidian"])


def _vault_path(p: str) -> Path:
    return Path(p)


@router.get("/status", response_model=ObsidianStatus)
async def get_status(_user: CurrentUser, db: DbSession) -> ObsidianStatus:
    s = await get_or_create_settings(db)
    n_conflicts = (
        await db.execute(
            select(func.count(ObsidianConflict.id)).where(
                ObsidianConflict.resolved_at.is_(None)
            )
        )
    ).scalar_one()
    return ObsidianStatus(
        enabled=s.obsidian_enabled,
        vault_path=s.obsidian_vault_path,
        sync_mode=s.obsidian_sync_mode,  # type: ignore[arg-type]
        template_set=s.obsidian_template_set,  # type: ignore[arg-type]
        last_sync_at=s.obsidian_last_sync_at,
        last_error=s.obsidian_last_error,
        conflict_count=int(n_conflicts),
    )


@router.patch("/config", response_model=ObsidianStatus)
async def update_config(
    payload: ObsidianConfigUpdate, _user: CurrentUser, db: DbSession
) -> ObsidianStatus:
    s = await get_or_create_settings(db)
    data = payload.model_dump(exclude_unset=True)
    if "enabled" in data:
        s.obsidian_enabled = bool(data["enabled"])
    if "vault_path" in data and data["vault_path"]:
        s.obsidian_vault_path = data["vault_path"]
    if "sync_mode" in data and data["sync_mode"]:
        s.obsidian_sync_mode = data["sync_mode"]
    if "template_set" in data and data["template_set"]:
        s.obsidian_template_set = data["template_set"]
    await db.commit()
    return await get_status(_user, db)


@router.post("/export-all", response_model=ExportSummarySchema)
async def export_all(_user: CurrentUser, db: DbSession) -> ExportSummarySchema:
    s = await get_or_create_settings(db)
    if not s.obsidian_enabled:
        raise bad_request("Obsidian integration is disabled. Toggle it on first.")
    vault = _vault_path(s.obsidian_vault_path)
    try:
        vault.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise unprocessable(
            f"Vault path is not writable: {e}", vault_path=str(vault)
        ) from e

    svc = ObsidianSyncService(vault, db)
    try:
        summary = await svc.export_all()
    except Exception as e:  # noqa: BLE001 — surface as last_error on settings
        s.obsidian_last_error = f"{type(e).__name__}: {e}"
        await db.commit()
        raise

    s.obsidian_last_sync_at = datetime.now(UTC)
    s.obsidian_last_error = None
    await db.commit()
    return ExportSummarySchema(**summary.__dict__)


@router.post("/sync-now", response_model=list[ChangeEventSchema])
async def sync_now(_user: CurrentUser, db: DbSession) -> list[ChangeEventSchema]:
    s = await get_or_create_settings(db)
    if not s.obsidian_enabled:
        raise bad_request("Obsidian integration is disabled. Toggle it on first.")
    if s.obsidian_sync_mode == "export_only":
        raise bad_request("sync_mode=export_only does not import changes.")
    vault = _vault_path(s.obsidian_vault_path)
    svc = ObsidianSyncService(vault, db)
    events = await svc.import_changes()
    s.obsidian_last_sync_at = datetime.now(UTC)
    await db.commit()
    return [ChangeEventSchema(**e.__dict__) for e in events]


@router.get("/conflicts", response_model=list[ConflictOut])
async def list_conflicts(_user: CurrentUser, db: DbSession) -> list[ObsidianConflict]:
    res = await db.execute(
        select(ObsidianConflict)
        .where(ObsidianConflict.resolved_at.is_(None))
        .order_by(ObsidianConflict.detected_at.desc())
    )
    return list(res.scalars().all())


@router.post("/conflicts/{conflict_id}/resolve", response_model=ConflictOut)
async def resolve_conflict(
    conflict_id: uuid.UUID,
    payload: ConflictResolveRequest,
    _user: CurrentUser,
    db: DbSession,
) -> ObsidianConflict:
    conflict = (
        await db.execute(
            select(ObsidianConflict).where(ObsidianConflict.id == conflict_id)
        )
    ).scalar_one_or_none()
    if conflict is None:
        raise not_found(f"Conflict {conflict_id} does not exist.")
    if conflict.resolved_at is not None:
        raise bad_request("Conflict already resolved.")

    if payload.resolution == "keep_db":
        # Nothing to write; the file will be regenerated on the next export.
        pass
    elif payload.resolution == "keep_file":
        if conflict.trade_id and conflict.file_text is not None:
            trade = (
                await db.execute(select(Trade).where(Trade.id == conflict.trade_id))
            ).scalar_one_or_none()
            if trade:
                trade.notes_md = conflict.file_text or None
    elif payload.resolution == "merged":
        if not payload.merged_text:
            raise unprocessable("Resolution 'merged' requires merged_text.")
        if conflict.trade_id:
            trade = (
                await db.execute(select(Trade).where(Trade.id == conflict.trade_id))
            ).scalar_one_or_none()
            if trade:
                trade.notes_md = payload.merged_text or None

    conflict.resolved_at = datetime.now(UTC)
    conflict.resolution = payload.resolution
    await db.commit()
    return conflict
