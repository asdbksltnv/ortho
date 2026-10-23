from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_security_headers(client: TestClient) -> None:
    r = client.get("/api/health")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"


def test_meta_exposes_demo_flag(client: TestClient) -> None:
    body = client.get("/api/v1/meta").json()
    assert set(body) == {
        "version",
        "demo_mode",
        "session_timeout_min",
        "decimal_separator",
        "tz_display",
    }
