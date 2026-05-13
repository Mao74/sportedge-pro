"""Preferences + bankroll snapshots-list integration tests."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient


class TestPreferences:
    def test_get_defaults(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.get("/api/v1/preferences")
        assert resp.status_code == 200
        body = resp.json()
        # Conftest seeds Betfair and points default_account_id at it.
        assert body["default_account_id"] is not None

    def test_patch_default_account_id(self, client_with_auth: TestClient) -> None:
        # Create a second account, then move the default onto it.
        created = client_with_auth.post(
            "/api/v1/accounts",
            json={
                "name": "Smarkets",
                "venue": "smarkets",
                "market_type": "exchange",
                "commission_pct": "2.00",
                "opening_balance": "500.00",
            },
        ).json()
        resp = client_with_auth.patch(
            "/api/v1/preferences",
            json={"default_account_id": created["id"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["default_account_id"] == created["id"]

    def test_patch_clear_default_account(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.patch(
            "/api/v1/preferences", json={"default_account_id": None}
        )
        assert resp.status_code == 200
        assert resp.json()["default_account_id"] is None

    def test_patch_unknown_field_rejected(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.patch(
            "/api/v1/preferences", json={"default_commission_pct": "2.00"}
        )
        # extra="forbid" on PreferencesUpdate
        assert resp.status_code == 422

    def test_get_requires_auth(self, client: TestClient) -> None:
        assert client.get("/api/v1/preferences").status_code == 401


class TestBankrollSnapshots:
    def test_list_empty(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.get("/api/v1/bankroll/snapshots")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_most_recent_first(self, client_with_auth: TestClient) -> None:
        client_with_auth.post(
            "/api/v1/bankroll/adjust",
            json={"amount_eur": "50.00", "kind": "deposit", "notes": "initial top-up"},
        )
        client_with_auth.post(
            "/api/v1/bankroll/adjust",
            json={"amount_eur": "20.00", "kind": "withdrawal", "notes": "cash out"},
        )
        body = client_with_auth.get(
            "/api/v1/bankroll/snapshots", params={"limit": 5}
        ).json()
        assert len(body) == 2
        # Newest first.
        assert Decimal(body[0]["withdrawal_eur"]) == Decimal("20.00")
        assert Decimal(body[1]["deposit_eur"]) == Decimal("50.00")

    def test_list_respects_limit(self, client_with_auth: TestClient) -> None:
        for i in range(15):
            client_with_auth.post(
                "/api/v1/bankroll/adjust",
                json={"amount_eur": "10.00", "kind": "deposit", "notes": f"snap {i}"},
            )
        ten = client_with_auth.get(
            "/api/v1/bankroll/snapshots", params={"limit": 10}
        ).json()
        assert len(ten) == 10
