"""Every endpoint x every role. Unauthenticated callers get 401; wrong roles get 403."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from app.domain.enums import Role
from tests.conftest import Api, case_payload

R = Role
CLINICAL = {R.DOCTOR, R.NURSE, R.ANAESTHESIOLOGIST, R.HEAD_OF_DEPARTMENT, R.HEAD_NURSE}
NOW = datetime(2026, 3, 1, 9, 0, tzinfo=UTC).isoformat()

Body = Callable[[dict[str, Any]], dict[str, Any] | None]

# (method, path template, body factory, roles allowed by the permission matrix)
ENDPOINTS: list[tuple[str, str, Body, set[Role]]] = [
    ("GET", "/board", lambda w: None, CLINICAL),
    ("GET", "/cases/{case}", lambda w: None, CLINICAL),
    (
        "POST",
        "/cases",
        lambda w: case_payload(treating_doctor_id=str(w["doctor"])),
        {R.DOCTOR, R.HEAD_OF_DEPARTMENT},
    ),
    ("PATCH", "/cases/{case}", lambda w: {"side": "right"}, {R.DOCTOR, R.HEAD_OF_DEPARTMENT}),
    (
        "PATCH",
        "/cases/{case}/checklist/docs",
        lambda w: {"status": "done"},
        {R.DOCTOR, R.HEAD_OF_DEPARTMENT},
    ),
    (
        "PATCH",
        "/cases/{case}/checklist/labs_core",
        lambda w: {"status": "done"},
        {R.DOCTOR, R.HEAD_OF_DEPARTMENT, R.NURSE, R.HEAD_NURSE},
    ),
    (
        "PATCH",
        "/cases/{case}/checklist/consent_surgical",
        lambda w: {"status": "done"},
        {R.DOCTOR, R.HEAD_OF_DEPARTMENT, R.NURSE, R.HEAD_NURSE},
    ),
    (
        "PATCH",
        "/cases/{case}/checklist/anaesthesia",
        lambda w: {"status": "done"},
        {R.ANAESTHESIOLOGIST, R.HEAD_OF_DEPARTMENT},
    ),
    ("GET", "/cases/{case}/labs", lambda w: None, CLINICAL),
    (
        "POST",
        "/cases/{case}/labs",
        lambda w: {"lab_code": "hiv", "result_text": "отр.", "collected_at": NOW},
        {R.DOCTOR, R.HEAD_OF_DEPARTMENT, R.NURSE, R.HEAD_NURSE},
    ),
    (
        "POST",
        "/cases/{case}/consents",
        lambda w: {"type": "surgical", "signed_at": NOW},
        {R.DOCTOR, R.HEAD_OF_DEPARTMENT, R.NURSE, R.HEAD_NURSE},
    ),
    ("GET", "/staff", lambda w: None, CLINICAL),
    ("GET", "/wards", lambda w: None, set(Role)),
    ("POST", "/wards", lambda w: {"name": "Новое"}, {R.ADMIN}),
    ("POST", "/wards/rooms", lambda w: {"ward_id": str(w["ward"]), "name": "Пал. 9"}, {R.ADMIN}),
    ("PATCH", "/wards/rooms/{room}", lambda w: {"name": "Пал. 1А"}, {R.ADMIN}),
    ("POST", "/wards/beds", lambda w: {"room_id": str(w["room"]), "label": "к. 9"}, {R.ADMIN}),
    ("PATCH", "/wards/beds/{bed}", lambda w: {"label": "к. 1А"}, {R.ADMIN}),
    ("GET", "/users", lambda w: None, {R.ADMIN}),
    (
        "POST",
        "/users",
        lambda w: {
            "login": "newuser",
            "full_name": "Новый",
            "role": "nurse",
            "password": "Passw0rd!12345",
        },
        {R.ADMIN},
    ),
    ("PATCH", "/users/{doctor}", lambda w: {"full_name": "Тест doctor"}, {R.ADMIN}),
    (
        "POST",
        "/users/{doctor}/reset-password",
        lambda w: {"password": "Another!Pass123"},
        {R.ADMIN},
    ),
    ("GET", "/audit", lambda w: None, {R.ADMIN, R.HEAD_OF_DEPARTMENT}),
    ("GET", "/admin/config-status", lambda w: None, {R.ADMIN}),
    ("GET", "/config/definitions", lambda w: None, set(Role)),
    ("GET", "/config/intake", lambda w: None, set(Role)),
    ("GET", "/cases/{case}/intake", lambda w: None, CLINICAL),
    (
        "PUT",
        "/cases/{case}/intake",
        lambda w: {"data": {}, "request_id": str(uuid.uuid4())},
        {R.DOCTOR, R.HEAD_OF_DEPARTMENT},
    ),
    ("GET", "/cases/{case}/documents", lambda w: None, CLINICAL),
    ("GET", "/cases/{case}/documents/t1_primary_exam", lambda w: None, CLINICAL),
    (
        "POST",
        "/cases/{case}/documents/t1_primary_exam/generate",
        lambda w: {},
        {R.DOCTOR, R.HEAD_OF_DEPARTMENT},
    ),
    (
        "POST",
        "/cases/{case}/documents/t1_primary_exam/copy-all",
        lambda w: {},
        {R.DOCTOR, R.HEAD_OF_DEPARTMENT},
    ),
    (
        "PUT",
        "/cases/{case}/anaesthesia",
        lambda w: {"type": "Тест"},
        {R.ANAESTHESIOLOGIST, R.HEAD_OF_DEPARTMENT},
    ),
]


@pytest.fixture
def ctx(api: Api, world: dict[str, Any], case_id: uuid.UUID, db: Any) -> dict[str, Any]:
    from sqlalchemy import select

    from app.models.ward import Ward

    with db() as s:
        ward_id = s.scalars(select(Ward.id)).first()
    return {
        "case": case_id,
        "room": world["room"],
        "bed": world["beds"][1],
        "doctor": world["doctor"],
        "ward": ward_id,
    }


def _ids(param: tuple[str, str, Body, set[Role]]) -> str:
    return f"{param[0]} {param[1]}"


@pytest.mark.parametrize("endpoint", ENDPOINTS, ids=_ids)
@pytest.mark.parametrize("role", list(Role))
def test_matrix(
    endpoint: tuple[str, str, Body, set[Role]], role: Role, api: Api, ctx: dict[str, Any]
) -> None:
    method, template, body_factory, allowed = endpoint
    path = template.format(**ctx)
    api.as_role(role)
    response = api.request(method, path, json=body_factory(ctx))
    if role in allowed:
        # A permitted call may still be refused for data reasons (e.g. 422 generation_blocked).
        assert response.status_code not in (401, 403), (role, path, response.text)
    else:
        assert response.status_code == 403, (role, path, response.status_code)
        assert response.json()["code"] == "forbidden"


@pytest.mark.parametrize("endpoint", ENDPOINTS, ids=_ids)
def test_unauthenticated_gets_401(
    endpoint: tuple[str, str, Body, set[Role]], api: Api, ctx: dict[str, Any]
) -> None:
    method, template, body_factory, _ = endpoint
    api.client.cookies.clear()
    response = api.request(method, template.format(**ctx), json=body_factory(ctx))
    assert response.status_code == 401


def test_doctor_cannot_edit_another_doctors_case(api: Api, case_id: uuid.UUID) -> None:
    api.login("doctor2")
    assert api.patch(f"/cases/{case_id}", json={"side": "right"}).status_code == 403
    assert api.patch(f"/cases/{case_id}/checklist/docs", json={"status": "done"}).status_code == 403
    labs = {"lab_code": "hiv", "result_text": "отр.", "collected_at": NOW}
    assert api.post(f"/cases/{case_id}/labs", json=labs).status_code == 403
    # but may read it
    assert api.get(f"/cases/{case_id}").status_code == 200


def test_only_head_reassigns_treating_doctor(
    api: Api, case_id: uuid.UUID, world: dict[str, Any]
) -> None:
    api.as_role(Role.DOCTOR)
    body = {"treating_doctor_id": str(world["doctor2"])}
    assert api.patch(f"/cases/{case_id}", json=body).status_code == 403
    api.as_role(Role.HEAD_OF_DEPARTMENT)
    assert api.patch(f"/cases/{case_id}", json=body).status_code == 200


def test_head_must_name_treating_doctor_when_creating(api: Api) -> None:
    api.as_role(Role.HEAD_OF_DEPARTMENT)
    assert api.post("/cases", json=case_payload()).status_code == 422


def test_admin_cannot_read_patient_data(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.ADMIN)
    assert api.get(f"/cases/{case_id}").status_code == 403
    assert api.get("/board").status_code == 403
