import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.errors import ApiError, forbidden, not_found
from app.auth import CurrentUser
from app.domain.enums import AuditAction, CaseStatus, ItemStatus, Role
from app.domain.permissions import can_edit_checklist_item
from app.domain.readiness import ItemDef, Readiness, ReadinessContext, compute_readiness
from app.models.base import utcnow
from app.models.case import Case, CaseStatusEvent, ChecklistItem, Patient
from app.models.user import User
from app.models.ward import Bed, Room
from app.schemas.api import CaseCreate, CaseUpdate, ChecklistUpdate
from app.services import audit
from app.services.clock import local_today
from app.services.config_loader import AppConfig

ACTIVE_STATUSES_EXCLUDED = (CaseStatus.DISCHARGED.value,)


def load_case(session: Session, case_id: uuid.UUID) -> Case:
    case = session.scalars(
        select(Case)
        .where(Case.id == case_id)
        .options(
            selectinload(Case.checklist_items),
            selectinload(Case.patient),
            selectinload(Case.bed).selectinload(Bed.room),
            selectinload(Case.treating_doctor),
        )
    ).one_or_none()
    if case is None:
        raise not_found("Случай")
    return case


def compute_case_readiness(case: Case, config: AppConfig) -> Readiness:
    template = config.procedures.get(case.procedure_key)
    ctx = ReadinessContext(
        today=local_today(),
        planned_surgery_date=case.planned_surgery_date,
        procedure_blocking_items=frozenset(template.blocking_items) if template else frozenset(),
        flags=frozenset({"takes_anticoagulant"}) if case.takes_anticoagulant else frozenset(),
    )
    defs = [ItemDef(d.key, d.blocking, d.auto_applies_flag) for d in config.checklist.items]
    statuses = {i.key: ItemStatus(i.status) for i in case.checklist_items}
    return compute_readiness(defs, statuses, ctx)


def refresh_first_ready(case: Case, config: AppConfig) -> Readiness:
    readiness = compute_case_readiness(case, config)
    if readiness.ready and case.first_ready_at is None:
        case.first_ready_at = utcnow()
    return readiness


def _require_bed_free(session: Session, bed_id: uuid.UUID, exclude_case: uuid.UUID | None) -> None:
    bed = session.get(Bed, bed_id)
    if bed is None or not bed.is_active:
        raise ApiError(422, "bed_invalid", "Койка не найдена или недоступна")
    stmt = select(Case.id).where(Case.bed_id == bed_id, Case.status != CaseStatus.DISCHARGED.value)
    if exclude_case is not None:
        stmt = stmt.where(Case.id != exclude_case)
    if session.scalars(stmt).first() is not None:
        raise ApiError(409, "bed_occupied", "Койка уже занята")


def _require_doctor(session: Session, doctor_id: uuid.UUID) -> User:
    doctor = session.get(User, doctor_id)
    if (
        doctor is None
        or not doctor.is_active
        or doctor.role
        not in (
            Role.DOCTOR.value,
            Role.HEAD_OF_DEPARTMENT.value,
        )
    ):
        raise ApiError(422, "doctor_invalid", "Лечащий врач не найден")
    return doctor


def _require_procedure(config: AppConfig, key: str) -> None:
    if key not in config.procedures:
        raise ApiError(422, "procedure_invalid", "Неизвестный тип операции")


