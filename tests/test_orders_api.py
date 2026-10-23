import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.domain.enums import Role
from tests.conftest import Api, FakeTelegram, link_telegram
from tests.helpers import make_ready


def uid(role: Role) -> str:
    return Api().as_role(role).get("/auth/me").json()["id"]


def order_body(role_assignee: Role = Role.NURSE, **kw: Any) -> dict[str, Any]:
    body = {"type": "lab", "item": "ОАК", "assignee_id": uid(role_assignee)}
    body.update(kw)
    return body


def create(api: Api, case: uuid.UUID, **kw: Any) -> dict[str, Any]:
    api.as_role(Role.DOCTOR)
    resp = api.post(f"/cases/{case}/orders", json=order_body(**kw))
    assert resp.status_code == 201, resp.text
    return resp.json()


def set_status(role: Role, order: str, status: str) -> Any:
    return Api().as_role(role).patch(f"/orders/{order}/status", json={"status": status})


def test_doctor_creates_an_order_and_it_shows_initials_not_names(
    api: Api, case_id: uuid.UUID
) -> None:
    order = create(api, case_id)
    assert order["status"] == "ordered" and order["assignee_name"] == "Тест nurse"
    assert order["case_label"] == "Пал. 1, к. 1 (И. А. Д.)" and "Иванов" not in str(order)
    assert api.get(f"/cases/{case_id}/orders").json()[0]["id"] == order["id"]


@pytest.mark.parametrize("role", [Role.NURSE, Role.HEAD_NURSE, Role.ANAESTHESIOLOGIST, Role.ADMIN])
def test_only_doctors_create_orders(api: Api, case_id: uuid.UUID, role: Role) -> None:
    api.as_role(role)
    assert api.post(f"/cases/{case_id}/orders", json=order_body()).status_code == 403


def test_a_doctor_cannot_order_for_another_doctors_patient_but_the_head_can(
    api: Api, case_id: uuid.UUID
) -> None:
    other = Api()
    other.login("doctor2")
    assert other.post(f"/cases/{case_id}/orders", json=order_body()).status_code == 403
    head = Api().as_role(Role.HEAD_OF_DEPARTMENT)
    assert head.post(f"/cases/{case_id}/orders", json=order_body()).status_code == 201


def test_validation(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.DOCTOR)
    assert api.post(f"/cases/{case_id}/orders", json=order_body(type="surgery")).status_code == 422
    assert api.post(f"/cases/{case_id}/orders", json=order_body(item="")).status_code == 422
    bad_user = api.post(f"/cases/{case_id}/orders", json=order_body(assignee_id=str(uuid.uuid4())))
    assert bad_user.status_code == 422 and bad_user.json()["code"] == "assignee_invalid"
    admin_assignee = api.post(f"/cases/{case_id}/orders", json=order_body(role_assignee=Role.ADMIN))
    assert admin_assignee.status_code == 422
    unknown_key = api.post(f"/cases/{case_id}/orders", json=order_body(linked_checklist_key="nope"))
    assert unknown_key.status_code == 422


def test_quick_order_sets_from_config(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.DOCTOR)
    sets = {s["key"]: s for s in api.get("/order-sets").json()}
    assert sets["control_xray"]["name_ru"] == "Контрольная рентгенография"
    assert sets["repeat_cbc"]["name_ru"] == "Повторный ОАК"
    created = api.post(
        f"/cases/{case_id}/orders/from-set",
        json={"set_key": "control_xray", "assignee_id": uid(Role.NURSE), "created_at_round": True},
    ).json()
    api.as_role(Role.DOCTOR)
    assert [(o["type"], o["item"], o["created_at_round"]) for o in created] == [
        ("imaging", "Контрольная рентгенография", True)
    ]
    assert (
        api.post(
            f"/cases/{case_id}/orders/from-set",
            json={"set_key": "nope", "assignee_id": uid(Role.NURSE)},
        ).status_code
        == 404
    )


