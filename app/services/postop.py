import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ApiError, forbidden, not_found
from app.auth import CurrentUser
from app.domain.enums import AuditAction, CaseStatus
from app.domain.permissions import can_edit_case
from app.domain.postop import (
    PostOpData,
    Thresholds,
    evaluate_alerts,
    note_input,
    post_op_day,
)
from app.models.base import utcnow
from app.models.case import AiNoteDraft, Case, PostOpEntry
from app.services import audit
from app.services.clock import local_today
from app.services.config_loader import AppConfig
from app.services.notes import generate_note
from app.services.notify import case_label, notify
from app.settings import get_settings

RECORDING_STATUSES = {
    CaseStatus.RETURNED_TO_WARD.value,
    CaseStatus.TRANSFERRED_ICU.value,
    CaseStatus.POST_OP.value,
}


def thresholds(config: AppConfig) -> Thresholds:
    t = config.alerts.thresholds
    return Thresholds(
        temperature_max=t.temperature_max,
        drain_output_ml_max=t.drain_output_ml_max,
        pain_vas_max=t.pain_vas_max,
        purulent_discharge=t.purulent_discharge,
    )


def require_editor(case: Case, user: CurrentUser) -> None:
    if not can_edit_case(user.role, is_treating_doctor=case.treating_doctor_id == user.id):
        raise forbidden()


def load_entry(session: Session, case_id: uuid.UUID, entry_id: uuid.UUID) -> PostOpEntry:
    entry = session.get(PostOpEntry, entry_id)
    if entry is None or entry.case_id != case_id:
        raise not_found("Запись")
    return entry


def entries_for(session: Session, case_id: uuid.UUID) -> list[PostOpEntry]:
    return list(
        session.scalars(
            select(PostOpEntry)
            .where(PostOpEntry.case_id == case_id)
            .order_by(PostOpEntry.entry_date)
        )
    )


def _draft(session: Session, entry: PostOpEntry) -> AiNoteDraft | None:
    return session.scalars(
        select(AiNoteDraft).where(AiNoteDraft.postop_entry_id == entry.id)
    ).one_or_none()


def regenerate_draft(session: Session, entry: PostOpEntry) -> AiNoteDraft:
    """(Re)drafts the note from the entry. A new draft is never approved."""
    data = PostOpData.model_validate(entry.data)
    generator, output = generate_note(get_settings(), note_input(data, entry.post_op_day))
    draft = _draft(session, entry)
    if draft is None:
        draft = AiNoteDraft(postop_entry_id=entry.id, generator=generator, output=output.to_dict())
        session.add(draft)
    else:
        draft.generator = generator
        draft.output = output.to_dict()
        draft.approved_by = None
        draft.approved_at = None
    session.flush()
    return draft


def _keep_server_photo(data: PostOpData, existing: str | None) -> PostOpData:
    """The photo key is set only by the upload endpoint, never by the form."""
    return data.model_copy(update={"photo_key": existing})


def _check_alerts(
    session: Session, case: Case, entry: PostOpEntry, data: PostOpData, config: AppConfig
) -> None:
    alerts = evaluate_alerts(data, thresholds(config))
    codes = [a.code for a in alerts]
    new = [a for a in alerts if a.code not in (entry.alerts or [])]
    entry.alerts = codes
    if new:
        notify(
            session,
            [case.treating_doctor],
            "postop_alert",
            f"{case_label(case)}: послеоперационный сигнал — "
            + ", ".join(a.message_ru for a in new),
            case=case,
        )
        entry.alerts_notified = True


def create_entry(
    session: Session,
    case: Case,
    data: PostOpData,
    user: CurrentUser,
    config: AppConfig,
    ip: str | None,
) -> PostOpEntry:
    require_editor(case, user)
    if case.status not in RECORDING_STATUSES or case.operated_on is None:
        raise ApiError(
            409, "not_postop", "Дневные записи ведутся после возвращения пациента из операционной"
        )
    today = local_today()
    existing = session.scalars(
        select(PostOpEntry).where(PostOpEntry.case_id == case.id, PostOpEntry.entry_date == today)
    ).first()
    if existing is not None:
        raise ApiError(
            409, "entry_exists", "За сегодня запись уже есть", {"entry_id": str(existing.id)}
        )
    data = _keep_server_photo(data, None)
    entry = PostOpEntry(
        case_id=case.id,
        entered_at=utcnow(),
        entry_date=today,
        post_op_day=post_op_day(case.operated_on, today),
        data=data.model_dump(mode="json"),
        alerts=[],
    )
    session.add(entry)
    session.flush()
    _check_alerts(session, case, entry, data, config)
    regenerate_draft(session, entry)
    audit.record(
        session,
        user_id=user.id,
        action=AuditAction.CREATE,
        entity="postop_entry",
        entity_id=entry.id,
        diff={"case_id": str(case.id), "post_op_day": entry.post_op_day},
        ip=ip,
    )
    return entry


def update_entry(
    session: Session,
    case: Case,
    entry: PostOpEntry,
    data: PostOpData,
    user: CurrentUser,
    config: AppConfig,
    ip: str | None,
) -> PostOpEntry:
    require_editor(case, user)
    current = PostOpData.model_validate(entry.data)
    data = _keep_server_photo(data, current.photo_key)
    entry.data = data.model_dump(mode="json")
    _check_alerts(session, case, entry, data, config)
    regenerate_draft(session, entry)  # changed facts: the earlier approval no longer applies
    audit.record(
        session,
        user_id=user.id,
        action=AuditAction.UPDATE,
        entity="postop_entry",
        entity_id=entry.id,
        diff={"case_id": str(case.id)},
        ip=ip,
    )
    session.flush()
    return entry


def approve_note(
    session: Session,
    case: Case,
    entry: PostOpEntry,
    general_condition: str,
    local_status: str,
    user: CurrentUser,
    ip: str | None,
) -> AiNoteDraft:
    require_editor(case, user)
    draft = _draft(session, entry)
    if draft is None:
        raise not_found("Черновик")
    draft.output = {
        "general_condition": " ".join(general_condition.split()),
        "local_status": " ".join(local_status.split()),
    }
    draft.approved_by = user.id
    draft.approved_at = utcnow()
    audit.record(
        session,
        user_id=user.id,
        action=AuditAction.UPDATE,
        entity="ai_note_draft",
        entity_id=draft.id,
        diff={"approved": True, "generator": draft.generator},
        ip=ip,
    )
    session.flush()
    return draft


def trends(entries: list[PostOpEntry]) -> list[dict[str, Any]]:
    """Per-day series for the charts: temperature, drain output, pain and wound status."""
    out: list[dict[str, Any]] = []
    for e in entries:
        d = PostOpData.model_validate(e.data)
        out.append(
            {
                "day": e.post_op_day,
                "date": e.entry_date.isoformat(),
                "temp": d.vitals.temp,
                "drain_ml": d.drain.output_ml,
                "pain": d.pain_vas,
                "discharge": d.wound.discharge,
                "redness": d.wound.redness,
                "swelling": d.wound.swelling,
            }
        )
    return out
