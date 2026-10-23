import csv
import io
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from app.domain.enums import Role
from app.domain.kpi import eve_cutoff, median_hours, most_frequent, was_not_ready_the_evening_before
from app.models.case import Case
from tests.conftest import Api, case_payload
from tests.helpers import make_ready, set_case

TZ = ZoneInfo("Asia/Tashkent")


def test_median_hours() -> None:
    assert median_hours([]) is None
    assert median_hours([timedelta(hours=2)]) == 2.0
    assert median_hours([timedelta(hours=1), timedelta(hours=9), timedelta(hours=3)]) == 3.0
    assert median_hours([timedelta(hours=1), timedelta(hours=2)]) == 1.5
    assert (
        median_hours([timedelta(hours=-5), timedelta(hours=4)]) == 4.0
    )  # negative spans are ignored


def test_eve_cutoff_is_18_00_local_the_day_before() -> None:
    assert eve_cutoff(date(2026, 3, 11), TZ) == datetime(2026, 3, 10, 13, 0, tzinfo=UTC)  # UTC+5


def test_not_ready_the_evening_before_boundaries() -> None:
    planned = date(2026, 3, 11)
    cutoff = eve_cutoff(planned, TZ)
    assert was_not_ready_the_evening_before(None, planned, TZ) is True
    assert was_not_ready_the_evening_before(cutoff + timedelta(minutes=1), planned, TZ) is True
    assert was_not_ready_the_evening_before(cutoff, planned, TZ) is False
    assert was_not_ready_the_evening_before(cutoff - timedelta(days=2), planned, TZ) is False


def test_most_frequent_orders_by_count_then_name() -> None:
    assert most_frequent(["b", "a", "b", "c", "a", "b"]) == [("b", 3), ("a", 2), ("c", 1)]
    assert most_frequent(["z", "a"]) == [("a", 1), ("z", 1)]
    assert most_frequent([]) == []


def second_case(world: dict[str, Any], mrn: str, bed: int) -> uuid.UUID:
    api = Api().as_role(Role.HEAD_OF_DEPARTMENT)
    resp = api.post(
        "/cases",
        json=case_payload(
            patient={
                "full_name": "Петров Иван",
                "birth_date": "1970-01-01",
                "sex": "M",
                "medical_record_number": mrn,
            },
            treating_doctor_id=str(world["doctor"]),
            bed_id=str(world["beds"][bed]),
        ),
    )
    return uuid.UUID(resp.json()["id"])


def test_kpis_over_a_small_ward(
    api: Api, world: dict[str, Any], case_id: uuid.UUID, db: Any
) -> None:
    other = second_case(world, "T-2", 1)
    make_ready(other)  # becomes Ready now
    with db() as s:
        s.get(Case, other).admitted_at = datetime.now(UTC) - timedelta(hours=10)  # type: ignore[union-attr]
        s.commit()
    # `other` called with an override while not ready is covered separately; here: planned yesterday, ready late
    yesterday = date.today() - timedelta(days=1)
    set_case(db, other, planned_surgery_date=yesterday, status="post_op")
    set_case(db, case_id, planned_surgery_date=yesterday, status="post_op")  # never Ready

    kpis = Api().as_role(Role.HEAD_OF_DEPARTMENT).get("/kpi").json()
    assert kpis["cases_total"] == 2 and kpis["ready_cases"] == 1
    assert 9.9 <= kpis["median_hours_to_ready"] <= 10.1
    assert kpis["surgeries_checked"] == 2
    # `case_id` never became Ready; `other` became Ready only after the evening cutoff
    assert len(kpis["not_ready_eve"]) == 2
    items = {i["key"]: i["count"] for i in kpis["blocking_items"]}
    assert items["docs"] == 1 and "labs_core" in items  # `case_id` still misses items; `other` none
    assert kpis["overrides"] == []


