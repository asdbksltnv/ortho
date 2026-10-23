"""Case status flow, who may move a case, and the call-to-OR readiness rule (section 6.4).

admitted -> in_preparation -> approved_for_surgery -> called_to_or -> left_ward -> in_or
  -> returned_to_ward | transferred_icu -> post_op -> discharged
"""

from dataclasses import dataclass
from enum import StrEnum

from app.domain.enums import CaseStatus, Role

S = CaseStatus

FORWARD: dict[CaseStatus, tuple[CaseStatus, ...]] = {
    S.ADMITTED: (S.IN_PREPARATION,),
    S.IN_PREPARATION: (S.APPROVED_FOR_SURGERY,),
    S.APPROVED_FOR_SURGERY: (S.CALLED_TO_OR,),
    S.CALLED_TO_OR: (S.LEFT_WARD,),
    S.LEFT_WARD: (S.IN_OR,),
    S.IN_OR: (S.RETURNED_TO_WARD, S.TRANSFERRED_ICU),
    S.RETURNED_TO_WARD: (S.POST_OP,),
    S.TRANSFERRED_ICU: (S.POST_OP, S.RETURNED_TO_WARD),
    S.POST_OP: (S.DISCHARGED,),
    S.DISCHARGED: (),
}

# Backward moves always need a reason and are limited to the head of department.
REVERSALS: dict[CaseStatus, CaseStatus] = {
    S.APPROVED_FOR_SURGERY: S.IN_PREPARATION,  # approval revoked
    S.CALLED_TO_OR: S.APPROVED_FOR_SURGERY,  # call cancelled
}

_WARD_STAFF = {Role.NURSE, Role.HEAD_NURSE}
_DOCTORS = {Role.DOCTOR, Role.HEAD_OF_DEPARTMENT}


class Refusal(StrEnum):
    NOT_ALLOWED = "transition_not_allowed"  # not a valid step from the current status
    FORBIDDEN = "forbidden"  # valid step, wrong role
    NOT_READY = "not_ready"  # call to OR on a case that is not Ready
    OVERRIDE_REASON_REQUIRED = "override_reason_required"
    REASON_REQUIRED = "reason_required"
    PLANNED_DATE_REQUIRED = "planned_date_required"


@dataclass(frozen=True)
class Decision:
    allowed: bool
    refusal: Refusal | None = None
    is_override: bool = False  # head called the case to the OR although it was not Ready


def _allowed_roles(target: CaseStatus) -> set[Role]:
    if target in (S.IN_PREPARATION,):
        return set(_DOCTORS)
    if target is S.APPROVED_FOR_SURGERY:
        return {Role.HEAD_OF_DEPARTMENT}
    if target is S.CALLED_TO_OR:
        return set(_DOCTORS)
    if target is S.LEFT_WARD:
        return set(_WARD_STAFF)
    if target is S.DISCHARGED:
        return set(_DOCTORS)
    # in_or, returned_to_ward, transferred_icu, post_op: ward staff and doctors
    return set(_WARD_STAFF) | set(_DOCTORS)


def decide_transition(
    current: CaseStatus,
    target: CaseStatus,
    *,
    role: Role,
    is_treating_doctor: bool,
    ready: bool,
    is_emergency: bool,
    reason: str | None,
    has_planned_date: bool,
) -> Decision:
    reason = (reason or "").strip() or None
    if REVERSALS.get(current) is target:
        if role is not Role.HEAD_OF_DEPARTMENT:
            return Decision(False, Refusal.FORBIDDEN)
        if reason is None:
            return Decision(False, Refusal.REASON_REQUIRED)
        return Decision(True)

    if target not in FORWARD.get(current, ()):
        return Decision(False, Refusal.NOT_ALLOWED)

    roles = _allowed_roles(target)
    if role not in roles:
        return Decision(False, Refusal.FORBIDDEN)
    # Doctors act on their own patients; the head of department and ward staff on any.
    if role is Role.DOCTOR and not is_treating_doctor:
        return Decision(False, Refusal.FORBIDDEN)

    if target is S.APPROVED_FOR_SURGERY and not has_planned_date:
        return Decision(False, Refusal.PLANNED_DATE_REQUIRED)

    if target is S.CALLED_TO_OR and not ready and not is_emergency:
        # Only the head of department may override, and always with a reason.
        if role is not Role.HEAD_OF_DEPARTMENT:
            return Decision(False, Refusal.NOT_READY)
        if reason is None:
            return Decision(False, Refusal.OVERRIDE_REASON_REQUIRED)
        return Decision(True, is_override=True)

    return Decision(True)


def available_targets(
    current: CaseStatus, *, role: Role, is_treating_doctor: bool
) -> list[CaseStatus]:
    """Targets the UI may offer (readiness and reasons are checked when the move is made)."""
    candidates = [*FORWARD.get(current, ())]
    reversal = REVERSALS.get(current)
    if reversal is not None:
        candidates.append(reversal)
    out: list[CaseStatus] = []
    for target in candidates:
        decision = decide_transition(
            current,
            target,
            role=role,
            is_treating_doctor=is_treating_doctor,
            ready=True,
            is_emergency=False,
            reason="x",
            has_planned_date=True,
        )
        if decision.allowed:
            out.append(target)
    return out
