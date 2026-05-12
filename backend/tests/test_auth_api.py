"""Auth API integration tests — login, refresh, /me, permission matrix."""

from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security import _create_token


class TestLogin:
    def test_login_returns_token_pair(self, client: TestClient) -> None:
        settings = get_settings()
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "email": settings.default_user_email,
                "password": settings.default_user_password,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert {"access_token", "refresh_token", "token_type", "expires_in"} <= body.keys()
        assert body["token_type"] == "bearer"
        assert body["expires_in"] == settings.jwt_access_token_ttl_minutes * 60
        assert body["access_token"] != body["refresh_token"]

    def test_login_with_wrong_password_returns_401(self, client: TestClient) -> None:
        settings = get_settings()
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": settings.default_user_email, "password": "wrong"},
        )
        assert resp.status_code == 401
        assert resp.headers["content-type"].startswith("application/problem+json")
        body = resp.json()
        assert body["title"] == "Unauthorized"
        # No email enumeration: same generic message regardless.
        assert "Invalid email or password" in body["detail"]

    def test_login_with_unknown_email_returns_401(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "ghost@example.com", "password": "whatever"},
        )
        assert resp.status_code == 401

    def test_login_email_validation(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "not-an-email", "password": "x"},
        )
        assert resp.status_code == 422
        assert resp.headers["content-type"].startswith("application/problem+json")
        body = resp.json()
        assert "errors" in body  # structured validation errors


class TestRefresh:
    def test_refresh_returns_new_pair(self, client: TestClient) -> None:
        settings = get_settings()
        login_resp = client.post(
            "/api/v1/auth/login",
            json={
                "email": settings.default_user_email,
                "password": settings.default_user_password,
            },
        )
        refresh_token = login_resp.json()["refresh_token"]

        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        new_pair = resp.json()
        assert new_pair["access_token"]  # non-empty

    def test_refresh_rejects_garbage(self, client: TestClient) -> None:
        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-jwt"})
        assert resp.status_code == 401

    def test_refresh_rejects_an_access_token(self, client: TestClient, auth_headers) -> None:
        # Reuse the access token as a refresh token — must be rejected by type check.
        access = auth_headers["Authorization"].removeprefix("Bearer ")
        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": access})
        assert resp.status_code == 401


class TestMe:
    def test_me_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_me_returns_current_user(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.get("/api/v1/auth/me")
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == get_settings().default_user_email
        assert "id" in body
        assert "created_at" in body

    def test_me_rejects_expired_token(self, client: TestClient) -> None:
        # Forge an already-expired access token for the right user.
        settings = get_settings()
        # Need the seeded user's id — login once to obtain it via /me.
        login = client.post(
            "/api/v1/auth/login",
            json={
                "email": settings.default_user_email,
                "password": settings.default_user_password,
            },
        ).json()
        # Decode the valid access token to extract the sub.
        from jose import jwt

        sub = jwt.decode(login["access_token"], settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])["sub"]
        expired = _create_token(sub, "access", ttl=timedelta(seconds=-1))
        resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})
        assert resp.status_code == 401

    def test_me_rejects_refresh_token_used_as_access(self, client: TestClient) -> None:
        settings = get_settings()
        login = client.post(
            "/api/v1/auth/login",
            json={
                "email": settings.default_user_email,
                "password": settings.default_user_password,
            },
        ).json()
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {login['refresh_token']}"},
        )
        assert resp.status_code == 401
