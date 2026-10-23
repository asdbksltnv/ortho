from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import _mount_frontend


@pytest.fixture
def spa_client(tmp_path: Path) -> TestClient:
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "index.html").write_text("<html>shell</html>")
    (tmp_path.parent / "secret.txt").write_text("nope")
    app = FastAPI()
    _mount_frontend(app, tmp_path)
    return TestClient(app)


def test_index_and_spa_fallback(spa_client: TestClient) -> None:
    assert "shell" in spa_client.get("/").text
    assert "shell" in spa_client.get("/case/abc").text


def test_unknown_api_path_is_404(spa_client: TestClient) -> None:
    assert spa_client.get("/api/v1/nope").status_code == 404


def test_path_traversal_does_not_escape(spa_client: TestClient) -> None:
    r = spa_client.get("/%2e%2e/secret.txt")
    assert "nope" not in r.text
