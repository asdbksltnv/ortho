"""Synthetic demo data. Never contains real patients. Credentials go to stdout only."""

import argparse
import random
import secrets
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.db import get_session_factory
from app.domain.enums import CaseStatus, ItemStatus, Role
from app.models.case import Case, CaseStatusEvent, ChecklistItem, Patient
from app.models.user import User
from app.models.ward import Bed, Room, Ward
from app.services.cases import refresh_first_ready
from app.services.clock import local_today
from app.services.config_loader import AppConfig, get_config

DEMO_USERS = [
    ("doctor1", "Демо Врач Первый", Role.DOCTOR),
    ("doctor2", "Демо Врач Второй", Role.DOCTOR),
    ("nurse1", "Демо Медсестра Первая", Role.NURSE),
    ("anaesth1", "Демо Анестезиолог", Role.ANAESTHESIOLOGIST),
    ("head1", "Демо Заведующий", Role.HEAD_OF_DEPARTMENT),
    ("headnurse1", "Демо Старшая Медсестра", Role.HEAD_NURSE),
    ("admin1", "Демо Администратор", Role.ADMIN),
]

SURNAMES = ["Тестов", "Образцов", "Примеров", "Условный", "Пробный", "Макетов"]
NAMES = ["Алишер", "Дилшод", "Мария", "Сардор", "Елена", "Тимур"]
PATRONYMICS = ["Тестович", "Образцович", "Примерович", "Условович", "Пробович", "Макетович"]

# (status, ready_state) for 12 synthetic cases
CASE_PLAN: list[tuple[CaseStatus, str]] = [
    (CaseStatus.ADMITTED, "none"),
    (CaseStatus.ADMITTED, "some"),
    (CaseStatus.IN_PREPARATION, "some"),
    (CaseStatus.IN_PREPARATION, "some"),
    (CaseStatus.IN_PREPARATION, "problem"),
    (CaseStatus.IN_PREPARATION, "almost"),
    (CaseStatus.APPROVED_FOR_SURGERY, "all"),
    (CaseStatus.APPROVED_FOR_SURGERY, "almost"),
    (CaseStatus.CALLED_TO_OR, "all"),
    (CaseStatus.IN_OR, "all"),
    (CaseStatus.POST_OP, "all"),
    (CaseStatus.POST_OP, "all"),
]
PROCEDURES = ["tka", "tha", "arthroscopy", "plate_osteosynthesis", "im_nailing"]


def seed_users(session: Session) -> dict[str, str]:
    credentials: dict[str, str] = {}
    for login, name, role in DEMO_USERS:
        password = secrets.token_urlsafe(12)
        session.add(
            User(
                login=login, full_name=name, role=role.value, password_hash=hash_password(password)
            )
        )
        credentials[login] = password
    session.flush()
    return credentials


def seed_ward(session: Session) -> list[Bed]:
    ward = Ward(name="Ортопедическое отделение (демо)")
    session.add(ward)
    session.flush()
    beds: list[Bed] = []
    for n in range(1, 5):
        room = Room(
            ward_id=ward.id, name=f"Пал. {n}", floor=2, position_x=(n - 1) * 100, position_y=0
        )
        session.add(room)
        session.flush()
        for b in range(1, 4):
            bed = Bed(room_id=room.id, label=f"к. {b}")
            session.add(bed)
            beds.append(bed)
    session.flush()
    return beds


def _statuses_for(plan: str, keys: list[str], rng: random.Random) -> dict[str, ItemStatus]:
    if plan == "all":
        return {k: ItemStatus.DONE for k in keys}
    if plan == "none":
        return {k: ItemStatus.NOT_STARTED for k in keys}
    out = {k: ItemStatus.NOT_STARTED for k in keys}
    done_count = {"some": 3, "problem": 2, "almost": len(keys) - 2}[plan]
    for k in rng.sample(keys, k=min(done_count, len(keys))):
        out[k] = ItemStatus.DONE
    if plan == "problem":
        out[next(k for k in keys if out[k] is ItemStatus.NOT_STARTED)] = ItemStatus.PROBLEM
    if plan in {"some", "almost"}:
        pending = [k for k in keys if out[k] is ItemStatus.NOT_STARTED]
        if pending:
            out[pending[0]] = ItemStatus.PENDING
    return out


def seed_cases(session: Session, beds: list[Bed], config: AppConfig) -> None:
    rng = random.Random(20260101)  # noqa: S311 - deterministic demo layout, not security
    doctors = list(session.scalars(select(User).where(User.role == Role.DOCTOR.value)))
    nurse = session.scalars(select(User).where(User.role == Role.NURSE.value)).first()
    keys = [d.key for d in config.checklist.items]
    today = local_today()
    for i, (status, plan) in enumerate(CASE_PLAN):
        patient = Patient(
            full_name=f"{SURNAMES[i % 6]} {NAMES[(i + 2) % 6]} {PATRONYMICS[(i + 4) % 6]}",
            birth_date=date(1950 + (i * 4) % 40, 1 + i % 12, 1 + (i * 3) % 27),
            sex="F" if i % 2 else "M",
            medical_record_number=f"DEMO-{i + 1:04d}",
        )
        session.add(patient)
        session.flush()
        case = Case(
            patient_id=patient.id,
            bed_id=beds[i].id,
            treating_doctor_id=doctors[i % len(doctors)].id,
            procedure_key=PROCEDURES[i % len(PROCEDURES)],
            side=rng.choice(["left", "right"]),
            planned_surgery_date=today + timedelta(days=1 if i % 3 == 0 else 2 + i % 4),
            status=status.value,
            takes_anticoagulant=(i == 5),
        )
        session.add(case)
        session.flush()
        statuses = _statuses_for(plan, keys, rng)
        for key in keys:
            session.add(
                ChecklistItem(
                    case_id=case.id,
                    key=key,
                    status=statuses[key].value,
                    updated_by=nurse.id if nurse else None,
                )
            )
        session.add(
            CaseStatusEvent(
                case_id=case.id,
                from_status=None,
                to_status=status.value,
                user_id=doctors[0].id,
            )
        )
        session.flush()
        session.refresh(case)
        refresh_first_ready(case, config)


def seed_if_empty() -> dict[str, str] | None:
    """Seeds demo data when no users exist. Returns the generated credentials, else None."""
    with get_session_factory()() as session:
        if session.scalar(select(func.count()).select_from(User)):
            return None
        config = get_config()
        credentials = seed_users(session)
        beds = seed_ward(session)
        seed_cases(session, beds, config)
        session.commit()
        return credentials


def print_credentials(credentials: dict[str, str]) -> None:
    print("=== DEMO CREDENTIALS (synthetic data only; shown once in this log) ===", flush=True)
    for login, password in credentials.items():
        print(f"  {login}: {password}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed synthetic demo data")
    parser.add_argument("--if-empty", action="store_true", help="only seed when there are no users")
    parser.parse_args()
    credentials = seed_if_empty()
    if credentials is None:
        print("seed: users already exist, nothing to do", flush=True)
    else:
        print_credentials(credentials)


if __name__ == "__main__":
    main()
