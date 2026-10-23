import uuid
from datetime import date, timedelta
from typing import Any

import pytest
from sqlalchemy import select

from app.domain.enums import Role
from app.models.case import Notification
from app.services import jobs
from app.services.config_loader import get_config
from tests.conftest import Api, FakeTelegram, case_payload, link_telegram
from tests.helpers import make_ready, move_to_postop, set_case
from tests.test_postop_api import entry_data

TODAY = date(2026, 3, 10)
TOMORROW = TODAY + timedelta(days=1)


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    for target in (
        "app.services.cases",
        "app.services.board",
        "app.services.postop",
        "app.api.postop",
    ):
        monkeypatch.setattr(f"{target}.local_today", lambda: TODAY)


def texts(db: Any, event: str, channel: str = "app") -> list[tuple[Any, str]]:
    with db() as s:
        rows = s.scalars(
            select(Notification).where(Notification.event == event, Notification.channel == channel)
        ).all()
        return [(n.user_id, n.payload["text"]) for n in rows]


def second_case(world: dict[str, Any], doctor: str = "doctor") -> uuid.UUID:
    api = Api().as_role(Role.HEAD_OF_DEPARTMENT)
    doc_id = world[doctor]
    resp = api.post(
        "/cases",
        json=case_payload(
            patient={
                "full_name": "Петров Иван Иванович",
                "birth_date": "1970-02-02",
                "sex": "M",
                "medical_record_number": "T-2",
            },
            treating_doctor_id=str(doc_id),
            bed_id=str(world["beds"][1]),
        ),
    )
    assert resp.status_code == 201
    return uuid.UUID(resp.json()["id"])


# -------------------------------------------------------------- digest


def test_digest_lists_tomorrows_cases_that_are_not_ready(
    api: Api, world: dict[str, Any], case_id: uuid.UUID, db: Any, telegram_fake: FakeTelegram
) -> None:
    ready = second_case(world)
    make_ready(ready)
    Api().as_role(Role.DOCTOR).patch(
        f"/cases/{case_id}", json={"planned_surgery_date": TOMORROW.isoformat()}
    )
    Api().as_role(Role.HEAD_OF_DEPARTMENT).patch(
        f"/cases/{ready}", json={"planned_surgery_date": TOMORROW.isoformat()}
    )
    link_telegram(db, "doctor", "222")
    link_telegram(db, "headnurse", "444")
    with db() as s:
        recipients = jobs.run_daily_digest(s, get_config(), TODAY)
        s.commit()
    assert recipients == 2  # the doctor and the head nurse
    doctor_msg = dict(telegram_fake.sent)["222"]
    assert doctor_msg.startswith("Завтра не готовы:")
    assert "Пал. 1, к. 1 (И. А. Д.): не хватает — Документы, Анализы, Согласие" in doctor_msg
    assert "Пал. 1, к. 2" not in doctor_msg  # the Ready case is not listed
    assert dict(telegram_fake.sent)["444"] == doctor_msg
    for secret in ("Иванов", "Петров", "T-0001", "T-2", "1960"):
        assert secret not in doctor_msg


def test_digest_only_goes_to_each_cases_own_doctor(
    api: Api, world: dict[str, Any], case_id: uuid.UUID, db: Any
) -> None:
    other = second_case(world, doctor="doctor2")
    for cid in (case_id, other):
        Api().as_role(Role.HEAD_OF_DEPARTMENT).patch(
            f"/cases/{cid}", json={"planned_surgery_date": TOMORROW.isoformat()}
        )
    with db() as s:
        jobs.run_daily_digest(s, get_config(), TODAY)
        s.commit()
    mine = texts(db, "digest")
    assert len(mine) == 3  # each doctor for their own case, plus the head nurse for both
    texts_only = [t for _, t in mine]
    assert sum("(П. И. И.)" in t and "(И. А. Д.)" not in t for t in texts_only) == 1
    assert sum("(И. А. Д.)" in t and "(П. И. И.)" not in t for t in texts_only) == 1
    assert sum("(И. А. Д.)" in t and "(П. И. И.)" in t for t in texts_only) == 1


def test_no_digest_when_nothing_is_missing(api: Api, case_id: uuid.UUID, db: Any) -> None:
    make_ready(case_id)
    Api().as_role(Role.DOCTOR).patch(
        f"/cases/{case_id}", json={"planned_surgery_date": TOMORROW.isoformat()}
    )
    Api().as_role(Role.HEAD_OF_DEPARTMENT).post(
        f"/cases/{case_id}/transition", json={"to": "in_preparation"}
    )
    with db() as s:
        assert jobs.run_daily_digest(s, get_config(), TODAY) == 0
    assert texts(db, "digest") == []


def test_digest_ignores_other_days_and_discharged_cases(
    api: Api, case_id: uuid.UUID, db: Any
) -> None:
    Api().as_role(Role.DOCTOR).patch(
        f"/cases/{case_id}", json={"planned_surgery_date": TODAY.isoformat()}
    )
    with db() as s:
        assert jobs.run_daily_digest(s, get_config(), TODAY) == 0
    set_case(db, case_id, planned_surgery_date=TOMORROW, status="discharged")
    with db() as s:
        assert jobs.run_daily_digest(s, get_config(), TODAY) == 0


# -------------------------------------------------------------- lab expiry


