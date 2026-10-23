import uuid

from fastapi import APIRouter, Request
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import SessionDep, UserDep, WardsAdmin, ip_of
from app.api.errors import not_found
from app.auth import CurrentUser
from app.domain.enums import AuditAction
from app.models.ward import Bed, Room, Ward
from app.schemas.api import (
    BedCreate,
    BedOut,
    BedUpdate,
    RoomCreate,
    RoomOut,
    RoomUpdate,
    WardCreate,
    WardOut,
)
from app.services import audit

router = APIRouter(prefix="/wards", tags=["wards"])


@router.get("", response_model=list[WardOut])
def list_wards(session: SessionDep, _: UserDep) -> list[Ward]:
    return list(
        session.scalars(
            select(Ward)
            .options(selectinload(Ward.rooms).selectinload(Room.beds))
            .order_by(Ward.name)
        )
    )


def _log(
    session: SessionDep,
    admin: CurrentUser,
    request: Request,
    action: AuditAction,
    entity: str,
    id_: uuid.UUID,
) -> None:
    audit.record(
        session, user_id=admin.id, action=action, entity=entity, entity_id=id_, ip=ip_of(request)
    )


@router.post("", response_model=WardOut, status_code=201)
def create_ward(
    data: WardCreate,
    request: Request,
    session: SessionDep,
    admin: WardsAdmin,
) -> Ward:
    ward = Ward(name=data.name)
    session.add(ward)
    session.flush()
    _log(session, admin, request, AuditAction.CREATE, "ward", ward.id)
    session.commit()
    return ward


@router.post("/rooms", response_model=RoomOut, status_code=201)
def create_room(
    data: RoomCreate,
    request: Request,
    session: SessionDep,
    admin: WardsAdmin,
) -> Room:
    if session.get(Ward, data.ward_id) is None:
        raise not_found("Отделение")
    room = Room(**data.model_dump())
    session.add(room)
    session.flush()
    _log(session, admin, request, AuditAction.CREATE, "room", room.id)
    session.commit()
    session.refresh(room)
    return room


@router.patch("/rooms/{room_id}", response_model=RoomOut)
def update_room(
    room_id: uuid.UUID,
    data: RoomUpdate,
    request: Request,
    session: SessionDep,
    admin: WardsAdmin,
) -> Room:
    room = session.get(Room, room_id)
    if room is None:
        raise not_found("Палата")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(room, field, value)
    _log(session, admin, request, AuditAction.UPDATE, "room", room.id)
    session.commit()
    return room


@router.post("/beds", response_model=BedOut, status_code=201)
def create_bed(
    data: BedCreate,
    request: Request,
    session: SessionDep,
    admin: WardsAdmin,
) -> Bed:
    if session.get(Room, data.room_id) is None:
        raise not_found("Палата")
    bed = Bed(**data.model_dump())
    session.add(bed)
    session.flush()
    _log(session, admin, request, AuditAction.CREATE, "bed", bed.id)
    session.commit()
    return bed


@router.patch("/beds/{bed_id}", response_model=BedOut)
def update_bed(
    bed_id: uuid.UUID,
    data: BedUpdate,
    request: Request,
    session: SessionDep,
    admin: WardsAdmin,
) -> Bed:
    bed = session.get(Bed, bed_id)
    if bed is None:
        raise not_found("Койка")
    for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(bed, field, value)
    _log(session, admin, request, AuditAction.UPDATE, "bed", bed.id)
    session.commit()
    return bed
