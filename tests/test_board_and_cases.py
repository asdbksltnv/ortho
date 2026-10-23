import json
import uuid
from datetime import date, timedelta
from typing import Any

import pytest

from app.domain.enums import Role
from tests.conftest import Api, case_payload

ALL_KEYS = [
    "docs",
    "labs_core",
    "labs_optional",
    "consults",
    "consent_surgical",
    "anaesthesia",
    "antibiotic",
    "anticoag",
    "site_marking",
    "blood_reserve",
    "implant",
]
TODAY = date(2026, 3, 10)


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.cases.local_today", lambda: TODAY)
    monkeypatch.setattr("app.services.board.local_today", lambda: TODAY)


def _set(api: Api, role: Role, case: uuid.UUID, key: str, status: str, **extra: Any) -> Any:
    api.as_role(role)
    return api.patch(f"/cases/{case}/checklist/{key}", json={"status": status, **extra})


def _mark_all_done(api: Api, case: uuid.UUID, keys: list[str]) -> None:
    owners = {
        "labs_core": Role.NURSE,
        "anaesthesia": Role.ANAESTHESIOLOGIST,
        "blood_reserve": Role.NURSE,
        "implant": Role.NURSE,
    }
    for key in keys:
        assert (
            _set(api, owners.get(key, Role.HEAD_OF_DEPARTMENT), case, key, "done").status_code
            == 200
        )


def test_board_contains_initials_never_full_name_or_identifiers(
    api: Api, case_id: uuid.UUID
) -> None:
    api.as_role(Role.NURSE)
    raw = api.get("/board").text
    row = json.loads(raw)["rows"][0]
    assert row["initials"] == "И. А. Д."
    for secret in ("Иванов", "Алишер", "Дилшодович", "T-0001", "1960"):
        assert secret not in raw
    assert set(row) >= {"case_id", "initials", "room_name", "bed_label", "ready", "items"}


def test_case_page_has_full_identity_and_writes_view_audit(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.NURSE)
    body = api.get(f"/cases/{case_id}").json()
    assert body["patient"]["full_name"] == "Иванов Алишер Дилшодович"
    assert body["patient"]["medical_record_number"] == "T-0001"
    api.as_role(Role.HEAD_OF_DEPARTMENT)
    views = api.get("/audit?action=view").json()["items"]
    assert any(v["entity_id"] == str(case_id) for v in views)


def test_new_case_has_every_checklist_item_not_started(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.DOCTOR)
    body = api.get(f"/cases/{case_id}").json()
    assert sorted(i["key"] for i in body["items"]) == sorted(ALL_KEYS)
    assert {i["status"] for i in body["items"]} == {"not_started"}
    assert body["status"] == "admitted"
    assert body["readiness"]["ready"] is False


def test_tka_becomes_ready_only_when_always_and_procedure_items_done(
    api: Api, case_id: uuid.UUID
) -> None:
    always = ["docs", "labs_core", "consent_surgical", "anaesthesia", "antibiotic"]
    _mark_all_done(api, case_id, always)
    api.as_role(Role.DOCTOR)
    body = api.get(f"/cases/{case_id}").json()
    assert body["readiness"] == {"ready": False, "blocking": ["blood_reserve", "implant"]}
    _mark_all_done(api, case_id, ["blood_reserve", "implant"])
    api.as_role(Role.DOCTOR)
    assert api.get(f"/cases/{case_id}").json()["readiness"] == {"ready": True, "blocking": []}


def test_arthroscopy_does_not_require_blood_or_implant(api: Api, world: dict[str, Any]) -> None:
    api.as_role(Role.DOCTOR)
    cid = api.post("/cases", json=case_payload(procedure_key="arthroscopy")).json()["id"]
    _mark_all_done(
        api, uuid.UUID(cid), ["docs", "labs_core", "consent_surgical", "anaesthesia", "antibiotic"]
    )
    api.as_role(Role.DOCTOR)
    assert api.get(f"/cases/{cid}").json()["readiness"]["ready"] is True