def test_overrides_are_listed_with_initials_only(api: Api, case_id: uuid.UUID) -> None:
    head = Api().as_role(Role.HEAD_OF_DEPARTMENT)
    assert (
        Api()
        .as_role(Role.DOCTOR)
        .post(f"/cases/{case_id}/transition", json={"to": "in_preparation"})
        .status_code
        == 200
    )
    head.post(
        f"/cases/{case_id}/transition",
        json={"to": "approved_for_surgery", "planned_surgery_date": "2026-03-11"},
    )
    head.post(
        f"/cases/{case_id}/transition",
        json={"to": "called_to_or", "reason": "Освободилась операционная"},
    )
    kpis = head.get("/kpi").json()
    assert len(kpis["overrides"]) == 1
    row = kpis["overrides"][0]
    assert (
        row["reason"] == "Освободилась операционная"
        and row["case_label"] == "Пал. 1, к. 1 (И. А. Д.)"
    )
    assert "Иванов" not in str(kpis)


def test_emergency_cases_are_not_counted_as_not_ready_the_evening_before(
    api: Api, case_id: uuid.UUID, db: Any
) -> None:
    set_case(
        db,
        case_id,
        planned_surgery_date=date.today() - timedelta(days=1),
        status="post_op",
        is_emergency=True,
    )
    kpis = Api().as_role(Role.HEAD_NURSE).get("/kpi").json()
    assert kpis["surgeries_checked"] == 0 and kpis["not_ready_eve"] == []


def test_period_filter(api: Api, case_id: uuid.UUID) -> None:
    head = Api().as_role(Role.HEAD_OF_DEPARTMENT)
    assert (
        head.get("/kpi", params={"from": "2020-01-01", "to": "2020-01-31"}).json()["cases_total"]
        == 0
    )
    assert head.get("/kpi", params={"from": "2026-02-01", "to": "2026-01-01"}).status_code == 422
    assert head.get("/kpi", params={"from": "2010-01-01", "to": "2026-01-01"}).status_code == 422


@pytest.mark.parametrize("role", [Role.DOCTOR, Role.NURSE, Role.ANAESTHESIOLOGIST, Role.ADMIN])
def test_only_head_roles_read_kpis(api: Api, role: Role) -> None:
    for path in ("/kpi", "/kpi/export.csv"):
        assert Api().as_role(role).get(path).status_code == 403
    assert Api().get("/kpi").status_code == 401
    assert Api().as_role(Role.HEAD_NURSE).get("/kpi").status_code == 200


def test_csv_export_has_aggregates_only_and_is_audited(api: Api, case_id: uuid.UUID) -> None:
    head = Api().as_role(Role.HEAD_OF_DEPARTMENT)
    Api().as_role(Role.DOCTOR).post(f"/cases/{case_id}/transition", json={"to": "in_preparation"})
    head.post(
        f"/cases/{case_id}/transition",
        json={"to": "approved_for_surgery", "planned_surgery_date": "2026-03-11"},
    )
    head.post(
        f"/cases/{case_id}/transition", json={"to": "called_to_or", "reason": "СЕКРЕТНАЯ ПРИЧИНА"}
    )
    resp = head.get("/kpi/export.csv")
    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/csv")
    assert resp.headers["content-disposition"].startswith('attachment; filename="kpi_')
    text = resp.text
    for secret in ("Иванов", "Алишер", "T-0001", "СЕКРЕТНАЯ", "Пал.", "И. А. Д.", str(case_id)):
        assert secret not in text, secret
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0] == ["metric", "key", "value"]
    metrics = {r[0]: r[2] for r in rows if r[1] == ""}
    assert metrics["cases_total"] == "1" and metrics["overrides_count"] == "1"
    assert any(r[0] == "blocking_item_cases" and r[1] == "docs" for r in rows)
    audit = head.get("/audit?action=export").json()["items"]
    assert audit and audit[0]["entity"] == "kpi_csv" and audit[0]["user_name"] == "Тест head"


def test_audit_viewer_shows_user_names(api: Api, case_id: uuid.UUID) -> None:
    rows = Api().as_role(Role.HEAD_OF_DEPARTMENT).get("/audit?entity=case").json()["items"]
    assert rows[0]["user_name"] == "Тест doctor"
