"""User preferences API.

After migration 0007 the only setting living here is the default account
(pre-selected on the new-trade form). The other per-trade defaults
(commission, venue, market type) now live on each ``Account`` row.

Lives on the single-row ``app_settings`` table, alongside the Obsidian
config. Obsidian-specific fields stay in `/obsidian/*`; the rest is here.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, DbSession
from app.schemas.preferences import Preferences, PreferencesUpdate
from app.services.account_service import get_account
from app.services.obsidian.sync import get_or_create_settings

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("", response_model=Preferences)
async def get_preferences(_user: CurrentUser, db: DbSession) -> Preferences:
    s = await get_or_create_settings(db)
    return Preferences.model_validate(s)


@router.patch("", response_model=Preferences)
async def update_preferences(
    payload: PreferencesUpdate, _user: CurrentUser, db: DbSession
) -> Preferences:
    s = await get_or_create_settings(db)
    data = payload.model_dump(exclude_unset=True)
    if "default_account_id" in data:
        new_id = data["default_account_id"]
        if new_id is not None:
            acc = await get_account(db, new_id)
            if acc is None:
                raise HTTPException(
                    status_code=404, detail=f"account {new_id} not found"
                )
        s.default_account_id = new_id
    await db.commit()
    await db.refresh(s)
    return Preferences.model_validate(s)
