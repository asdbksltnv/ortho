from datetime import date, time

from sqlalchemy.orm import Session

from app.api.errors import ApiError, forbidden
from app.auth import CurrentUser
from app.domain.enums import AuditAction, CaseStatus, Role
from app.domain.status_flow import Decision, Refusal, decide_transition
from app.models.case import Case, CaseStatusEvent
from app.services import audit
from app.services.cases import compute_case_readiness, refresh_first_ready
from app.services.clock import local_today
from app.services.config_loader import AppConfig
from app.services.notify import case_label, notify, users_with_roles

_MESSAGES = {
    Refusal.NOT_ALLOWED: (409, "Такой переход статуса недоступен"),
    Refusal.REASON_REQUIRED: (422, "Укажите причину"),
    Refusal.OVERRIDE_REASON_REQUIRED: (422, "Для вызова неготового пациента укажите причину"),
    Refusal.PLANNED_DATE_REQUIRED: (422, "Укажите плановую дату операции"),
}


def _refuse(decision: Decision, blocking_labels: list[str]) -> ApiError:
    refusal = decision.refusal or Refusal.NOT_ALLOWED
    if refusal is Refusal.FORBIDDEN:
        return forbidden()
    if refusal is Refusal.NOT_READY:
        return ApiError(
            409,
            "not_ready",
            "Пациент не готов к операции: вызов в операционную невозможен",
            {"blocking": blocking_labels},
        )
    status, message = _MESSAGES[refusal]
    return ApiError(status, refusal.value, message)


def transition_case(
    session: Session,
    case: Case,
    target: CaseStatus,
    user: CurrentUser,
    config: AppConfig,
    *,
    reason: str | None,
    planned_date: date | None,
    planned_time: time | None,
    ip: str | None,
) -> Case:
    current = CaseStatus(case.status)
    readiness = compute_case_readiness(case, config)
    if planned_date is not None:
        case.planned_surgery_date = planned_date
    if planned_time is not None:
        case.planned_surgery_time = planned_time

    decision = decide_transition(
        current,
        target,
        role=user.role,
        is_treating_doctor=case.treating_doctor_id == user.id,
        ready=readiness.ready,
        is_emergency=case.is_emergency,
        reason=reason,
        has_planned_date=case.planned_surgery_date is not None,
    )
    if not decision.allowed:
        session.rollback()
        labels = {d.key: d.short_label_ru for d in config.checklist.items}
        raise _refuse(decision, [labels.get(k, k) for k in readiness.blocking])

    clean_reason = (reason or "").strip() or None
    case.status = target.value
    if target is CaseStatus.CALLED_TO_OR:
        case.override_reason = clean_reason if decision.is_override else None
    elif current is CaseStatus.CALLED_TO_OR:
        case.override_reason = None  # the call was cancelled
    if target is CaseStatus.IN_OR:
        case.operated_on = local_today()
    refresh_first_ready(case, config)

    session.add(
        CaseStatusEvent(
            case_id=case.id,
            from_status=current.value,
            to_status=target.value,
            user_id=user.id,
            reason=clean_reason,
            is_override=decision.is_override,
        )
    )
    audit.record(
        session,
        user_id=user.id,
        action=AuditAction.UPDATE,
        entity="case_status",
        entity_id=case.id,
        diff={"from": current.value, "to": target.value, "override": decision.is_override},
        ip=ip,
    )
    session.flush()
    _notify(session, case, target)
    return case


def _notify(session: Session, case: Case, target: CaseStatus) -> None:
    label = case_label(case)
    if target is CaseStatus.CALLED_TO_OR:
        recipients = [
            case.treating_doctor,
            *users_with_roles(session, Role.NURSE, Role.HEAD_NURSE, Role.ANAESTHESIOLOGIST),
        ]
        notify(session, recipients, "call_to_or", f"{label}: вызов в операционную", case=case)
    elif target is CaseStatus.APPROVED_FOR_SURGERY:
        notify(
            session, [case.treating_doctor], "approved", f"{label}: одобрен к операции", case=case
        )
