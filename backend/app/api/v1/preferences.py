"""User preferences API: trader-tunable defaults (commission, venue, market type).

Lives on the single-row ``app_settings`` table, alongside the Obsidian
config. Obsidian-specific fields stay in `/obsidian/*`; the rest is here.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.preferences import Preferences, PreferencesUpdate
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
    if "default_commission_pct" in data and data["default_commission_pct"] is not None:
        s.default_commission_pct = data["default_commission_pct"]
    if "betting_exchange" in data and data["betting_exchange"]:
        s.betting_exchange = data["betting_exchange"].strip().lower()
    if "default_market_type" in data and data["default_market_type"] is not None:
        s.default_market_type = data["default_market_type"]
    await db.commit()
    await db.refresh(s)
    return Preferences.model_validate(s)
