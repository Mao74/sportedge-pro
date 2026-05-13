"""User-tunable preferences (single-row, lives on app_settings).

Multi-account split (migration 0007): per-trade defaults (commission, venue,
market_type) moved off app_settings onto each `Account` row. What's left
here is purely "which account is pre-selected on a new trade".
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class Preferences(BaseModel):
    default_account_id: uuid.UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class PreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_account_id: uuid.UUID | None = None
