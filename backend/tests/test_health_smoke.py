"""Smoke test for the bootstrap step. The full health test (with a real DB)
arrives once Alembic and the test container are wired in step 2."""

from __future__ import annotations


def test_app_factory_builds_without_error(app) -> None:
    assert app.title == "SportEdge Pro API"
    routes = {r.path for r in app.routes}
    assert "/api/v1/health" in routes


def test_openapi_schema_published(client) -> None:
    resp = client.get("/api/v1/openapi.json")
    assert resp.status_code == 200
    body = resp.json()
    assert body["info"]["title"] == "SportEdge Pro API"
    assert "/api/v1/health" in body["paths"]
