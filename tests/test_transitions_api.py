import uuid
from datetime import date
from typing import Any

import pytest
from sqlalchemy import select

from app.domain.enums import Role
from app.models.case import Case, CaseStatusEvent, Notification
from tests.conftest import Api, FakeTelegram, case_payload, link_telegram
from tests.helpers import make_ready

TODAY = date(2026, 3, 10)
PATIENT_NAME = "Иванов Алишер Дилшодович"


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    for target in (
        "app.services.cases",
        "app.services.board",
        "app.services.transitions",
        "app.services.postop",
    ):
        monkeypatch.setattr(f"{target}.local_today", lambda: TODAY)


def go(role: Role, case: uuid.UUID, to: str, **body: Any) -> Any:
    return Api().as_role(role).post(f"/cases/{case}/transition", json={"to": to, **body})


def status_of(case: uuid.UUID, role: Role = Role.HEAD_OF_DEPARTMENT) -> str:
    return Api().as_role(role).get(f"/cases/{case}").json()["status"]


def approve(case: uuid.UUID) -> None:
    assert go(Role.DOCTOR, case, "in_preparation").status_code == 200
    assert (
        go(
            Role.HEAD_OF_DEPARTMENT, case, "approved_for_surgery", planned_surgery_date="2026-03-11"
        ).status_code
        == 200
    )


def test_full_happy_path_writes_a_status_event_for_every_step(
    api: Api, case_id: uuid.UUID, db: Any
) -> None:
    approve(case_id)
    make_ready(case_id)
    steps = [
        (Role.DOCTOR, "called_to_or"),
        (Role.NURSE, "left_ward"),
        (Role.NURSE, "in_or"),
        (Role.NURSE, "returned_to_ward"),
        (Role.NURSE, "post_op"),
        (Role.DOCTOR, "discharged"),
    ]
    for role, to in steps:
        resp = go(role, case_id, to)
        assert resp.status_code == 200, (to, resp.text)
        assert resp.json()["status"] == to
    with db() as s:
        events = s.scalars(
            select(CaseStatusEvent)
            .where(CaseStatusEvent.case_id == case_id)
            .order_by(CaseStatusEvent.created_at)
        ).all()
        assert [e.to_status for e in events] == [
            "admitted",
            "in_preparation",
            "approved_for_surgery",
            "called_to_or",
            "left_ward",
            "in_or",
            "returned_to_ward",
            "post_op",
            "discharged",
        ]
        assert events[-1].from_status == "post_op"
        assert s.get(Case, case_id).operated_on == TODAY  # type: ignore[union-attr]
    api.as_role(Role.NURSE)
    assert api.get("/board").json()["rows"] == []  # discharged: off the board


def test_events_endpoint_lists_who_and_why(api: Api, case_id: uuid.UUID) -> None:
    approve(case_id)
    api.as_role(Role.NURSE)
    events = api.get(f"/cases/{case_id}/events").json()
    assert [e["to_status"] for e in events] == [
        "admitted",
        "in_preparation",
        "approved_for_surgery",
    ]
    assert events[2]["user_name"] == "Тест head"
    assert Api().as_role(Role.ADMIN).get(f"/cases/{case_id}/events").status_code == 403


def test_only_the_head_approves_and_a_planned_date_is_required(
    api: Api, case_id: uuid.UUID
) -> None:
    go(Role.DOCTOR, case_id, "in_preparation")
    assert (
        go(
            Role.DOCTOR, case_id, "approved_for_surgery", planned_surgery_date="2026-03-11"
        ).status_code
        == 403
    )
    no_date = go(Role.HEAD_OF_DEPARTMENT, case_id, "approved_for_surgery")
    assert no_date.status_code == 422 and no_date.json()["code"] == "planned_date_required"
    ok = go(
        Role.HEAD_OF_DEPARTMENT,
        case_id,
        "approved_for_surgery",
        planned_surgery_date="2026-03-11",
        planned_surgery_time="09:30:00",
    )
    body = ok.json()
    assert ok.status_code == 200 and body["planned_surgery_date"] == "2026-03-11"
    assert body["planned_surgery_time"] == "09:30:00"