def add_lab(case: uuid.UUID, collected: str = "2026-03-01T08:00:00+00:00") -> Any:
    return (
        Api()
        .as_role(Role.NURSE)
        .post(
            f"/cases/{case}/labs",
            json={"lab_code": "hiv", "result_text": "отр.", "collected_at": collected},
        )
    )


def test_lab_expiry_is_silent_while_validity_is_unconfigured(
    api: Api, case_id: uuid.UUID, db: Any
) -> None:
    Api().as_role(Role.DOCTOR).patch(
        f"/cases/{case_id}", json={"planned_surgery_date": "2026-06-01"}
    )
    add_lab(case_id)  # validity_days is null in the shipped config: no valid_until
    with db() as s:
        assert jobs.run_lab_expiry(s, get_config()) == 0


def test_lab_expiry_flags_results_that_lapse_before_surgery_once(
    api: Api,
    case_id: uuid.UUID,
    db: Any,
    monkeypatch: pytest.MonkeyPatch,
    telegram_fake: FakeTelegram,
) -> None:
    lab = next(x for x in get_config().labs.labs if x.code == "hiv")
    monkeypatch.setattr(lab, "validity_days", 10)
    link_telegram(db, "doctor", "222")
    Api().as_role(Role.DOCTOR).patch(
        f"/cases/{case_id}", json={"planned_surgery_date": "2026-03-20"}
    )
    assert add_lab(case_id).json()["valid_until"] == "2026-03-11"
    with db() as s:
        assert jobs.run_lab_expiry(s, get_config()) == 1
        s.commit()
    assert telegram_fake.sent == [
        ("222", "Пал. 1, к. 1 (И. А. Д.): срок действия анализа «ВИЧ» истекает до операции")
    ]
    with db() as s:
        assert jobs.run_lab_expiry(s, get_config()) == 0  # not repeated
    Api().as_role(Role.DOCTOR).patch(
        f"/cases/{case_id}", json={"planned_surgery_date": "2026-03-11"}
    )
    add_lab(case_id, "2026-03-05T08:00:00+00:00")  # valid until the 15th: fine
    with db() as s:
        assert jobs.run_lab_expiry(s, get_config()) == 0


# -------------------------------------------------------------- alerts and reminders


def test_alert_scan_catches_thresholds_set_after_the_entry(
    api: Api, case_id: uuid.UUID, db: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    move_to_postop(db, case_id, TODAY - timedelta(days=1))
    resp = (
        Api()
        .as_role(Role.DOCTOR)
        .post(
            f"/cases/{case_id}/postop",
            json={
                "data": entry_data(
                    vitals={"bp": "120/80", "pulse": 76, "rr": 16, "spo2": 98, "temp": 39}
                )
            },
        )
    )
    assert resp.json()["alerts"] == []
    with db() as s:
        assert jobs.run_alert_scan(s, get_config()) == 0
    monkeypatch.setattr(get_config().alerts.thresholds, "temperature_max", 37.5)
    with db() as s:
        assert jobs.run_alert_scan(s, get_config()) == 1
        s.commit()
    assert (
        texts(db, "postop_alert")[0][1]
        == "Пал. 1, к. 1 (И. А. Д.): послеоперационный сигнал — температура выше порога"
    )
    with db() as s:
        assert jobs.run_alert_scan(s, get_config()) == 0


def test_reminder_only_for_post_op_cases_without_todays_entry(
    api: Api, world: dict[str, Any], case_id: uuid.UUID, db: Any
) -> None:
    other = second_case(world)
    move_to_postop(db, case_id, TODAY - timedelta(days=1))
    move_to_postop(db, other, TODAY - timedelta(days=1))
    Api().as_role(Role.HEAD_OF_DEPARTMENT).post(
        f"/cases/{other}/postop", json={"data": entry_data()}
    )
    with db() as s:
        assert jobs.run_postop_reminder(s, TODAY) == 1
        s.commit()
    assert (
        texts(db, "postop_reminder")[0][1]
        == "Пал. 1, к. 1 (И. А. Д.): нет дневной записи за сегодня"
    )
    set_case(db, case_id, status="returned_to_ward")
    with db() as s:
        assert jobs.run_postop_reminder(s, TODAY) == 0  # only cases in post_op are reminded


def test_job_entry_points_run_and_log(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    from app import db as db_module
    from app.settings import get_settings

    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'j.db'}")
    get_settings.cache_clear()
    db_module.get_engine.cache_clear()
    db_module.get_session_factory.cache_clear()
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(cfg, "head")
    from app.jobs import alert_scan, daily_digest, lab_expiry, postop_reminder

    for job in (daily_digest, lab_expiry, alert_scan, postop_reminder):
        job.main()  # empty database: runs cleanly
    db_module.get_engine.cache_clear()
    db_module.get_session_factory.cache_clear()
    get_settings.cache_clear()


def test_scheduler_registers_the_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.scheduler import start_scheduler

    scheduler = start_scheduler()
    try:
        assert {j.id for j in scheduler.get_jobs()} == {
            "daily_digest",
            "lab_expiry",
            "postop_reminder",
            "alert_scan",
        }
        digest = scheduler.get_job("daily_digest")
        assert "hour='18'" in repr(digest.trigger) and "Asia/Tashkent" in repr(digest.trigger)
    finally:
        scheduler.shutdown(wait=False)
