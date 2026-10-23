import uuid

from fastapi import APIRouter, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    CaseCreator,
    CaseEditor,
    CaseReader,
    ConfigDep,
    ConsentWriter,
    LabsWriter,
    SessionDep,
    ip_of,
)
from app.api.errors import ApiError, forbidden, not_found
from app.auth import CurrentUser
from app.domain.enums import AuditAction, ItemStatus
from app.domain.permissions import can_edit_case, can_write_clinical_records
from app.models.case import Case, Consent, LabResult
from app.models.user import User
from app.schemas.api import (
    BoardOut,
    CaseCreate,
    CaseOut,
    CaseUpdate,
    ChecklistUpdate,
    ConsentCreate,
    ConsentOut,
    ItemOut,
    LabResultCreate,
    LabResultOut,
    PatientOut,
    ReadinessOut,
    StaffOut,
)
from app.services import audit
from app.services import cases as case_service
from app.services.board import build_board
from app.services.config_loader import AppConfig

router = APIRouter(tags=["cases"])


def _case_out(session: Session, case: Case, user: CurrentUser, config: AppConfig) -> CaseOut:
    readiness = case_service.compute_case_readiness(case, config)
    names = {u.id: u.full_name for u in session.scalars(select(User))}
    template = config.procedures.get(case.procedure_key)
    room = case.bed.room if case.bed else None
    return CaseOut(
        id=case.id,
        status=case.status,
        patient=PatientOut.model_validate(case.patient),
        bed_id=case.bed_id,
        room_name=room.name if room else None,
        bed_label=case.bed.label if case.bed else None,
        treating_doctor=StaffOut.model_validate(case.treating_doctor),
        procedure_key=case.procedure_key,
        procedure_label=template.label_ru if template else case.procedure_key,
        side=case.side,
        planned_surgery_date=case.planned_surgery_date,
        planned_surgery_time=case.planned_surgery_time,
        anaesthesia_type=case.anaesthesia_type,
        anaesthesia_remarks=case.anaesthesia_remarks,
        is_emergency=case.is_emergency,
        takes_anticoagulant=case.takes_anticoagulant,
        admitted_at=case.admitted_at,
        override_reason=case.override_reason,
        items=[
            ItemOut(
                key=i.key,
                status=ItemStatus(i.status),
                note=i.note,
                updated_at=i.updated_at,
                updated_by=names.get(i.updated_by) if i.updated_by else None,
            )
            for i in case.checklist_items
        ],
        readiness=ReadinessOut(ready=readiness.ready, blocking=list(readiness.blocking)),
        can_edit=can_edit_case(user.role, is_treating_doctor=case.treating_doctor_id == user.id),
    )


@router.get("/board", response_model=BoardOut)
def board(
    user: CaseReader,
    session: SessionDep,
    config: ConfigDep,
    mine: bool = False,
    surgery_tomorrow: bool = False,
    not_ready: bool = False,
    doctor_id: uuid.UUID | None = None,
) -> BoardOut:
    return build_board(
        session,
        user,
        config,
        mine=mine,
        surgery_tomorrow=surgery_tomorrow,
        not_ready=not_ready,
        doctor_id=doctor_id,
    )


@router.post("/cases", response_model=CaseOut, status_code=201)
def create_case(
    data: CaseCreate,
    request: Request,
    session: SessionDep,
    config: ConfigDep,
    user: CaseCreator,
) -> CaseOut:
    case = case_service.create_case(session, data, user, config, ip_of(request))
    session.commit()
    return _case_out(session, case, user, config)


@router.get("/cases/{case_id}", response_model=CaseOut)
def get_case(
    case_id: uuid.UUID, request: Request, user: CaseReader, session: SessionDep, config: ConfigDep
) -> CaseOut:
    case = case_service.load_case(session, case_id)
    audit.record(
        session,
        user_id=user.id,
        action=AuditAction.VIEW,
        entity="case",
        entity_id=case.id,
        ip=ip_of(request),
    )
    session.commit()
    return _case_out(session, case, user, config)


