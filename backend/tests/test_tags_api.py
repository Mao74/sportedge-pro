"""Tags CRUD API integration tests."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


class TestTagsCrud:
    def test_list_empty(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.get("/api/v1/tags")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_returns_tag(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.post(
            "/api/v1/tags", json={"name": "high-xg", "color_hex": "#1DCC8C"}
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "high-xg"
        assert body["color_hex"] == "#1DCC8C"

    def test_create_duplicate_returns_409(self, client_with_auth: TestClient) -> None:
        client_with_auth.post("/api/v1/tags", json={"name": "live"})
        resp = client_with_auth.post("/api/v1/tags", json={"name": "live"})
        assert resp.status_code == 409
        assert resp.json()["title"] == "Conflict"

    def test_invalid_color_returns_422(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.post(
            "/api/v1/tags", json={"name": "bad", "color_hex": "not-a-color"}
        )
        assert resp.status_code == 422

    def test_patch_renames_tag(self, client_with_auth: TestClient) -> None:
        created = client_with_auth.post("/api/v1/tags", json={"name": "old-name"}).json()
        resp = client_with_auth.patch(
            f"/api/v1/tags/{created['id']}", json={"name": "new-name"}
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "new-name"

    def test_patch_rename_conflict_returns_409(self, client_with_auth: TestClient) -> None:
        client_with_auth.post("/api/v1/tags", json={"name": "alpha"})
        b = client_with_auth.post("/api/v1/tags", json={"name": "beta"}).json()
        resp = client_with_auth.patch(f"/api/v1/tags/{b['id']}", json={"name": "alpha"})
        assert resp.status_code == 409

    def test_patch_unknown_id_returns_404(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.patch(
            f"/api/v1/tags/{uuid.uuid4()}", json={"name": "x"}
        )
        assert resp.status_code == 404

    def test_delete_returns_204(self, client_with_auth: TestClient) -> None:
        created = client_with_auth.post("/api/v1/tags", json={"name": "doomed"}).json()
        resp = client_with_auth.delete(f"/api/v1/tags/{created['id']}")
        assert resp.status_code == 204

    def test_delete_unknown_returns_404(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.delete(f"/api/v1/tags/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_list_includes_usage_count(self, client_with_auth: TestClient) -> None:
        # Use a custom strategy with no required fields so the POST is minimal.
        s = client_with_auth.post(
            "/api/v1/strategies", json={"name": "Bare", "field_schema": {"fields": []}}
        ).json()
        body = {
            "strategy_id": s["id"],
            "home_team": "A", "away_team": "B", "league": "X",
            "kickoff_at": "2026-04-28T20:00:00+00:00",
            "stake_total": "100.00", "avg_odds": "2.50",
            "pnl_mode": "MANUAL", "manual_pnl_eur": "0.00",
            "tags": ["used-tag"],
        }
        resp = client_with_auth.post("/api/v1/trades", json=body)
        assert resp.status_code == 201, resp.text

        listing = client_with_auth.get("/api/v1/tags").json()
        assert len(listing) == 1
        assert listing[0]["name"] == "used-tag"
        assert listing[0]["n_trades"] == 1


class TestAuth:
    def test_list_requires_auth(self, client: TestClient) -> None:
        assert client.get("/api/v1/tags").status_code == 401
