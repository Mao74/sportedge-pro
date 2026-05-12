"""API v1 router aggregator."""

from fastapi import APIRouter

from app.api.v1 import (
    analytics,
    auth,
    bankroll,
    health,
    obsidian,
    preferences,
    strategies,
    tags,
    trades,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router)
api_router.include_router(strategies.router)
api_router.include_router(tags.router)
api_router.include_router(trades.router)
api_router.include_router(bankroll.router)
api_router.include_router(analytics.router)
api_router.include_router(obsidian.router)
api_router.include_router(preferences.router)
