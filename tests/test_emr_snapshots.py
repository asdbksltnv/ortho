"""Snapshot tests of the generated Russian text: one synthetic TKA case per template.

Regenerate after an intentional wording change:  UPDATE_SNAPSHOTS=1 pytest tests/test_emr_snapshots.py
"""

import os
import uuid
from pathlib import Path

import pytest

from app.domain.enums import Role
from tests.conftest import Api
from tests.intake_fixture import tka_intake
from tests.test_documents_api import (
    T1,
    T2,
    T3,
    _fixed_today,  # noqa: F401 - autouse fixture reused
    _ready_for_t3,
    put_intake,
)

SNAPSHOTS = Path(__file__).parent / "snapshots"


def check(name: str, actual: str) -> None:
    path = SNAPSHOTS / f"{name}.txt"
    if os.environ.get("UPDATE_SNAPSHOTS"):
        path.write_text(actual + "\n", encoding="utf-8")
    assert path.exists(), f"missing snapshot {path.name}; run with UPDATE_SNAPSHOTS=1"
    assert actual + "\n" == path.read_text(encoding="utf-8")


def render_all(api: Api, case_id: uuid.UUID, template: str) -> str:
    api.as_role(Role.DOCTOR)
    assert api.post(f"/cases/{case_id}/documents/{template}/generate").status_code == 200
    return api.post(f"/cases/{case_id}/documents/{template}/copy-all").json()["all_text"]


@pytest.fixture
def prepared(api: Api, case_id: uuid.UUID) -> uuid.UUID:
    _ready_for_t3(api, case_id)
    api.as_role(Role.DOCTOR)
    data = tka_intake()
    for key in ("skin", "cvs", "resp", "gu", "gi"):
        data["systems"][key] = {"normal": True, "text": ""}
    put_intake(api, case_id, data)
    return case_id


def test_t1_snapshot(api: Api, prepared: uuid.UUID) -> None:
    check("t1_tka", render_all(api, prepared, T1))


def test_t2_snapshot(api: Api, prepared: uuid.UUID) -> None:
    check("t2_tka", render_all(api, prepared, T2))


def test_t3_snapshot(api: Api, prepared: uuid.UUID) -> None:
    check("t3_tka", render_all(api, prepared, T3))
