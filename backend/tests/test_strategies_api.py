"""Strategies CRUD API tests — covers the full permission matrix."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


class TestList:
    def test_list_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/v1/strategies")
        assert resp.status_code == 401

    def test_list_returns_two_builtins(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.get("/api/v1/strategies")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        slugs = {s["slug"] for s in body}
        assert slugs == {"magic-cs", "draw-hunter"}
        for s in body:
            assert s["kind"] == "builtin"
            assert s["template_key"] in {"magic_cs_v3", "draw_hunter_s4"}

    def test_list_includes_inactive_when_flag_set(self, client_with_auth: TestClient) -> None:
        builtins = client_with_auth.get("/api/v1/strategies").json()
        sid = builtins[0]["id"]
        client_with_auth.patch(f"/api/v1/strategies/{sid}", json={"is_active": False})

        active_only = client_with_auth.get("/api/v1/strategies").json()
        assert len(active_only) == 1
        with_inactive = client_with_auth.get(
            "/api/v1/strategies", params={"include_inactive": True}
        ).json()
        assert len(with_inactive) == 2


class TestCreateCustom:
    def test_create_minimal(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.post(
            "/api/v1/strategies",
            json={"name": "Value 1X2", "color_hex": "#FFB547"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["kind"] == "custom"
        assert body["template_key"] is None
        assert body["slug"] == "value-1x2"
        assert body["is_active"] is True

    def test_create_validates_field_schema(self, client_with_auth: TestClient) -> None:
        # Missing 'options' on a select field → 422.
        resp = client_with_auth.post(
            "/api/v1/strategies",
            json={
                "name": "Bad Schema",
                "field_schema": {"fields": [
                    {"key": "selection", "label": "Selection", "type": "select"}
                ]},
            },
        )
        assert resp.status_code == 422

    def test_create_rejects_duplicate_keys(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.post(
            "/api/v1/strategies",
            json={
                "name": "Dup Keys",
                "field_schema": {"fields": [
                    {"key": "k1", "label": "K1", "type": "text"},
                    {"key": "k1", "label": "K1 again", "type": "number"},
                ]},
            },
        )
        assert resp.status_code == 422

    def test_create_with_full_field_schema(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.post(
            "/api/v1/strategies",
            json={
                "name": "Custom 1",
                "color_hex": "#4DA3FF",
                "field_schema": {
                    "fields": [
                        {"key": "selection", "label": "Selection", "type": "select",
                         "options": ["1", "X", "2"], "required": True},
                        {"key": "edge", "label": "Edge", "type": "computed",
                         "formula": "(prob * odds - 1) * 100"},
                    ]
                },
            },
        )
        assert resp.status_code == 201, resp.text

    def test_create_slug_collision_appends_suffix(self, client_with_auth: TestClient) -> None:
        # Reuse a name that slugifies to "magic-cs" (already used by the built-in).
        resp = client_with_auth.post(
            "/api/v1/strategies",
            json={"name": "Magic CS"},
        )
        assert resp.status_code == 201
        # New slug should NOT clobber the built-in.
        new_slug = resp.json()["slug"]
        assert new_slug != "magic-cs"
        assert new_slug.startswith("magic-cs")

    def test_invalid_color_hex_rejected(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.post(
            "/api/v1/strategies",
            json={"name": "Bad Color", "color_hex": "not-a-color"},
        )
        assert resp.status_code == 422


class TestUpdateBuiltin:
    """Built-in permission matrix."""

    def _builtin_id(self, client: TestClient) -> str:
        items = client.get("/api/v1/strategies").json()
        return next(s["id"] for s in items if s["template_key"] == "magic_cs_v3")

    def test_can_rename_builtin(self, client_with_auth: TestClient) -> None:
        sid = self._builtin_id(client_with_auth)
        resp = client_with_auth.patch(
            f"/api/v1/strategies/{sid}", json={"name": "Magic CS (rinominato)"}
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Magic CS (rinominato)"

    def test_can_change_color_and_description(self, client_with_auth: TestClient) -> None:
        sid = self._builtin_id(client_with_auth)
        resp = client_with_auth.patch(
            f"/api/v1/strategies/{sid}",
            json={"color_hex": "#1DCC8C", "description": "new desc"},
        )
        assert resp.status_code == 200
        assert resp.json()["color_hex"] == "#1DCC8C"
        assert resp.json()["description"] == "new desc"

    def test_can_deactivate_builtin(self, client_with_auth: TestClient) -> None:
        sid = self._builtin_id(client_with_auth)
        resp = client_with_auth.patch(f"/api/v1/strategies/{sid}", json={"is_active": False})
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_cannot_modify_field_schema_on_builtin(self, client_with_auth: TestClient) -> None:
        sid = self._builtin_id(client_with_auth)
        resp = client_with_auth.patch(
            f"/api/v1/strategies/{sid}",
            json={"field_schema": {"fields": []}},
        )
        assert resp.status_code == 403
        body = resp.json()
        assert body["title"] == "Forbidden"

    def test_can_delete_builtin_when_no_trades(self, client_with_auth: TestClient) -> None:
        # Built-ins are now deletable (single-user app — the trader chooses
        # which playbooks live in their workspace).
        sid = self._builtin_id(client_with_auth)
        resp = client_with_auth.delete(f"/api/v1/strategies/{sid}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"
        # Confirm gone
        assert client_with_auth.get(f"/api/v1/strategies/{sid}").status_code == 404

    def test_delete_builtin_with_trades_soft_deactivates(
        self, client_with_auth: TestClient
    ) -> None:
        sid = self._builtin_id(client_with_auth)
        # Use minimal strategy_data; the Magic CS schema requires fields we
        # don't care about for this delete-protection check, so post to a
        # dedicated bare strategy that we then attempt to delete via builtin.
        # Simpler: directly attach a trade to the builtin with minimal data.
        # The builtin's `field_schema` requires cs_selected/tier; satisfy them.
        body = {
            "strategy_id": sid,
            "home_team": "A", "away_team": "B", "league": "X",
            "kickoff_at": "2026-04-28T20:00:00+00:00",
            "stake_total": "100.00", "avg_odds": "2.50",
            "pnl_mode": "MANUAL", "manual_pnl_eur": "0.00",
            "strategy_data": {"cs_selected": ["1-0"], "tier": "1-CS"},
        }
        post = client_with_auth.post("/api/v1/trades", json=body)
        assert post.status_code == 201, post.text
        resp = client_with_auth.delete(f"/api/v1/strategies/{sid}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "soft_deactivated"


class TestUpdateCustom:
    def _make_custom(self, client: TestClient, **kwargs) -> dict:
        payload = {"name": "Custom A"} | kwargs
        resp = client.post("/api/v1/strategies", json=payload)
        assert resp.status_code == 201
        return resp.json()

    def test_can_modify_field_schema_when_no_trades_reference(
        self, client_with_auth: TestClient
    ) -> None:
        s = self._make_custom(
            client_with_auth,
            field_schema={"fields": [
                {"key": "k1", "label": "K1", "type": "text"},
            ]},
        )
        resp = client_with_auth.patch(
            f"/api/v1/strategies/{s['id']}",
            json={"field_schema": {"fields": [
                {"key": "k1", "label": "K1", "type": "text"},
                {"key": "k2", "label": "K2", "type": "number"},
            ]}},
        )
        assert resp.status_code == 200
        assert len(resp.json()["field_schema"]["fields"]) == 2


class TestDeleteCustom:
    def test_hard_delete_when_no_trades(self, client_with_auth: TestClient) -> None:
        created = client_with_auth.post(
            "/api/v1/strategies", json={"name": "Toss it"}
        ).json()
        resp = client_with_auth.delete(f"/api/v1/strategies/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

        # Confirm gone
        get_resp = client_with_auth.get(f"/api/v1/strategies/{created['id']}")
        assert get_resp.status_code == 404


class TestGetSingle:
    def test_get_unknown_id_404(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.get(f"/api/v1/strategies/{uuid.uuid4()}")
        assert resp.status_code == 404
