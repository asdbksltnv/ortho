import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.auth import ACCESS_COOKIE
from app.domain.enums import Role
from app.settings import get_settings
from tests.conftest import PASSWORD, Api


def test_login_sets_httponly_cookie_and_returns_user(api: Api) -> None:
    resp = api.login("doctor")
    assert resp.status_code == 200
    body = resp.json()
    assert body["login"] == "doctor" and body["role"] == "doctor"
    assert "password" not in str(body)
    set_cookie = resp.headers.get_list("set-cookie")
    access = next(c for c in set_cookie if c.startswith("access_token="))
    assert "HttpOnly" in access and "SameSite=lax" in access
    csrf = next(c for c in set_cookie if c.startswith("csrf_token="))
    assert "HttpOnly" not in csrf


def test_secure_flag_in_production(api: Api, monkeypatch: Any) -> None:
    monkeypatch.setenv("COOKIE_SECURE", "true")
    get_settings.cache_clear()
    resp = api.login("doctor")
    assert "Secure" in next(
        c for c in resp.headers.get_list("set-cookie") if c.startswith("access")
    )


def test_wrong_password_and_unknown_user_look_identical(api: Api) -> None:
    a = api.login("doctor", "wrong-password")
    b = api.login("nobody", "wrong-password")
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_login_rate_limited_after_repeated_failures(api: Api) -> None:
    for _ in range(5):
        assert api.login("doctor", "bad").status_code == 401
    assert api.login("doctor", "bad").status_code == 429
    assert api.login("doctor", PASSWORD).status_code == 429  # even the right password is held off


def test_rate_limit_is_per_login(api: Api) -> None:
    for _ in range(5):
        api.login("doctor", "bad")
    assert api.login("nurse", PASSWORD).status_code == 200


def test_me_requires_login_and_logout_clears_session(api: Api) -> None:
    assert api.get("/auth/me").status_code == 401
    api.as_role(Role.NURSE)
    assert api.get("/auth/me").json()["login"] == "nurse"
    assert api.post("/auth/logout").status_code == 204
    api.client.cookies.clear()
    assert api.get("/auth/me").status_code == 401


def test_mutating_request_requires_csrf_token(api: Api) -> None:
    api.as_role(Role.ADMIN)
    body = {"name": "Новое"}
    no_header = api.client.post("/api/v1/wards", json=body)
    assert no_header.status_code == 403 and no_header.json()["code"] == "csrf_failed"
    wrong = api.client.post("/api/v1/wards", json=body, headers={"X-CSRF-Token": "nope"})
    assert wrong.status_code == 403
    assert api.post("/wards", json=body).status_code == 201


def test_get_does_not_need_csrf(api: Api) -> None:
    api.as_role(Role.NURSE)
    assert api.client.get("/api/v1/board").status_code == 200


def test_expired_token_is_rejected(api: Api, world: dict[str, Any]) -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(world["doctor"]),
            "csrf": "x",
            "iat": int((now - timedelta(minutes=30)).timestamp()),
            "exp": int((now - timedelta(minutes=15)).timestamp()),
        },
        settings.secret_key,
        algorithm="HS256",
    )
    api.client.cookies.set(ACCESS_COOKIE, token)
    assert api.get("/auth/me").status_code == 401


def test_token_signed_with_other_key_is_rejected(api: Api, world: dict[str, Any]) -> None:
    token = jwt.encode(
        {
            "sub": str(world["doctor"]),
            "csrf": "x",
            "exp": int((datetime.now(UTC) + timedelta(minutes=5)).timestamp()),
        },
        "some-other-secret-key-that-is-long-enough",
        algorithm="HS256",
    )
    api.client.cookies.set(ACCESS_COOKIE, token)
    assert api.get("/auth/me").status_code == 401


def test_activity_refreshes_session_cookie(api: Api) -> None:
    api.as_role(Role.DOCTOR)
    resp = api.get("/auth/me")
    assert any(c.startswith("access_token=") for c in resp.headers.get_list("set-cookie"))


def test_deactivated_user_is_locked_out_immediately(api: Api, world: dict[str, Any]) -> None:
    admin = Api().as_role(Role.ADMIN)
    api.as_role(Role.NURSE)
    assert api.get("/auth/me").status_code == 200
    assert admin.patch(f"/users/{world['nurse']}", json={"is_active": False}).status_code == 200
    assert api.get("/auth/me").status_code == 401
    assert Api().login("nurse").status_code == 401


def test_admin_cannot_lock_themselves_out(api: Api, world: dict[str, Any]) -> None:
    api.as_role(Role.ADMIN)
    assert api.patch(f"/users/{world['admin']}", json={"is_active": False}).status_code == 409
    assert api.patch(f"/users/{world['admin']}", json={"role": "doctor"}).status_code == 409


def test_change_password(api: Api) -> None:
    api.as_role(Role.NURSE)
    bad = api.post(
        "/auth/change-password", json={"current_password": "nope", "new_password": "NewPassw0rd!99"}
    )
    assert bad.status_code == 422
    short = api.post(
        "/auth/change-password", json={"current_password": PASSWORD, "new_password": "short"}
    )
    assert short.status_code == 422
    ok = api.post(
        "/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "NewPassw0rd!99"},
    )
    assert ok.status_code == 204
    assert Api().login("nurse", PASSWORD).status_code == 401
    assert Api().login("nurse", "NewPassw0rd!99").status_code == 200


def test_admin_user_management(api: Api) -> None:
    api.as_role(Role.ADMIN)
    created = api.post(
        "/users",
        json={
            "login": "new.doc",
            "full_name": "Новый Врач",
            "role": "doctor",
            "password": "Passw0rd!12345",
        },
    )
    assert created.status_code == 201
    assert "password" not in created.text
    assert (
        api.post(
            "/users",
            json={
                "login": "new.doc",
                "full_name": "Дубликат",
                "role": "nurse",
                "password": "Passw0rd!12345",
            },
        ).status_code
        == 409
    )
    weak = api.post(
        "/users",
        json={"login": "weak", "full_name": "Слабый", "role": "nurse", "password": "short"},
    )
    assert weak.status_code == 422
    uid = uuid.UUID(created.json()["id"])
    assert (
        api.post(f"/users/{uid}/reset-password", json={"password": "Reset!Passw0rd1"}).status_code
        == 204
    )
    assert Api().login("new.doc", "Reset!Passw0rd1").status_code == 200


def test_error_shape_is_code_message_details(api: Api) -> None:
    body = api.get("/auth/me").json()
    assert set(body) == {"code", "message", "details"}
    assert api.client.post("/api/v1/auth/login", json={}).json()["code"] == "validation_error"
