import uuid
from datetime import date
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.domain.enums import Role
from app.models.case import Case
from tests.conftest import Api, case_payload  # noqa: F401

READY_KEYS = [
    "docs",
    "labs_core",
    "consent_surgical",
    "anaesthesia",
    "antibiotic",
    "blood_reserve",
    "implant",
]
OWNERS = {
    "labs_core": Role.NURSE,
    "blood_reserve": Role.NURSE,
    "implant": Role.NURSE,
    "anaesthesia": Role.ANAESTHESIOLOGIST,
}


def make_ready(case_id: uuid.UUID) -> None:
    """Marks every always-blocking TKA item done, each by a role allowed to do it."""
    for key in READY_KEYS:
        actor = Api().as_role(OWNERS.get(key, Role.HEAD_OF_DEPARTMENT))
        resp = actor.patch(f"/cases/{case_id}/checklist/{key}", json={"status": "done"})
        assert resp.status_code == 200, resp.text


def set_case(db: sessionmaker[Session], case_id: uuid.UUID, **fields: Any) -> None:
    with db() as session:
        case = session.get(Case, case_id)
        assert case is not None
        for key, value in fields.items():
            setattr(case, key, value)
        session.commit()


def move_to_postop(db: sessionmaker[Session], case_id: uuid.UUID, operated_on: date) -> None:
    set_case(db, case_id, status="post_op", operated_on=operated_on)