def test_status_flow_and_who_may_review(api: Api, case_id: uuid.UUID) -> None:
    order = create(api, case_id)
    oid = order["id"]
    assert set_status(Role.NURSE, oid, "reviewed").status_code == 409  # cannot skip ahead
    assert set_status(Role.NURSE, oid, "in_progress").status_code == 200
    assert set_status(Role.NURSE, oid, "result_available").status_code == 200
    assert set_status(Role.NURSE, oid, "reviewed").status_code == 403  # only a doctor reviews
    assert set_status(Role.HEAD_NURSE, oid, "reviewed").status_code == 403
    assert set_status(Role.ANAESTHESIOLOGIST, oid, "reviewed").status_code == 403
    assert set_status(Role.ADMIN, oid, "in_progress").status_code == 403
    other = Api()
    other.login("doctor2")
    assert other.patch(f"/orders/{oid}/status", json={"status": "reviewed"}).status_code == 403
    done = set_status(Role.DOCTOR, oid, "reviewed")
    assert (
        done.status_code == 200
        and done.json()["status"] == "reviewed"
        and done.json()["next_statuses"] == []
    )
    assert set_status(Role.DOCTOR, oid, "cancelled").status_code == 409  # terminal


def test_next_statuses_are_filtered_for_the_viewer(api: Api, case_id: uuid.UUID) -> None:
    order = create(api, case_id)
    set_status(Role.NURSE, order["id"], "in_progress")
    set_status(Role.NURSE, order["id"], "result_available")
    nurse_view = Api().as_role(Role.NURSE).get(f"/cases/{case_id}/orders").json()[0]
    doctor_view = Api().as_role(Role.DOCTOR).get(f"/cases/{case_id}/orders").json()[0]
    assert nurse_view["next_statuses"] == []
    assert set(doctor_view["next_statuses"]) == {"reviewed", "cancelled"}


def test_only_a_doctor_cancels(api: Api, case_id: uuid.UUID) -> None:
    oid = create(api, case_id)["id"]
    assert set_status(Role.NURSE, oid, "cancelled").status_code == 403
    assert set_status(Role.DOCTOR, oid, "cancelled").json()["status"] == "cancelled"


def test_an_assigned_anaesthesiologist_can_work_their_own_consult(
    api: Api, case_id: uuid.UUID
) -> None:
    oid = create(
        api,
        case_id,
        type="consult",
        item="Осмотр анестезиолога",
        role_assignee=Role.ANAESTHESIOLOGIST,
    )["id"]
    assert set_status(Role.ANAESTHESIOLOGIST, oid, "in_progress").status_code == 200
    assert set_status(Role.ANAESTHESIOLOGIST, oid, "result_available").status_code == 200


def test_assignment_and_ready_results_notify_without_identifiers(
    api: Api, case_id: uuid.UUID, db: Any, telegram_fake: FakeTelegram
) -> None:
    link_telegram(db, "nurse", "111")
    link_telegram(db, "doctor", "222")
    oid = create(api, case_id)["id"]
    assert ("111", "Пал. 1, к. 1 (И. А. Д.): новое назначение (анализы)") in telegram_fake.sent
    set_status(Role.NURSE, oid, "in_progress")
    set_status(Role.NURSE, oid, "result_available")
    assert ("222", "Пал. 1, к. 1 (И. А. Д.): анализы готовы") in telegram_fake.sent
    assert all(
        "Иванов" not in t and "ОАК" not in t for _, t in telegram_fake.sent
    )  # no item text either


def test_assigning_to_yourself_does_not_notify_you(api: Api, case_id: uuid.UUID) -> None:
    create(api, case_id, role_assignee=Role.DOCTOR)
    assert Api().as_role(Role.DOCTOR).get("/notifications").json() == []


