from pathlib import Path
from typing import Any

import pytest
import yaml
from sqlalchemy import func, select

from app.floorplan import apply_plan, load_plan
from app.models.ward import Bed, Room
from app.seed import seed_ward

CONFIG = Path(__file__).resolve().parents[1] / "config" / "floor_plan.yaml"


def test_plan_matches_the_10th_floor_evacuation_plan() -> None:
    plan = load_plan(CONFIG)
    patient = [r.name for r in plan.rooms if r.kind == "patient"]
    assert patient == [f"Пал. {n}" for n in range(1001, 1017)]
    service = {r.name for r in plan.rooms if r.kind != "patient"}
    assert {"Ординаторская", "Перевязочная", "Процедурная 1", "Процедурная 2", "Лифт", "Лифт 2"} <= service
    assert all(r.beds == 0 for r in plan.rooms if r.kind != "patient")
    for r in plan.rooms:  # everything sits on the canvas
        assert 0 <= r.x and r.x + r.w <= plan.canvas.width and 0 <= r.y and r.y + r.h <= plan.canvas.height


def test_rooms_do_not_overlap() -> None:
    rooms = load_plan(CONFIG).rooms
    for i, a in enumerate(rooms):
        for b in rooms[i + 1 :]:
            apart = a.x + a.w <= b.x or b.x + b.w <= a.x or a.y + a.h <= b.y or b.y + b.h <= a.y
            assert apart, (a.name, b.name)


def test_apply_is_idempotent_and_only_adds_beds(db: Any) -> None:
    plan = load_plan(CONFIG)
    with db() as s:
        _, rooms, beds = apply_plan(s, plan)
        assert (rooms, beds) == (28, 16)
        assert apply_plan(s, plan)[1:] == (0, 0)
        room = s.scalars(select(Room).where(Room.name == "Пал. 1005")).one()
        assert (room.kind, room.width, room.floor) == ("patient", 70, 10)
        two = plan.model_copy(deep=True)
        next(r for r in two.rooms if r.name == "Пал. 1005").beds = 2
        assert apply_plan(s, two)[1:] == (0, 1)
        assert apply_plan(s, plan)[1:] == (0, 0)  # going back to 1 bed never deletes one
        assert s.scalar(select(func.count()).select_from(Bed).where(Bed.room_id == room.id)) == 2


def test_duplicate_room_names_are_rejected(tmp_path: Path) -> None:
    data = yaml.safe_load(CONFIG.read_text())
    data["rooms"].append(dict(data["rooms"][0]))
    bad = tmp_path / "plan.yaml"
    bad.write_text(yaml.safe_dump(data, allow_unicode=True))
    with pytest.raises(ValueError, match="duplicate"):
        load_plan(bad)


def test_demo_seed_uses_the_patient_rooms(db: Any) -> None:
    with db() as s:
        beds = seed_ward(s)
        assert len(beds) == 16
        names = {s.get(Room, b.room_id).name for b in beds}  # type: ignore[union-attr]
        assert names == {f"Пал. {n}" for n in range(1001, 1017)}


def test_wards_api_exposes_the_layout(api: Any, db: Any) -> None:
    from app.domain.enums import Role
    from tests.conftest import Api

    with db() as s:
        apply_plan(s, load_plan(CONFIG))
        s.commit()
    wards = Api().as_role(Role.NURSE).get("/wards").json()
    floor = next(w for w in wards if w["name"].endswith("10 этаж"))
    lift = next(r for r in floor["rooms"] if r["name"] == "Лифт")
    assert lift["kind"] == "service" and lift["beds"] == [] and lift["width"] == 50