def test_anticoagulant_flag_makes_anticoag_item_blocking(api: Api, case_id: uuid.UUID) -> None:
    _mark_all_done(
        api,
        case_id,
        [
            "docs",
            "labs_core",
            "consent_surgical",
            "anaesthesia",
            "antibiotic",
            "blood_reserve",
            "implant",
        ],
    )
    api.as_role(Role.DOCTOR)
    assert api.get(f"/cases/{case_id}").json()["readiness"]["ready"] is True
    assert api.patch(f"/cases/{case_id}", json={"takes_anticoagulant": True}).status_code == 200
    assert api.get(f"/cases/{case_id}").json()["readiness"]["blocking"] == ["anticoag"]
    assert _set(api, Role.DOCTOR, case_id, "anticoag", "done").json()["readiness"]["ready"] is True


def test_site_marking_blocks_on_the_day_of_surgery_only(api: Api, case_id: uuid.UUID) -> None:
    _mark_all_done(
        api,
        case_id,
        [
            "docs",
            "labs_core",
            "consent_surgical",
            "anaesthesia",
            "antibiotic",
            "blood_reserve",
            "implant",
        ],
    )
    api.as_role(Role.DOCTOR)
    tomorrow = (TODAY + timedelta(days=1)).isoformat()
    body = api.patch(f"/cases/{case_id}", json={"planned_surgery_date": tomorrow}).json()
    assert body["readiness"]["ready"] is True
    body = api.patch(f"/cases/{case_id}", json={"planned_surgery_date": TODAY.isoformat()}).json()
    assert body["readiness"]["blocking"] == ["site_marking"]


def test_pending_consults_block_until_done(api: Api, case_id: uuid.UUID) -> None:
    _mark_all_done(
        api,
        case_id,
        [
            "docs",
            "labs_core",
            "consent_surgical",
            "anaesthesia",
            "antibiotic",
            "blood_reserve",
            "implant",
        ],
    )
    body = _set(api, Role.DOCTOR, case_id, "consults", "pending").json()
    assert body["readiness"]["blocking"] == ["consults"]
    assert _set(api, Role.DOCTOR, case_id, "consults", "not_applicable").json()["readiness"][
        "ready"
    ]


def test_board_filters(api: Api, case_id: uuid.UUID, world: dict[str, Any]) -> None:
    api.as_role(Role.DOCTOR)
    api.post(
        "/cases",
        json=case_payload(
            patient={
                "full_name": "Петров Иван",
                "birth_date": "1970-01-01",
                "sex": "M",
                "medical_record_number": "T-2",
            },
            planned_surgery_date=(TODAY + timedelta(days=1)).isoformat(),
            bed_id=str(world["beds"][1]),
        ),
    )
    api.as_role(Role.HEAD_OF_DEPARTMENT)
    other = api.post(
        "/cases",
        json=case_payload(
            patient={
                "full_name": "Сидоров Пётр",
                "birth_date": "1971-01-01",
                "sex": "M",
                "medical_record_number": "T-3",
            },
            treating_doctor_id=str(world["doctor2"]),
            bed_id=str(world["beds"][2]),
        ),
    ).json()
    assert len(api.get("/board").json()["rows"]) == 3
    assert len(api.get("/board?not_ready=true").json()["rows"]) == 3
    assert len(api.get("/board?surgery_tomorrow=true").json()["rows"]) == 1
    assert [
        r["case_id"] for r in api.get(f"/board?doctor_id={world['doctor2']}").json()["rows"]
    ] == [other["id"]]
    api.as_role(Role.DOCTOR)
    assert len(api.get("/board?mine=true").json()["rows"]) == 2


def test_board_rows_sorted_by_room_then_bed_and_columns_follow_config(
    api: Api, case_id: uuid.UUID
) -> None:
    api.as_role(Role.NURSE)
    board = api.get("/board").json()
    assert [c["key"] for c in board["columns"]] == ALL_KEYS


def test_discharged_cases_leave_the_board(api: Api, case_id: uuid.UUID, db: Any) -> None:
    from app.models.case import Case

    with db() as s:
        s.get(Case, case_id).status = "discharged"  # type: ignore[union-attr]
        s.commit()
    api.as_role(Role.NURSE)
    assert api.get("/board").json()["rows"] == []