def create_case(
    session: Session, data: CaseCreate, user: CurrentUser, config: AppConfig, ip: str | None
) -> Case:
    _require_procedure(config, data.procedure_key)
    if user.role is Role.DOCTOR:
        doctor_id = user.id
    else:
        if data.treating_doctor_id is None:
            raise ApiError(422, "doctor_required", "Укажите лечащего врача")
        doctor_id = data.treating_doctor_id
    _require_doctor(session, doctor_id)
    if data.bed_id is not None:
        _require_bed_free(session, data.bed_id, None)

    patient = Patient(**data.patient.model_dump())
    session.add(patient)
    session.flush()
    case = Case(
        patient_id=patient.id,
        bed_id=data.bed_id,
        treating_doctor_id=doctor_id,
        procedure_key=data.procedure_key,
        side=data.side,
        planned_surgery_date=data.planned_surgery_date,
        planned_surgery_time=data.planned_surgery_time,
        is_emergency=data.is_emergency,
        status=CaseStatus.ADMITTED.value,
    )
    session.add(case)
    session.flush()
    for definition in config.checklist.items:
        session.add(ChecklistItem(case_id=case.id, key=definition.key))
    session.add(
        CaseStatusEvent(
            case_id=case.id, from_status=None, to_status=CaseStatus.ADMITTED.value, user_id=user.id
        )
    )
    audit.record(
        session,
        user_id=user.id,
        action=AuditAction.CREATE,
        entity="case",
        entity_id=case.id,
        diff={"procedure_key": data.procedure_key, "is_emergency": data.is_emergency},
        ip=ip,
    )
    session.flush()
    return load_case(session, case.id)


def update_case(
    session: Session,
    case: Case,
    data: CaseUpdate,
    user: CurrentUser,
    config: AppConfig,
    ip: str | None,
) -> Case:
    changes = data.model_dump(exclude_unset=True)
    diff: dict[str, Any] = {}
    if "procedure_key" in changes and changes["procedure_key"] is not None:
        _require_procedure(config, changes["procedure_key"])
    if "bed_id" in changes and changes["bed_id"] is not None:
        _require_bed_free(session, changes["bed_id"], case.id)
    if "treating_doctor_id" in changes:
        if user.role is not Role.HEAD_OF_DEPARTMENT:
            raise forbidden()  # only the head reassigns the treating doctor
        if changes["treating_doctor_id"] is None:
            raise ApiError(422, "doctor_required", "Укажите лечащего врача")
        _require_doctor(session, changes["treating_doctor_id"])
    for field, value in changes.items():
        if field in {"procedure_key", "is_emergency", "takes_anticoagulant"} and value is None:
            continue
        old = getattr(case, field)
        if old != value:
            diff[field] = [str(old), str(value)]
            setattr(case, field, value)
    if diff:
        refresh_first_ready(case, config)  # flags / procedure may change what is blocking
        audit.record(
            session,
            user_id=user.id,
            action=AuditAction.UPDATE,
            entity="case",
            entity_id=case.id,
            diff=diff,
            ip=ip,
        )
    session.flush()
    return load_case(session, case.id)


def update_checklist_item(
    session: Session,
    case: Case,
    key: str,
    data: ChecklistUpdate,
    user: CurrentUser,
    config: AppConfig,
    ip: str | None,
) -> ChecklistItem:
    definition = config.checklist_by_key.get(key)
    if definition is None:
        raise not_found("Пункт чек-листа")
    if not can_edit_checklist_item(
        user.role,
        item_key=key,
        item_owner=definition.owner_role,
        is_treating_doctor=case.treating_doctor_id == user.id,
    ):
        raise forbidden()

    item = next((i for i in case.checklist_items if i.key == key), None)
    if item is None:
        raise not_found("Пункт чек-листа")

    if data.expected_updated_at is not None and item.updated_at != data.expected_updated_at:
        editor = session.get(User, item.updated_by) if item.updated_by else None
        raise ApiError(
            409,
            "conflict",
            "Пункт уже изменён другим пользователем",
            {
                "current": {
                    "status": item.status,
                    "note": item.note,
                    "updated_at": item.updated_at.isoformat(),
                    "updated_by": editor.full_name if editor else None,
                }
            },
        )

    old_status = item.status
    note_changed = (item.note or None) != (data.note or None)
    item.status = data.status.value
    item.note = data.note or None
    # Force a version bump even when only the status is re-confirmed.
    item.updated_at = utcnow()
    refresh_first_ready(case, config)
    audit.record(
        session,
        user_id=user.id,
        action=AuditAction.UPDATE,
        entity="checklist_item",
        entity_id=item.id,
        diff={
            "case_id": str(case.id),
            "key": key,
            "status": [old_status, data.status.value],
            "note_changed": note_changed,
        },
        ip=ip,
    )
    session.flush()
    return item


def timestamp(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def room_of(bed: Bed | None) -> Room | None:
    return bed.room if bed else None
