"""Loads config/floor_plan.yaml into wards/rooms/beds. Idempotent: matches rooms by name, updates
their position and kind, and only ever adds beds (never removes them, they may be occupied).

    python -m app.floorplan
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ward import Bed, Room, Ward
from app.settings import get_settings


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanRoom(_Strict):
    name: str
    kind: Literal["patient", "service", "exit"]
    beds: int = 0
    x: int
    y: int
    w: int
    h: int


class Canvas(_Strict):
    width: int
    height: int


class FloorPlan(_Strict):
    version: int
    ward: str
    floor: int
    canvas: Canvas
    rooms: list[PlanRoom]


def load_plan(path: Path | None = None) -> FloorPlan:
    path = path or Path(get_settings().config_dir) / "floor_plan.yaml"
    with path.open(encoding="utf-8") as fh:
        plan = FloorPlan.model_validate(yaml.safe_load(fh))
    names = [r.name for r in plan.rooms]
    if len(names) != len(set(names)):
        raise ValueError("floor_plan.yaml: duplicate room names")
    return plan


def apply_plan(session: Session, plan: FloorPlan) -> tuple[Ward, int, int]:
    """Returns (ward, rooms created, beds created)."""
    ward = session.scalars(select(Ward).where(Ward.name == plan.ward)).first()
    if ward is None:
        ward = Ward(name=plan.ward)
        session.add(ward)
        session.flush()
    existing = {r.name: r for r in session.scalars(select(Room).where(Room.ward_id == ward.id))}
    rooms_created = beds_created = 0
    for spec in plan.rooms:
        room = existing.get(spec.name)
        if room is None:
            room = Room(ward_id=ward.id, name=spec.name)
            session.add(room)
            rooms_created += 1
        room.floor = plan.floor
        room.kind = spec.kind
        room.position_x, room.position_y = spec.x, spec.y
        room.width, room.height = spec.w, spec.h
        session.flush()
        have = len(list(session.scalars(select(Bed).where(Bed.room_id == room.id))))
        for n in range(have + 1, spec.beds + 1):
            session.add(Bed(room_id=room.id, label=f"к. {n}"))
            beds_created += 1
    session.flush()
    return ward, rooms_created, beds_created


def main() -> None:
    from app.db import get_session_factory

    with get_session_factory()() as session:
        _, rooms, beds = apply_plan(session, load_plan())
        session.commit()
    print(f"floor plan: {rooms} room(s) and {beds} bed(s) added", flush=True)


if __name__ == "__main__":
    main()
