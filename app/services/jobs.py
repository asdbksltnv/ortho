"""Scheduled work as plain functions over a session: testable without a clock or network."""

import uuid
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.enums import CaseStatus, Role
from app.domain.postop import PostOpData
from app.models.case import Case, LabResult, Notification, PostOpEntry
from app.models.user import User
from app.models.ward import Bed
from app.services.cases import compute_case_readiness
from app.services.config_loader import AppConfig
from app.services.notify import case_label, notify, users_with_roles
from app.services.postop import RECORDING_STATUSES, thresholds

_CASE_LOAD = (
    selectinload(Case.checklist_items),
    selectinload(Case.patient),
    selectinload(Case.bed).selectinload(Bed.room),
    selectinload(Case.treating_doctor),
)


def run_daily_digest(session: Session, config: AppConfig, today: date) -> int:
    """18:00 digest: tomorrow's cases that are not Ready, with the missing items.

    Sent to each treating doctor (their own cases) and to the head nurse (all). Returns the number
    of recipients messaged.
    """
    tomorrow = today + timedelta(days=1)
    cases = session.scalars(
        select(Case)
        .where(
            Case.planned_surgery_date == tomorrow,
            Case.status != CaseStatus.DISCHARGED.value,
        )
        .options(*_CASE_LOAD)
    ).all()
    labels = {d.key: d.short_label_ru for d in config.checklist.items}
    lines_by_doctor: dict[uuid.UUID, list[str]] = defaultdict(list)
    doctors: dict[uuid.UUID, User] = {}
    all_lines: list[str] = []
    for case in cases:
        readiness = compute_case_readiness(case, config)
        if readiness.ready:
            continue
        missing = ", ".join(labels.get(k, k) for k in readiness.blocking)
        line = f"{case_label(case)}: не хватает — {missing}"
        lines_by_doctor[case.treating_doctor_id].append(line)
        doctors[case.treating_doctor_id] = case.treating_doctor
        all_lines.append(line)

    sent = 0
    for doctor_id, lines in lines_by_doctor.items():
        notify(session, [doctors[doctor_id]], "digest", "Завтра не готовы:\n" + "\n".join(lines))
        sent += 1
    if all_lines:
        head_nurses = users_with_roles(session, Role.HEAD_NURSE)
        notify(session, head_nurses, "digest", "Завтра не готовы:\n" + "\n".join(all_lines))
        sent += len(head_nurses)
    return sent


def run_lab_expiry(session: Session, config: AppConfig) -> int:
    """Flags lab results whose validity ends before the planned surgery date (once per result)."""
    names = {lab.code: lab.name_ru for lab in config.labs.labs}
    rows = session.execute(
        select(LabResult, Case)
        .join(Case, Case.id == LabResult.case_id)
        .where(
            LabResult.valid_until.is_not(None),
            Case.planned_surgery_date.is_not(None),
            Case.status != CaseStatus.DISCHARGED.value,
        )
        .options(
            selectinload(Case.patient),
            selectinload(Case.bed).selectinload(Bed.room),
            selectinload(Case.treating_doctor),
        )
    ).all()
    already = {
        n.payload.get("lab_result_id")
        for n in session.scalars(select(Notification).where(Notification.event == "lab_expiry"))
    }
    sent = 0
    for lab, case in rows:
        if lab.valid_until is None or case.planned_surgery_date is None:
            continue
        if lab.valid_until >= case.planned_surgery_date or str(lab.id) in already:
            continue
        name = names.get(lab.lab_code, lab.lab_code)
        notify(
            session,
            [case.treating_doctor],
            "lab_expiry",
            f"{case_label(case)}: срок действия анализа «{name}» истекает до операции",
            case=case,
            extra={"lab_result_id": str(lab.id)},
        )
        sent += 1
    return sent


def run_alert_scan(session: Session, config: AppConfig) -> int:
    """Re-checks today's latest entries against the (possibly changed) thresholds."""
    sent = 0
    latest: dict[uuid.UUID, PostOpEntry] = {}
    for entry in session.scalars(select(PostOpEntry).order_by(PostOpEntry.entry_date)):
        latest[entry.case_id] = entry
    from app.domain.postop import evaluate_alerts

    for case_id, entry in latest.items():
        case = session.scalars(select(Case).where(Case.id == case_id).options(*_CASE_LOAD)).one()
        if case.status not in RECORDING_STATUSES:
            continue
        alerts = evaluate_alerts(PostOpData.model_validate(entry.data), thresholds(config))
        new = [a for a in alerts if a.code not in (entry.alerts or [])]
        if new:
            entry.alerts = [a.code for a in alerts]
            notify(
                session,
                [case.treating_doctor],
                "postop_alert",
                f"{case_label(case)}: послеоперационный сигнал — "
                + ", ".join(a.message_ru for a in new),
                case=case,
            )
            sent += 1
    return sent


def run_postop_reminder(session: Session, today: date) -> int:
    """Reminds the treating doctor when a post-op case has no entry for today (default 12:00)."""
    cases = session.scalars(
        select(Case)
        .where(Case.status == CaseStatus.POST_OP.value, Case.operated_on.is_not(None))
        .options(*_CASE_LOAD)
    ).all()
    sent = 0
    for case in cases:
        has_entry = session.scalars(
            select(PostOpEntry.id).where(
                PostOpEntry.case_id == case.id, PostOpEntry.entry_date == today
            )
        ).first()
        if has_entry is None:
            notify(
                session,
                [case.treating_doctor],
                "postop_reminder",
                f"{case_label(case)}: нет дневной записи за сегодня",
                case=case,
            )
            sent += 1
    return sent
