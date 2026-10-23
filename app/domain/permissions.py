"""Permission matrix (BUILD_PROMPT section 4). Pure functions; the API layer calls these."""

from enum import StrEnum

from app.domain.enums import Role


class Perm(StrEnum):
    CASE_READ = "case.read"
    CASE_CREATE = "case.create"
    CASE_EDIT = "case.edit"  # doctors: own patients only (see can_edit_case)
    LABS_WRITE = "labs.write"
    CONSENT_WRITE = "consent.write"
    USERS_MANAGE = "users.manage"
    WARDS_MANAGE = "wards.manage"
    AUDIT_READ = "audit.read"
    KPI_READ = "kpi.read"
    CONFIG_STATUS_READ = "config.status.read"
    ANAESTHESIA_WRITE = "anaesthesia.write"
    ORDER_CREATE = "order.create"
    POSTOP_WRITE = "postop.write"


_CLINICAL_READERS = {
    Role.DOCTOR,
    Role.NURSE,
    Role.ANAESTHESIOLOGIST,
    Role.HEAD_OF_DEPARTMENT,
    Role.HEAD_NURSE,
}

ROLE_PERMS: dict[Perm, frozenset[Role]] = {
    Perm.CASE_READ: frozenset(_CLINICAL_READERS),
    Perm.CASE_CREATE: frozenset({Role.DOCTOR, Role.HEAD_OF_DEPARTMENT}),
    Perm.CASE_EDIT: frozenset({Role.DOCTOR, Role.HEAD_OF_DEPARTMENT}),
    Perm.LABS_WRITE: frozenset({Role.NURSE, Role.HEAD_NURSE, Role.DOCTOR, Role.HEAD_OF_DEPARTMENT}),
    Perm.CONSENT_WRITE: frozenset(
        {Role.NURSE, Role.HEAD_NURSE, Role.DOCTOR, Role.HEAD_OF_DEPARTMENT}
    ),
    Perm.USERS_MANAGE: frozenset({Role.ADMIN}),
    Perm.WARDS_MANAGE: frozenset({Role.ADMIN}),
    Perm.AUDIT_READ: frozenset({Role.ADMIN, Role.HEAD_OF_DEPARTMENT}),
    Perm.KPI_READ: frozenset({Role.HEAD_OF_DEPARTMENT, Role.HEAD_NURSE}),
    Perm.CONFIG_STATUS_READ: frozenset({Role.ADMIN}),
    Perm.ANAESTHESIA_WRITE: frozenset({Role.ANAESTHESIOLOGIST, Role.HEAD_OF_DEPARTMENT}),
    Perm.ORDER_CREATE: frozenset({Role.DOCTOR, Role.HEAD_OF_DEPARTMENT}),
    Perm.POSTOP_WRITE: frozenset({Role.DOCTOR, Role.HEAD_OF_DEPARTMENT}),
}

# Items a nurse may update besides those she owns: the consent received on the ward.
_NURSE_EXTRA_ITEMS = frozenset({"consent_surgical"})
# Only the anaesthesiologist (or head of department) decides anaesthesia clearance.
_ANAESTHESIA_ITEM = "anaesthesia"


def has_perm(role: Role, perm: Perm) -> bool:
    return role in ROLE_PERMS[perm]


def can_edit_case(role: Role, *, is_treating_doctor: bool) -> bool:
    """Doctors edit their own patients; head of department edits any."""
    if role is Role.HEAD_OF_DEPARTMENT:
        return True
    return role is Role.DOCTOR and is_treating_doctor


def can_write_clinical_records(role: Role, *, is_treating_doctor: bool) -> bool:
    """Labs and consents: nurses on any case, doctors on their own, head roles on any."""
    if role in {Role.NURSE, Role.HEAD_NURSE, Role.HEAD_OF_DEPARTMENT}:
        return True
    return role is Role.DOCTOR and is_treating_doctor


def can_edit_checklist_item(
    role: Role, *, item_key: str, item_owner: Role, is_treating_doctor: bool
) -> bool:
    if role is Role.HEAD_OF_DEPARTMENT:
        return True
    if role is Role.ANAESTHESIOLOGIST:
        return item_key == _ANAESTHESIA_ITEM
    if role in {Role.NURSE, Role.HEAD_NURSE}:
        return item_owner is Role.NURSE or item_key in _NURSE_EXTRA_ITEMS
    if role is Role.DOCTOR:
        return is_treating_doctor and item_key != _ANAESTHESIA_ITEM
    return False  # admin has no clinical edit rights
