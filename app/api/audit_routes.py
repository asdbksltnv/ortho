import base64
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Query
from sqlalchemy import and_, or_, select

from app.api.deps import AuditReader, ConfigDep, SessionDep, UserDep
from app.api.errors import ApiError, forbidden
from app.domain.permissions import Perm, has_perm
from app.models.case import AuditLog
from app.schemas.api import (
    AuditOut,
    AuditPage,
    ColumnDef,
    ConfigFileOut,
    DefinitionsOut,
    ProcedureOut,
)

router = APIRouter(tags=["admin"])


def _encode(row: AuditLog) -> str:
    raw = json.dumps({"t": row.created_at.isoformat(), "i": str(row.id)}).encode()
    return base64.urlsafe_b64encode(raw).decode()


def _decode(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return datetime.fromisoformat(data["t"]), uuid.UUID(data["i"])
    except (ValueError, KeyError, TypeError) as exc:
        raise ApiError(422, "bad_cursor", "Некорректный курсор") from exc


@router.get("/audit", response_model=AuditPage)
def list_audit(
    session: SessionDep,
    _: AuditReader,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    entity: str | None = None,
    action: str | None = None,
) -> AuditPage:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    if entity:
        stmt = stmt.where(AuditLog.entity == entity)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if cursor:
        ts, last_id = _decode(cursor)
        stmt = stmt.where(
            or_(AuditLog.created_at < ts, and_(AuditLog.created_at == ts, AuditLog.id < last_id))
        )
    rows = list(session.scalars(stmt.limit(limit + 1)))
    page, more = rows[:limit], len(rows) > limit
    return AuditPage(
        items=[AuditOut.model_validate(r) for r in page],
        next_cursor=_encode(page[-1]) if more and page else None,
    )


@router.get("/config/definitions", response_model=DefinitionsOut)
def definitions(config: ConfigDep, _: UserDep) -> DefinitionsOut:
    return DefinitionsOut(
        checklist=[
            ColumnDef(
                key=d.key,
                label_ru=d.label_ru,
                short_label_ru=d.short_label_ru,
                owner_role=d.owner_role,
            )
            for d in config.checklist.items
        ],
        procedures=[ProcedureOut(id=p.id, label_ru=p.label_ru) for p in config.procedures.values()],
    )


@router.get("/admin/config-status", response_model=list[ConfigFileOut])
def config_status(config: ConfigDep, user: UserDep) -> list[ConfigFileOut]:
    if not has_perm(user.role, Perm.CONFIG_STATUS_READ):
        raise forbidden()
    return [
        ConfigFileOut(
            name=f.name,
            version=f.version,
            requires_clinical_validation=f.requires_clinical_validation,
        )
        for f in config.files
    ]