def test_linked_order_keeps_the_checklist_item_pending_until_reviewed(
    api: Api, case_id: uuid.UUID
) -> None:
    make_ready(case_id)
    api.as_role(Role.DOCTOR)
    assert api.get(f"/cases/{case_id}").json()["readiness"]["ready"] is True
    oid = create(api, case_id, linked_checklist_key="labs_core")["id"]
    case = Api().as_role(Role.DOCTOR).get(f"/cases/{case_id}").json()
    item = next(i for i in case["items"] if i["key"] == "labs_core")
    assert item["status"] == "pending" and case["readiness"]["blocking"] == ["labs_core"]
    # the nurse cannot mark it done while the linked order is open
    nurse = Api().as_role(Role.NURSE)
    blocked = nurse.patch(f"/cases/{case_id}/checklist/labs_core", json={"status": "done"})
    assert blocked.status_code == 409 and blocked.json()["code"] == "linked_orders_pending"
    set_status(Role.NURSE, oid, "in_progress")
    set_status(Role.NURSE, oid, "result_available")
    assert (
        nurse.patch(f"/cases/{case_id}/checklist/labs_core", json={"status": "done"}).status_code
        == 409
    )
    set_status(Role.DOCTOR, oid, "reviewed")
    assert (
        nurse.patch(f"/cases/{case_id}/checklist/labs_core", json={"status": "done"}).status_code
        == 200
    )


def test_cancelled_linked_order_no_longer_blocks(api: Api, case_id: uuid.UUID) -> None:
    oid = create(api, case_id, linked_checklist_key="labs_core")["id"]
    set_status(Role.DOCTOR, oid, "cancelled")
    nurse = Api().as_role(Role.NURSE)
    assert (
        nurse.patch(f"/cases/{case_id}/checklist/labs_core", json={"status": "done"}).status_code
        == 200
    )


def test_my_tasks_lists_open_assignments_and_results_to_review(
    api: Api, case_id: uuid.UUID
) -> None:
    mine = create(api, case_id)
    create(api, case_id, role_assignee=Role.HEAD_NURSE)
    nurse = Api().as_role(Role.NURSE)
    tasks = nurse.get("/tasks").json()
    assert [t["id"] for t in tasks] == [mine["id"]]
    set_status(Role.NURSE, mine["id"], "in_progress")
    set_status(Role.NURSE, mine["id"], "result_available")
    assert nurse.get("/tasks").json() == []  # waiting for the doctor now
    doctor_tasks = Api().as_role(Role.DOCTOR).get("/tasks").json()
    assert [t["id"] for t in doctor_tasks] == [mine["id"]] and doctor_tasks[0][
        "status"
    ] == "result_available"
    other = Api()
    other.login("doctor2")
    assert other.get("/tasks").json() == []  # not their patient
    assert Api().as_role(Role.HEAD_OF_DEPARTMENT).get("/tasks").json()[0]["id"] == mine["id"]
    assert Api().as_role(Role.ADMIN).get("/tasks").status_code == 403


def test_round_summary_groups_what_was_ordered_at_rounds(api: Api, case_id: uuid.UUID) -> None:
    start = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    create(api, case_id, created_at_round=True)
    create(api, case_id, created_at_round=False, item="вне обхода")
    api.as_role(Role.DOCTOR)
    rows = api.get("/orders/round-summary", params={"since": start}).json()
    assert [(r["item"], r["assignee_name"], r["case_label"]) for r in rows] == [
        ("ОАК", "Тест nurse", "Пал. 1, к. 1 (И. А. Д.)")
    ]
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    assert api.get("/orders/round-summary", params={"since": future}).json() == []
    assert (
        Api().as_role(Role.NURSE).get("/orders/round-summary", params={"since": start}).status_code
        == 403
    )


def test_orders_are_audited_without_the_item_text(api: Api, case_id: uuid.UUID) -> None:
    create(api, case_id, item="СЕКРЕТНОЕ НАЗНАЧЕНИЕ")
    rows = Api().as_role(Role.HEAD_OF_DEPARTMENT).get("/audit?entity=order").json()["items"]
    assert rows and "СЕКРЕТНОЕ" not in str(rows)


def test_nurses_and_anaesthesiologists_can_read_orders(api: Api, case_id: uuid.UUID) -> None:
    create(api, case_id)
    for role in (Role.NURSE, Role.ANAESTHESIOLOGIST, Role.HEAD_NURSE):
        assert len(Api().as_role(role).get(f"/cases/{case_id}/orders").json()) == 1
    assert Api().as_role(Role.ADMIN).get(f"/cases/{case_id}/orders").status_code == 403