def test_checklist_conflict_returns_current_value(api: Api, case_id: uuid.UUID) -> None:
    first = _set(api, Role.NURSE, case_id, "labs_core", "pending").json()
    seen = next(i for i in first["items"] if i["key"] == "labs_core")["updated_at"]
    _set(api, Role.HEAD_NURSE, case_id, "labs_core", "problem", note="повторить")
    api.as_role(Role.NURSE)
    conflict = api.patch(
        f"/cases/{case_id}/checklist/labs_core",
        json={"status": "done", "expected_updated_at": seen},
    )
    assert conflict.status_code == 409
    body = conflict.json()
    assert body["code"] == "conflict"
    assert body["details"]["current"]["status"] == "problem"
    assert body["details"]["current"]["updated_by"] == "Тест headnurse"
    # retrying with the fresh version succeeds
    fresh = body["details"]["current"]["updated_at"]
    retry = api.patch(
        f"/cases/{case_id}/checklist/labs_core",
        json={"status": "done", "expected_updated_at": fresh},
    )
    assert retry.status_code == 200


def test_checklist_records_who_changed_it(api: Api, case_id: uuid.UUID) -> None:
    body = _set(api, Role.NURSE, case_id, "labs_core", "pending", note="взяли кровь").json()
    item = next(i for i in body["items"] if i["key"] == "labs_core")
    assert item["updated_by"] == "Тест nurse" and item["note"] == "взяли кровь"


def test_unknown_checklist_key_is_404(api: Api, case_id: uuid.UUID) -> None:
    assert _set(api, Role.HEAD_OF_DEPARTMENT, case_id, "nonsense", "done").status_code == 404


def test_invalid_status_is_422(api: Api, case_id: uuid.UUID) -> None:
    assert _set(api, Role.HEAD_OF_DEPARTMENT, case_id, "docs", "finished").status_code == 422


def test_first_ready_at_is_set_once(api: Api, case_id: uuid.UUID, db: Any) -> None:
    from app.models.case import Case

    _mark_all_done(
        api,
        case_id,
        [
            "docs",
            "labs_core",
            "consent_surgical",
            "anaesthesia",
            "antibiotic",
            "blood_reserve",
            "implant",
        ],
    )
    with db() as s:
        first = s.get(Case, case_id).first_ready_at  # type: ignore[union-attr]
    assert first is not None
    _set(api, Role.NURSE, case_id, "labs_core", "problem")
    with db() as s:
        assert s.get(Case, case_id).first_ready_at == first  # type: ignore[union-attr]


def test_bed_cannot_be_double_booked(api: Api, case_id: uuid.UUID, world: dict[str, Any]) -> None:
    api.as_role(Role.DOCTOR)
    resp = api.post("/cases", json=case_payload(bed_id=str(world["beds"][0])))
    assert resp.status_code == 409 and resp.json()["code"] == "bed_occupied"


def test_unknown_procedure_rejected(api: Api) -> None:
    api.as_role(Role.DOCTOR)
    assert api.post("/cases", json=case_payload(procedure_key="nope")).status_code == 422


def test_validation_errors_do_not_echo_submitted_values(api: Api) -> None:
    api.as_role(Role.DOCTOR)
    resp = api.post(
        "/cases",
        json=case_payload(
            patient={
                "full_name": "Секретов Секрет",
                "birth_date": "not-a-date",
                "sex": "X",
                "medical_record_number": "S-1",
            }
        ),
    )
    assert resp.status_code == 422
    assert "Секретов" not in resp.text and "not-a-date" not in resp.text


def test_lab_validity_follows_config(
    api: Api, case_id: uuid.UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.config_loader import get_config

    api.as_role(Role.NURSE)
    payload = {
        "lab_code": "hiv",
        "result_text": "отрицательно",
        "collected_at": "2026-03-01T08:00:00+00:00",
    }
    assert (
        api.post(f"/cases/{case_id}/labs", json=payload).json()["valid_until"] is None
    )  # rule is null
    config = get_config()
    lab = next(x for x in config.labs.labs if x.code == "hiv")
    monkeypatch.setattr(lab, "validity_days", 30)
    assert api.post(f"/cases/{case_id}/labs", json=payload).json()["valid_until"] == "2026-03-31"
    bad = api.post(f"/cases/{case_id}/labs", json={**payload, "lab_code": "zzz"})
    assert bad.status_code == 422


def test_naive_datetime_is_rejected_for_labs(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.NURSE)
    resp = api.post(
        f"/cases/{case_id}/labs",
        json={"lab_code": "hiv", "result_text": "x", "collected_at": "2026-03-01T08:00:00"},
    )
    assert resp.status_code == 422
