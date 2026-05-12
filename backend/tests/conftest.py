"""Pytest fixtures.

Test isolation strategy:

- Each test runs against the live Postgres (same one the dev stack uses),
  but we TRUNCATE every table and re-seed the defaults (default user + two
  built-in strategies) before the test runs. This is fast (~50-80ms per
  test on the local DB) and avoids the complexity of nested transactions
  with async sessions and TestClient's event-loop juggling.
- Between tests we clear the cached async engine so the next request
  rebuilds it inside TestClient's freshly-spun event loop. This dodges the
  asyncpg "connection bound to a different event loop" trap.
- A user can be authenticated trivially via the ``client_with_auth`` fixture
  which performs a real login round-trip and sets the ``Authorization``
  header on the test client.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Iterator

# Disable the daily-snapshot scheduler in test runs. Must be set BEFORE
# settings are first read by any imported module.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("ENABLE_SCHEDULER", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core import database as db_mod
from app.core.config import get_settings
from app.core.security import hash_password
from app.main import create_app
from app.services.strategy_templates import all_templates

# Tables truncated in dependency-safe order (children before parents).
_TABLES_TO_TRUNCATE = [
    "trade_tags", "tags", "trades", "strategies", "users",
    "bankroll_snapshots", "daily_reflections", "whatif_scratch",
    "obsidian_conflicts", "app_settings",
]


async def _reset_db() -> None:
    """Truncate every domain table and re-seed the defaults."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(f"TRUNCATE {', '.join(_TABLES_TO_TRUNCATE)} RESTART IDENTITY CASCADE")
            )
            await conn.execute(
                text(
                    "INSERT INTO users (email, password_hash) VALUES (:email, :pw)"
                ),
                {
                    "email": settings.default_user_email,
                    "pw": hash_password(settings.default_user_password),
                },
            )
            for tpl in all_templates():
                await conn.execute(
                    text(
                        """
                        INSERT INTO strategies
                            (name, slug, kind, template_key, sport,
                             description, color_hex, is_active, field_schema)
                        VALUES
                            (:name, :slug, 'builtin', :template_key, 'football',
                             :description, :color_hex, true, CAST(:field_schema AS jsonb))
                        """
                    ),
                    {
                        "name": tpl.name,
                        "slug": tpl.slug,
                        "template_key": tpl.template_key,
                        "description": tpl.description,
                        "color_hex": tpl.color_hex,
                        "field_schema": json.dumps(tpl.field_schema),
                    },
                )
    finally:
        await engine.dispose()


@pytest.fixture(autouse=True)
def reset_db() -> Iterator[None]:
    asyncio.run(_reset_db())
    # Clear cached engine so the next request rebuilds it in the test's loop.
    db_mod._engine = None
    db_mod._session_factory = None
    yield
    db_mod._engine = None
    db_mod._session_factory = None


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    """Login as the seeded default user and return ready-to-use headers."""
    settings = get_settings()
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": settings.default_user_email, "password": settings.default_user_password},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client_with_auth(client: TestClient, auth_headers) -> TestClient:
    client.headers.update(auth_headers)
    return client