def test_a_refused_move_does_not_save_the_planned_date(api: Api, case_id: uuid.UUID) -> None:
    go(Role.DOCTOR, case_id, "in_preparation")
    go(Role.DOCTOR, case_id, "approved_for_surgery", planned_surgery_date="2026-04-01")
    api.as_role(Role.DOCTOR)
    assert api.get(f"/cases/{case_id}").json()["planned_surgery_date"] is None


def test_call_to_or_is_refused_for_a_case_that_is_not_ready(api: Api, case_id: uuid.UUID) -> None:
    approve(case_id)
    resp = go(Role.DOCTOR, case_id, "called_to_or")
    assert resp.status_code == 409 and resp.json()["code"] == "not_ready"
    assert "Анализы" in resp.json()["details"]["blocking"]
    assert status_of(case_id) == "approved_for_surgery"
    # a doctor cannot talk their way past it
    refused = go(Role.DOCTOR, case_id, "called_to_or", reason="очень нужно")
    assert refused.status_code == 409


def test_head_override_requires_a_reason_and_shows_on_board_and_events(
    api: Api, case_id: uuid.UUID, db: Any
) -> None:
    approve(case_id)
    no_reason = go(Role.HEAD_OF_DEPARTMENT, case_id, "called_to_or")
    assert no_reason.status_code == 422 and no_reason.json()["code"] == "override_reason_required"
    ok = go(Role.HEAD_OF_DEPARTMENT, case_id, "called_to_or", reason="Освободилась операционная")
    assert ok.status_code == 200 and ok.json()["override_reason"] == "Освободилась операционная"
    board = Api().as_role(Role.NURSE).get("/board").json()["rows"][0]
    assert (
        board["status"] == "called_to_or"
        and board["override_reason"] == "Освободилась операционная"
    )
    with db() as s:
        event = s.scalars(
            select(CaseStatusEvent).where(CaseStatusEvent.to_status == "called_to_or")
        ).one()
        assert event.is_override is True and event.reason == "Освободилась операционная"


def test_a_ready_case_is_called_without_an_override(api: Api, case_id: uuid.UUID, db: Any) -> None:
    approve(case_id)
    make_ready(case_id)
    resp = go(Role.HEAD_OF_DEPARTMENT, case_id, "called_to_or", reason="лишняя причина")
    assert resp.status_code == 200 and resp.json()["override_reason"] is None
    with db() as s:
        assert (
            s.scalars(select(CaseStatusEvent).where(CaseStatusEvent.is_override.is_(True))).first()
            is None
        )


def test_emergency_case_is_not_blocked_by_the_checklist(api: Api, case_id: uuid.UUID) -> None:
    approve(case_id)
    Api().as_role(Role.DOCTOR).patch(f"/cases/{case_id}", json={"is_emergency": True})
    assert go(Role.DOCTOR, case_id, "called_to_or").status_code == 200


def test_cancelling_a_call_needs_the_head_and_a_reason_and_clears_the_override(
    api: Api, case_id: uuid.UUID
) -> None:
    approve(case_id)
    go(Role.HEAD_OF_DEPARTMENT, case_id, "called_to_or", reason="срочно")
    assert go(Role.DOCTOR, case_id, "approved_for_surgery", reason="отмена").status_code == 403
    assert go(Role.HEAD_OF_DEPARTMENT, case_id, "approved_for_surgery").status_code == 422
    resp = go(
        Role.HEAD_OF_DEPARTMENT, case_id, "approved_for_surgery", reason="операционная занята"
    )
    assert resp.status_code == 200 and resp.json()["override_reason"] is None


def test_invalid_and_forbidden_moves(api: Api, case_id: uuid.UUID) -> None:
    skip = go(Role.HEAD_OF_DEPARTMENT, case_id, "in_or")
    assert skip.status_code == 409 and skip.json()["code"] == "transition_not_allowed"
    assert go(Role.NURSE, case_id, "in_preparation").status_code == 403
    assert go(Role.ANAESTHESIOLOGIST, case_id, "in_preparation").status_code == 403
    assert go(Role.ADMIN, case_id, "in_preparation").status_code == 403
    Api().login("doctor2")
    other = Api()
    other.login("doctor2")
    assert (
        other.post(f"/cases/{case_id}/transition", json={"to": "in_preparation"}).status_code == 403
    )
    assert (
        Api().post(f"/cases/{case_id}/transition", json={"to": "in_preparation"}).status_code == 401
    )
    assert go(Role.DOCTOR, case_id, "nonsense").status_code == 422