@router.patch("/cases/{case_id}", response_model=CaseOut)
def update_case(
    case_id: uuid.UUID,
    data: CaseUpdate,
    request: Request,
    session: SessionDep,
    config: ConfigDep,
    user: CaseEditor,
) -> CaseOut:
    case = case_service.load_case(session, case_id)
    if not can_edit_case(user.role, is_treating_doctor=case.treating_doctor_id == user.id):
        raise forbidden()
    case = case_service.update_case(session, case, data, user, config, ip_of(request))
    session.commit()
    return _case_out(session, case, user, config)


@router.patch("/cases/{case_id}/checklist/{key}", response_model=CaseOut)
def update_checklist(
    case_id: uuid.UUID,
    key: str,
    data: ChecklistUpdate,
    request: Request,
    user: CaseReader,
    session: SessionDep,
    config: ConfigDep,
) -> CaseOut:
    case = case_service.load_case(session, case_id)
    try:
        case_service.update_checklist_item(session, case, key, data, user, config, ip_of(request))
    except ApiError:
        session.rollback()
        raise
    session.commit()
    return _case_out(session, case_service.load_case(session, case_id), user, config)


def _valid_until(config: AppConfig, lab_code: str, collected_at_date):  # type: ignore[no-untyped-def]
    from datetime import timedelta

    lab = next((x for x in config.labs.labs if x.code == lab_code), None)
    if lab is None:
        raise ApiError(422, "lab_invalid", "Неизвестный код анализа")
    if lab.validity_days is None:
        return None
    return collected_at_date + timedelta(days=lab.validity_days)


@router.get("/cases/{case_id}/labs", response_model=list[LabResultOut])
def list_labs(case_id: uuid.UUID, _: CaseReader, session: SessionDep) -> list[LabResult]:
    if session.get(Case, case_id) is None:
        raise not_found("Случай")
    return list(
        session.scalars(
            select(LabResult).where(LabResult.case_id == case_id).order_by(LabResult.collected_at)
        )
    )


@router.post("/cases/{case_id}/labs", response_model=LabResultOut, status_code=201)
def add_lab(
    case_id: uuid.UUID,
    data: LabResultCreate,
    request: Request,
    session: SessionDep,
    config: ConfigDep,
    user: LabsWriter,
) -> LabResult:
    case = session.get(Case, case_id)
    if case is None:
        raise not_found("Случай")
    if not can_write_clinical_records(
        user.role, is_treating_doctor=case.treating_doctor_id == user.id
    ):
        raise forbidden()
    lab = LabResult(
        case_id=case_id,
        lab_code=data.lab_code,
        result_text=data.result_text,
        collected_at=data.collected_at,
        valid_until=_valid_until(config, data.lab_code, data.collected_at.date()),
    )
    session.add(lab)
    session.flush()
    audit.record(
        session,
        user_id=user.id,
        action=AuditAction.CREATE,
        entity="lab_result",
        entity_id=lab.id,
        diff={"case_id": str(case_id), "lab_code": data.lab_code},
        ip=ip_of(request),
    )
    session.commit()
    return lab


@router.post("/cases/{case_id}/consents", response_model=ConsentOut, status_code=201)
def add_consent(
    case_id: uuid.UUID,
    data: ConsentCreate,
    request: Request,
    session: SessionDep,
    user: ConsentWriter,
) -> Consent:
    case = session.get(Case, case_id)
    if case is None:
        raise not_found("Случай")
    if not can_write_clinical_records(
        user.role, is_treating_doctor=case.treating_doctor_id == user.id
    ):
        raise forbidden()
    consent = Consent(
        case_id=case_id, type=data.type.value, signed_at=data.signed_at, recorded_by=user.id
    )
    session.add(consent)
    session.flush()
    audit.record(
        session,
        user_id=user.id,
        action=AuditAction.CREATE,
        entity="consent",
        entity_id=consent.id,
        diff={"case_id": str(case_id), "type": data.type.value},
        ip=ip_of(request),
    )
    session.commit()
    return consent
