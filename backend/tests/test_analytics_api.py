"""Analytics API integration tests."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient


def _bare_strategy(client: TestClient, name: str = "Bare") -> dict:
    return client.post(
        "/api/v1/strategies", json={"name": name, "field_schema": {"fields": []}}
    ).json()


def _post(
    client: TestClient, sid: str, *, pnl: str, kickoff: str, status: str = "CLOSED",
    league: str = "Serie A", outcome: str = "WIN",
) -> dict:
    body = {
        "strategy_id": sid,
        "home_team": "A", "away_team": "B", "league": league,
        "kickoff_at": kickoff,
        "stake_total": "100.00", "avg_odds": "2.50",
        "pnl_mode": "MANUAL", "manual_pnl_eur": pnl,
        "status": status,
        "outcome_label": outcome,
    }
    resp = client.post("/api/v1/trades", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestSummary:
    def test_empty_summary(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.get("/api/v1/analytics/summary").json()
        assert resp["n_trades"] == 0
        assert Decimal(resp["total_pnl_eur"]) == Decimal("0")

    def test_summary_aggregates_closed_trades(self, client_with_auth: TestClient) -> None:
        sid = _bare_strategy(client_with_auth)["id"]
        _post(client_with_auth, sid, pnl="50.00", kickoff="2026-04-20T20:00:00+00:00")
        _post(client_with_auth, sid, pnl="-30.00", kickoff="2026-04-21T20:00:00+00:00", outcome="LOSS")
        # OPEN trade ignored
        _post(client_with_auth, sid, pnl="0.00", kickoff="2026-04-22T20:00:00+00:00", status="OPEN")
        s = client_with_auth.get("/api/v1/analytics/summary").json()
        assert s["n_trades"] == 2
        assert Decimal(s["total_pnl_eur"]) == Decimal("20.00")
        assert Decimal(s["roi_pct"]) == Decimal("10.0000")
        assert Decimal(s["win_rate_pct"]) == Decimal("50.0000")


class TestBreakdowns:
    def test_by_strategy(self, client_with_auth: TestClient) -> None:
        a = _bare_strategy(client_with_auth, name="Strat A")["id"]
        b = _bare_strategy(client_with_auth, name="Strat B")["id"]
        _post(client_with_auth, a, pnl="100", kickoff="2026-04-20T20:00:00+00:00")
        _post(client_with_auth, b, pnl="-50", kickoff="2026-04-21T20:00:00+00:00", outcome="LOSS")
        rows = client_with_auth.get("/api/v1/analytics/by-strategy").json()
        assert len(rows) == 2
        # Sorted desc by total_pnl
        assert rows[0]["key"] == "strat-a"
        assert rows[1]["key"] == "strat-b"

    def test_by_league(self, client_with_auth: TestClient) -> None:
        sid = _bare_strategy(client_with_auth)["id"]
        _post(client_with_auth, sid, pnl="20", kickoff="2026-04-20T20:00:00+00:00", league="A")
        _post(client_with_auth, sid, pnl="30", kickoff="2026-04-21T20:00:00+00:00", league="B")
        rows = client_with_auth.get("/api/v1/analytics/by-league").json()
        assert {r["key"] for r in rows} == {"A", "B"}

    def test_by_outcome(self, client_with_auth: TestClient) -> None:
        sid = _bare_strategy(client_with_auth)["id"]
        _post(client_with_auth, sid, pnl="20", kickoff="2026-04-20T20:00:00+00:00", outcome="WIN")
        _post(client_with_auth, sid, pnl="-10", kickoff="2026-04-21T20:00:00+00:00", outcome="LOSS")
        rows = client_with_auth.get("/api/v1/analytics/by-outcome").json()
        keys = {r["key"] for r in rows}
        assert keys == {"WIN", "LOSS"}


class TestRolling:
    def test_rolling_window(self, client_with_auth: TestClient) -> None:
        sid = _bare_strategy(client_with_auth)["id"]
        for i, pnl in enumerate(["10", "20", "-5", "30", "-10"]):
            _post(
                client_with_auth, sid, pnl=pnl,
                kickoff=f"2026-04-{20+i:02d}T20:00:00+00:00",
                outcome="WIN" if Decimal(pnl) > 0 else "LOSS",
            )
        rows = client_with_auth.get(
            "/api/v1/analytics/rolling", params={"window": 3}
        ).json()
        # 5 trades, window=3 → 3 points (indices 2, 3, 4)
        assert [r["idx"] for r in rows] == [2, 3, 4]


class TestDrawdown:
    def test_drawdown_after_loss(self, client_with_auth: TestClient) -> None:
        sid = _bare_strategy(client_with_auth)["id"]
        _post(client_with_auth, sid, pnl="100", kickoff="2026-04-20T20:00:00+00:00")
        _post(client_with_auth, sid, pnl="-30", kickoff="2026-04-21T20:00:00+00:00", outcome="LOSS")
        resp = client_with_auth.get("/api/v1/analytics/drawdown").json()
        assert len(resp["points"]) == 2
        assert Decimal(resp["max_drawdown_eur"]) == Decimal("30.00")


class TestCalendar:
    def test_calendar_buckets(self, client_with_auth: TestClient) -> None:
        sid = _bare_strategy(client_with_auth)["id"]
        _post(client_with_auth, sid, pnl="20", kickoff="2026-04-28T14:00:00+00:00")  # Tue 14
        _post(client_with_auth, sid, pnl="10", kickoff="2026-04-28T14:00:00+00:00")  # same slot
        _post(client_with_auth, sid, pnl="5", kickoff="2026-05-02T20:00:00+00:00")   # Sat 20
        grid = client_with_auth.get("/api/v1/analytics/calendar").json()
        assert len(grid["cells"]) == 2
        # Tuesday 14:00 → 30€ across 2 trades
        tue = next(c for c in grid["cells"] if c["day_of_week"] == 1 and c["hour"] == 14)
        assert tue["n_trades"] == 2
        assert Decimal(tue["pnl_eur"]) == Decimal("30.00")


class TestMonteCarlo:
    def test_monte_carlo_with_history(self, client_with_auth: TestClient) -> None:
        sid = _bare_strategy(client_with_auth)["id"]
        # 4 historical pnls
        for i, pnl in enumerate(["20", "-10", "30", "-15"]):
            _post(
                client_with_auth, sid, pnl=pnl,
                kickoff=f"2026-04-{20+i:02d}T20:00:00+00:00",
                outcome="WIN" if Decimal(pnl) > 0 else "LOSS",
            )
        resp = client_with_auth.post(
            "/api/v1/analytics/monte-carlo",
            json={
                "starting_bankroll": "1000.00",
                "n_simulations": 200, "horizon_trades": 30, "seed": 42,
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["n_simulations"] == 200
        assert body["horizon_trades"] == 30
        assert body["n_historical_pnls"] == 4
        # P10 ≤ P50 ≤ P90
        assert (
            Decimal(body["p10_ending_bankroll"])
            <= Decimal(body["p50_ending_bankroll"])
            <= Decimal(body["p90_ending_bankroll"])
        )

    def test_monte_carlo_with_no_history_returns_flat(
        self, client_with_auth: TestClient
    ) -> None:
        resp = client_with_auth.post(
            "/api/v1/analytics/monte-carlo",
            json={"starting_bankroll": "1000", "n_simulations": 100, "horizon_trades": 10},
        ).json()
        assert resp["n_historical_pnls"] == 0
        assert Decimal(resp["risk_of_ruin_pct"]) == Decimal("0")


class TestWhatIfCashout:
    def test_back_winning(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.post(
            "/api/v1/analytics/whatif-cashout",
            json={
                "stake_total": "62.00", "avg_odds": "5.42",
                "cashout_odds": "1.45", "position_side": "back",
                "commission_pct": "5.00",
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # 62 * (1.45-1) * 0.95 = 26.505 → 26.50 (HALF_EVEN)
        assert Decimal(body["locked_in_pnl_eur"]) == Decimal("26.50")
        assert Decimal(body["breakeven_cashout_odds"]) == Decimal("1")

    def test_lay_breakeven_at_odds_two(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.post(
            "/api/v1/analytics/whatif-cashout",
            json={
                "stake_total": "50.00", "avg_odds": "3.00",
                "cashout_odds": "2.00", "position_side": "lay",
                "commission_pct": "5.00",
            },
        ).json()
        assert Decimal(resp["locked_in_pnl_eur"]) == Decimal("0")
        assert Decimal(resp["breakeven_cashout_odds"]) == Decimal("2")


class TestAuth:
    def test_summary_requires_auth(self, client: TestClient) -> None:
        assert client.get("/api/v1/analytics/summary").status_code == 401