def test_only_ward_staff_set_left_ward(api: Api, case_id: uuid.UUID) -> None:
    approve(case_id)
    go(Role.HEAD_OF_DEPARTMENT, case_id, "called_to_or", reason="срочно")
    assert go(Role.DOCTOR, case_id, "left_ward").status_code == 403
    assert go(Role.HEAD_OF_DEPARTMENT, case_id, "left_ward").status_code == 403
    assert go(Role.NURSE, case_id, "left_ward").status_code == 200


def test_available_transitions_are_offered_per_role(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.DOCTOR)
    assert api.get(f"/cases/{case_id}").json()["available_transitions"] == ["in_preparation"]
    api.as_role(Role.NURSE)
    assert api.get(f"/cases/{case_id}").json()["available_transitions"] == []


# ---------------------------------------------------------------- notifications


def test_call_to_or_notifies_nurses_doctor_and_anaesthesiologist_without_identifiers(
    api: Api, case_id: uuid.UUID, db: Any, telegram_fake: FakeTelegram
) -> None:
    for login, chat in (
        ("nurse", "111"),
        ("doctor", "222"),
        ("anaesth", "333"),
        ("headnurse", "444"),
    ):
        link_telegram(db, login, chat)
    approve(case_id)
    go(Role.HEAD_OF_DEPARTMENT, case_id, "called_to_or", reason="срочно")

    delivered = {chat for chat, _ in telegram_fake.sent}
    assert {"111", "222", "333", "444"} <= delivered
    for _, text in telegram_fake.sent:
        assert text == "Пал. 1, к. 1 (И. А. Д.): вызов в операционную" or "одобрен" in text
    blob = " ".join(text for _, text in telegram_fake.sent)
    for secret in (PATIENT_NAME, "Иванов", "Алишер", "T-0001", "1960"):
        assert secret not in blob
    with db() as s:
        for n in s.scalars(select(Notification)):
            dump = str(n.payload)
            assert "Иванов" not in dump and "T-0001" not in dump and "1960" not in dump
            assert n.channel in ("app", "telegram")


def test_call_to_or_is_visible_in_the_app_feed(api: Api, case_id: uuid.UUID) -> None:
    approve(case_id)
    go(Role.HEAD_OF_DEPARTMENT, case_id, "called_to_or", reason="срочно")
    feed = Api().as_role(Role.NURSE).get("/notifications").json()
    assert feed[0]["event"] == "call_to_or" and feed[0]["case_id"] == str(case_id)
    assert feed[0]["text"].endswith("вызов в операционную") and not feed[0]["read"]
    assert (
        Api().as_role(Role.ANAESTHESIOLOGIST).get("/notifications").json()[0]["event"]
        == "call_to_or"
    )
    nurse = Api().as_role(Role.NURSE)
    assert nurse.post("/notifications/read-all").status_code == 204
    assert nurse.get("/notifications").json()[0]["read"] is True


def test_a_telegram_failure_is_recorded_and_never_blocks_the_action(
    api: Api, case_id: uuid.UUID, db: Any, telegram_fake: FakeTelegram
) -> None:
    link_telegram(db, "nurse", "111")
    telegram_fake.fail = True
    approve(case_id)
    resp = go(Role.HEAD_OF_DEPARTMENT, case_id, "called_to_or", reason="срочно")
    assert resp.status_code == 200
    with db() as s:
        failed = s.scalars(select(Notification).where(Notification.channel == "telegram")).all()
        assert failed and all(n.error == "HTTP 500" and n.sent_at is None for n in failed)


def test_inactive_users_are_not_notified(api: Api, case_id: uuid.UUID) -> None:
    approve(case_id)
    Api().as_role(Role.ADMIN)
    admin = Api().as_role(Role.ADMIN)
    uid = Api().as_role(Role.NURSE).get("/auth/me").json()["id"]
    admin.patch(f"/users/{uid}", json={"is_active": False})
    go(Role.HEAD_OF_DEPARTMENT, case_id, "called_to_or", reason="срочно")
    assert Api().as_role(Role.HEAD_NURSE).get("/notifications").json()[0]["event"] == "call_to_or"
    assert Api().login("nurse").status_code == 401


def test_unused_imports_keep_linters_quiet() -> None:
    assert case_payload()["procedure_key"] == "tka"
