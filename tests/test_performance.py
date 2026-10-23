"""Board load budget: constant query count, small payload, compression, cacheable assets."""

import gzip
import json
import time
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import event

from app.domain.enums import Role
from app.seed import seed_extra_cases
from app.services.config_loader import get_config
from tests.conftest import Api


def count_queries(factory: Any, action: Any) -> int:
    engine = factory.kw["bind"]
    seen: list[str] = []

    def hook(*args: Any) -> None:
        seen.append(args[2])

    event.listen(engine, "before_cursor_execute", hook)
    try:
        action()
    finally:
        event.remove(engine, "before_cursor_execute", hook)
    return len(seen)


@pytest.fixture
def sixty(world: dict[str, Any], db: Any) -> None:
    with db() as s:
        seed_extra_cases(s, get_config(), 60)
        s.commit()


def test_board_query_count_does_not_grow_with_the_number_of_cases(
    api: Api, world: dict[str, Any], db: Any
) -> None:
    nurse = Api().as_role(Role.NURSE)
    with db() as s:
        seed_extra_cases(s, get_config(), 3)
        s.commit()
    few = count_queries(db, lambda: nurse.get("/board"))
    with db() as s:
        seed_extra_cases(s, get_config(), 57)
        s.commit()
    many = count_queries(db, lambda: nurse.get("/board"))
    assert many == few and many <= 12, (few, many)


def test_board_with_sixty_active_cases_is_small_and_fast(api: Api, sixty: None) -> None:
    nurse = Api().as_role(Role.NURSE)
    started = time.perf_counter()
    resp = nurse.get("/board")
    elapsed = time.perf_counter() - started
    body = resp.json()
    assert len(body["rows"]) == 60
    raw = json.dumps(body, ensure_ascii=False).encode()
    assert len(raw) < 250_000  # uncompressed ceiling
    assert len(gzip.compress(raw)) < 20_000  # what a phone downloads
    assert elapsed < 1.0  # server time on a laptop, well inside the 1.5 s budget on 4G


def test_responses_are_gzipped(api: Api, sixty: None) -> None:
    nurse = Api().as_role(Role.NURSE)
    resp = nurse.client.get("/api/v1/board", headers={"Accept-Encoding": "gzip"})
    assert resp.headers.get("content-encoding") == "gzip"


def test_assets_are_immutable_and_the_shell_is_not_cached(tmp_path: Path) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.main import _mount_frontend
    from app.security import security_headers

    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app-abc123.js").write_text("x" * 2000)
    (tmp_path / "index.html").write_text("<html></html>")
    app = FastAPI()
    app.middleware("http")(security_headers)
    _mount_frontend(app, tmp_path)
    client = TestClient(app)
    assert (
        client.get("/assets/app-abc123.js").headers["cache-control"]
        == "public, max-age=31536000, immutable"
    )
    assert client.get("/").headers["cache-control"] == "no-cache"
