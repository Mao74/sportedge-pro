"""Obsidian config + status schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SyncMode = Literal["export_only", "two_way", "manual_only"]
TemplateSet = Literal["complete", "minimal", "tactical"]


class ObsidianStatus(BaseModel):
    enabled: bool
    vault_path: str
    sync_mode: SyncMode
    template_set: TemplateSet
    last_sync_at: datetime | None
    last_error: str | None
    conflict_count: int


class ObsidianConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    vault_path: str | None = Field(default=None, max_length=512)
    sync_mode: SyncMode | None = None
    template_set: TemplateSet | None = None


class ExportSummary(BaseModel):
    trades_exported: int
    daily_exported: int
    strategies_exported: int
    dashboards_exported: int
    took_ms: int


class ChangeEvent(BaseModel):
    path: str
    trade_id: str | None
    action: Literal["updated", "conflict", "unknown"]
    detail: str | None = None


class ConflictOut(BaseModel):
    id: uuid.UUID
    path: str
    trade_id: uuid.UUID | None
    detected_at: datetime
    db_updated_at: datetime | None
    file_updated_at: datetime | None
    db_text: str | None
    file_text: str | None

    model_config = ConfigDict(from_attributes=True)


class ConflictResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolution: Literal["keep_db", "keep_file", "merged"]
    merged_text: str | None = None
