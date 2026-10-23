import pytest

from app.domain.enums import Role
from app.domain.permissions import (
    Perm,
    can_edit_case,
    can_edit_checklist_item,
    can_write_clinical_records,
    has_perm,
)
from app.domain.privacy import initials


def test_initials() -> None:
    assert initials("Иванов Алишер Дилшодович") == "И. А. Д."
    assert initials("  петров   иван ") == "П. И."
    assert initials("") == ""


@pytest.mark.parametrize(
    ("role", "key", "owner", "own", "expected"),
    [
        (Role.DOCTOR, "docs", Role.DOCTOR, True, True),
        (Role.DOCTOR, "docs", Role.DOCTOR, False, False),
        (Role.DOCTOR, "labs_core", Role.NURSE, True, True),
        (Role.DOCTOR, "anaesthesia", Role.ANAESTHESIOLOGIST, True, False),
        (Role.NURSE, "labs_core", Role.NURSE, False, True),
        (Role.NURSE, "consent_surgical", Role.DOCTOR, False, True),
        (Role.NURSE, "docs", Role.DOCTOR, False, False),
        (Role.NURSE, "anaesthesia", Role.ANAESTHESIOLOGIST, False, False),
        (Role.HEAD_NURSE, "implant", Role.NURSE, False, True),
        (Role.HEAD_NURSE, "antibiotic", Role.DOCTOR, False, False),
        (Role.ANAESTHESIOLOGIST, "anaesthesia", Role.ANAESTHESIOLOGIST, False, True),
        (Role.ANAESTHESIOLOGIST, "docs", Role.DOCTOR, False, False),
        (Role.HEAD_OF_DEPARTMENT, "anaesthesia", Role.ANAESTHESIOLOGIST, False, True),
        (Role.HEAD_OF_DEPARTMENT, "docs", Role.DOCTOR, False, True),
        (Role.ADMIN, "docs", Role.DOCTOR, True, False),
    ],
)
def test_checklist_edit_matrix(
    role: Role, key: str, owner: Role, own: bool, expected: bool
) -> None:
    assert (
        can_edit_checklist_item(role, item_key=key, item_owner=owner, is_treating_doctor=own)
        is expected
    )


def test_case_edit_rules() -> None:
    assert can_edit_case(Role.DOCTOR, is_treating_doctor=True)
    assert not can_edit_case(Role.DOCTOR, is_treating_doctor=False)
    assert can_edit_case(Role.HEAD_OF_DEPARTMENT, is_treating_doctor=False)
    assert not can_edit_case(Role.NURSE, is_treating_doctor=False)
    assert not can_edit_case(Role.ADMIN, is_treating_doctor=True)


def test_clinical_records_rules() -> None:
    assert can_write_clinical_records(Role.NURSE, is_treating_doctor=False)
    assert can_write_clinical_records(Role.DOCTOR, is_treating_doctor=True)
    assert not can_write_clinical_records(Role.DOCTOR, is_treating_doctor=False)
    assert not can_write_clinical_records(Role.ANAESTHESIOLOGIST, is_treating_doctor=False)
    assert not can_write_clinical_records(Role.ADMIN, is_treating_doctor=False)


def test_admin_has_no_clinical_permissions() -> None:
    for perm in (Perm.CASE_READ, Perm.CASE_CREATE, Perm.CASE_EDIT, Perm.LABS_WRITE, Perm.KPI_READ):
        assert not has_perm(Role.ADMIN, perm)
    assert has_perm(Role.ADMIN, Perm.USERS_MANAGE)
    assert has_perm(Role.ADMIN, Perm.AUDIT_READ)
