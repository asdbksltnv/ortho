import uuid

from fastapi import APIRouter, Request

from app.api.cases import _case_out
from app.api.deps import CaseReader, ConfigDep, SessionDep, UserDep, ip_of
from app.api.errors import forbidden
from app.domain.enums import AuditAction
from app.domain.permissions import Perm, can_edit_case, has_perm
from app.models.case import Case
from app.schemas.api import AnaesthesiaIn, CaseOut, IntakeConfigOut, IntakeIn, IntakeOut
from app.services import audit
from app.services import cases as case_service
from app.services import intake as intake_service

router = APIRouter(tags=["intake"])


def _out(session, case: Case, user, config) -> IntakeOut:  # type: ignore[no-untyped-def]
    data, row = intake_service.load_intake(session, case, config)
    return IntakeOut(
        data=data,
        schema_version=row.schema_version if row else 1,
        updated_at=row.updated_at if row else None,
        completed_at=row.completed_at if row else None,
        is_new=row is None,
        can_edit=can_edit_case(user.role, is_treating_doctor=case.treating_doctor_id == user.id),
        derived=intake_service.derived(
            data, case.patient.birth_date, config, intake_service.today()
        ),
    )


@router.get("/cases/{case_id}/intake", response_model=IntakeOut)
def get_intake(
    case_id: uuid.UUID, user: CaseReader, session: SessionDep, config: ConfigDep
) -> IntakeOut:
    case = case_service.load_case(session, case_id)
    return _out(session, case, user, config)


@router.put("/cases/{case_id}/intake", response_model=IntakeOut)
def put_intake(
    case_id: uuid.UUID,
    body: IntakeIn,
    request: Request,
    user: CaseReader,
    session: SessionDep,
    config: ConfigDep,
) -> IntakeOut:
    case = case_service.load_case(session, case_id)
    if not can_edit_case(user.role, is_treating_doctor=case.treating_doctor_id == user.id):
        raise forbidden()
    intake_service.save_intake(
        session,
        case,
        body.data,
        user=user,
        request_id=body.request_id,
        base_updated_at=body.base_updated_at,
        completed=body.completed,
        config=config,
        ip=ip_of(request),
    )
    session.commit()
    return _out(session, case_service.load_case(session, case_id), user, config)


@router.get("/config/intake", response_model=IntakeConfigOut)
def intake_config(_: UserDep, config: ConfigDep) -> IntakeConfigOut:
    return IntakeConfigOut(
        picklists=config.defaults.picklists,
        segments=config.defaults.segments,
        locations=config.locations,
        systems=config.defaults.systems,
        psycho=config.defaults.psycho,
        caprini=config.caprini,
        columbia=config.columbia,
        nutrition=config.nutrition,
        diets=config.diets.diets,
        default_diet=config.diets.default,
        core_labs=[lab.name_ru for lab in config.labs.labs if lab.group == "core"],
    )


@router.put("/cases/{case_id}/anaesthesia", response_model=CaseOut)
def put_anaesthesia(
    case_id: uuid.UUID,
    body: AnaesthesiaIn,
    request: Request,
    user: UserDep,
    session: SessionDep,
    config: ConfigDep,
) -> CaseOut:
    if not has_perm(user.role, Perm.ANAESTHESIA_WRITE):
        raise forbidden()
    case = case_service.load_case(session, case_id)
    case.anaesthesia_type = (body.type or "").strip() or None
    case.anaesthesia_remarks = (body.remarks or "").strip() or None
    audit.record(
        session,
        user_id=user.id,
        action=AuditAction.UPDATE,
        entity="anaesthesia_clearance",
        entity_id=case.id,
        diff={"type_set": case.anaesthesia_type is not None},
        ip=ip_of(request),
    )
    session.commit()
    return _case_out(session, case_service.load_case(session, case_id), user, config)
