import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import CurrentUser
from app.domain.privacy import initials
from app.models.base import utcnow
from app.models.case import Case
from app.models.user import User
from app.models.ward import Bed
from app.schemas.api import BoardItem, BoardOut, BoardRow, ColumnDef
from app.services.cases import ACTIVE_STATUSES_EXCLUDED, compute_case_readiness
from app.services.clock import local_today
from app.services.config_loader import AppConfig


def build_board(
    session: Session,
    user: CurrentUser,
    config: AppConfig,
    *,
    mine: bool = False,
    surgery_tomorrow: bool = False,
    not_ready: bool = False,
    doctor_id: uuid.UUID | None = None,
) -> BoardOut:
    """Ward board rows. Identifies patients by initials and bed only; never full names."""
    stmt = (
        select(Case)
        .where(Case.status.not_in(ACTIVE_STATUSES_EXCLUDED))
        .options(
            selectinload(Case.checklist_items),
            selectinload(Case.patient),
            selectinload(Case.bed).selectinload(Bed.room),
            selectinload(Case.treating_doctor),
        )
    )
    if mine:
        stmt = stmt.where(Case.treating_doctor_id == user.id)
    if doctor_id is not None:
        stmt = stmt.where(Case.treating_doctor_id == doctor_id)
    if surgery_tomorrow:
        stmt = stmt.where(Case.planned_surgery_date == local_today() + timedelta(days=1))
    cases = list(session.scalars(stmt))

    names = {u.id: u.full_name for u in session.scalars(select(User))}
    rows: list[BoardRow] = []
    for case in cases:
        readiness = compute_case_readiness(case, config)
        if not_ready and readiness.ready:
            continue
        room = case.bed.room if case.bed else None
        template = config.procedures.get(case.procedure_key)
        rows.append(
            BoardRow(
                case_id=case.id,
                bed_id=case.bed_id,
                initials=initials(case.patient.full_name),
                room_id=room.id if room else None,
                room_name=room.name if room else None,
                bed_label=case.bed.label if case.bed else None,
                status=case.status,
                procedure_label=template.label_ru if template else case.procedure_key,
                planned_surgery_date=case.planned_surgery_date,
                is_emergency=case.is_emergency,
                treating_doctor_id=case.treating_doctor_id,
                treating_doctor_name=case.treating_doctor.full_name,
                ready=readiness.ready,
                blocking=list(readiness.blocking),
                applicable_count=len(readiness.applicable),
                override_reason=case.override_reason,
                items={
                    i.key: BoardItem(
                        status=i.status,
                        note=i.note,
                        updated_at=i.updated_at,
                        updated_by=names.get(i.updated_by) if i.updated_by else None,
                    )
                    for i in case.checklist_items
                },
            )
        )
    # Cases without a bed go last ("~" would sort before Cyrillic letters).
    rows.sort(key=lambda r: (r.room_name is None, r.room_name or "", r.bed_label or ""))
    return BoardOut(
        columns=[
            ColumnDef(
                key=d.key,
                label_ru=d.label_ru,
                short_label_ru=d.short_label_ru,
                owner_role=d.owner_role,
            )
            for d in config.checklist.items
        ],
        rows=rows,
        generated_at=utcnow(),
    )
