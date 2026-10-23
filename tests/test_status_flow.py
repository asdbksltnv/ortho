import itertools

import pytest

from app.domain.enums import CaseStatus, Role
from app.domain.status_flow import FORWARD, Refusal, available_targets, decide_transition

S = CaseStatus
R = Role


def decide(current, target, role=R.HEAD_OF_DEPARTMENT, **kw):  # type: ignore[no-untyped-def]
    args = {
        "role": role,
        "is_treating_doctor": True,
        "ready": True,
        "is_emergency": False,
        "reason": None,
        "has_planned_date": True,
    }
    args.update(kw)
    return decide_transition(current, target, **args)


def test_every_status_is_reachable_in_the_documented_order() -> None:
    chain = [
        S.ADMITTED,
        S.IN_PREPARATION,
        S.APPROVED_FOR_SURGERY,
        S.CALLED_TO_OR,
        S.LEFT_WARD,
        S.IN_OR,
    ]
    for a, b in itertools.pairwise(chain):
        assert b in FORWARD[a]
    assert set(FORWARD[S.IN_OR]) == {S.RETURNED_TO_WARD, S.TRANSFERRED_ICU}
    assert S.POST_OP in FORWARD[S.RETURNED_TO_WARD] and S.POST_OP in FORWARD[S.TRANSFERRED_ICU]
    assert FORWARD[S.POST_OP] == (S.DISCHARGED,) and FORWARD[S.DISCHARGED] == ()


@pytest.mark.parametrize("target", [t for t in CaseStatus if t is not S.IN_PREPARATION])
def test_skipping_steps_is_not_allowed(target: CaseStatus) -> None:
    d = decide(S.ADMITTED, target)
    assert not d.allowed and d.refusal is Refusal.NOT_ALLOWED


def test_only_head_of_department_approves_for_surgery() -> None:
    for role in R:
        d = decide(S.IN_PREPARATION, S.APPROVED_FOR_SURGERY, role=role)
        assert d.allowed is (role is R.HEAD_OF_DEPARTMENT), role


def test_approval_needs_a_planned_date() -> None:
    d = decide(S.IN_PREPARATION, S.APPROVED_FOR_SURGERY, has_planned_date=False)
    assert d.refusal is Refusal.PLANNED_DATE_REQUIRED


def test_call_to_or_needs_a_ready_case() -> None:
    d = decide(S.APPROVED_FOR_SURGERY, S.CALLED_TO_OR, role=R.DOCTOR, ready=False)
    assert not d.allowed and d.refusal is Refusal.NOT_READY
    assert decide(S.APPROVED_FOR_SURGERY, S.CALLED_TO_OR, role=R.DOCTOR, ready=True).allowed


def test_head_override_requires_a_reason_and_is_flagged() -> None:
    no_reason = decide(S.APPROVED_FOR_SURGERY, S.CALLED_TO_OR, ready=False)
    assert not no_reason.allowed and no_reason.refusal is Refusal.OVERRIDE_REASON_REQUIRED
    blank = decide(S.APPROVED_FOR_SURGERY, S.CALLED_TO_OR, ready=False, reason="   ")
    assert blank.refusal is Refusal.OVERRIDE_REASON_REQUIRED
    ok = decide(S.APPROVED_FOR_SURGERY, S.CALLED_TO_OR, ready=False, reason="срочно")
    assert ok.allowed and ok.is_override


def test_doctor_cannot_override_even_with_a_reason() -> None:
    d = decide(S.APPROVED_FOR_SURGERY, S.CALLED_TO_OR, role=R.DOCTOR, ready=False, reason="срочно")
    assert not d.allowed and d.refusal is Refusal.NOT_READY


def test_ready_case_is_never_flagged_as_override() -> None:
    d = decide(S.APPROVED_FOR_SURGERY, S.CALLED_TO_OR, ready=True, reason="лишнее")
    assert d.allowed and not d.is_override


def test_emergency_is_not_blocked_by_the_checklist() -> None:
    d = decide(
        S.APPROVED_FOR_SURGERY, S.CALLED_TO_OR, role=R.DOCTOR, ready=False, is_emergency=True
    )
    assert d.allowed and not d.is_override


def test_doctors_act_only_on_their_own_patients() -> None:
    assert not decide(S.ADMITTED, S.IN_PREPARATION, role=R.DOCTOR, is_treating_doctor=False).allowed
    assert decide(S.ADMITTED, S.IN_PREPARATION, role=R.DOCTOR).allowed
    assert decide(
        S.ADMITTED, S.IN_PREPARATION, role=R.HEAD_OF_DEPARTMENT, is_treating_doctor=False
    ).allowed


def test_leaving_the_ward_is_set_by_nurses() -> None:
    for role in R:
        d = decide(S.CALLED_TO_OR, S.LEFT_WARD, role=role)
        assert d.allowed is (role in {R.NURSE, R.HEAD_NURSE}), role


@pytest.mark.parametrize("role", [R.ANAESTHESIOLOGIST, R.ADMIN])
def test_anaesthesiologist_and_admin_never_move_cases(role: Role) -> None:
    for current, targets in FORWARD.items():
        for target in targets:
            assert not decide(current, target, role=role).allowed


def test_post_op_steps_for_ward_staff_and_doctors() -> None:
    for target in (S.RETURNED_TO_WARD, S.TRANSFERRED_ICU):
        assert decide(S.IN_OR, target, role=R.NURSE).allowed
        assert decide(S.IN_OR, target, role=R.DOCTOR).allowed
    assert decide(S.TRANSFERRED_ICU, S.RETURNED_TO_WARD, role=R.NURSE).allowed
    assert decide(S.RETURNED_TO_WARD, S.POST_OP, role=R.NURSE).allowed
    assert not decide(S.POST_OP, S.DISCHARGED, role=R.NURSE).allowed
    assert decide(S.POST_OP, S.DISCHARGED, role=R.DOCTOR).allowed


def test_reversals_are_head_only_and_need_a_reason() -> None:
    cancel = decide(S.CALLED_TO_OR, S.APPROVED_FOR_SURGERY)
    assert cancel.refusal is Refusal.REASON_REQUIRED
    assert decide(S.CALLED_TO_OR, S.APPROVED_FOR_SURGERY, reason="отмена").allowed
    assert decide(S.APPROVED_FOR_SURGERY, S.IN_PREPARATION, reason="пересмотр").allowed
    d = decide(S.CALLED_TO_OR, S.APPROVED_FOR_SURGERY, role=R.DOCTOR, reason="отмена")
    assert d.refusal is Refusal.FORBIDDEN
    assert not decide(S.LEFT_WARD, S.CALLED_TO_OR, reason="x").allowed  # no other way back


def test_available_targets_follow_the_role() -> None:
    assert available_targets(
        S.IN_PREPARATION, role=R.HEAD_OF_DEPARTMENT, is_treating_doctor=False
    ) == [S.APPROVED_FOR_SURGERY]
    assert available_targets(S.IN_PREPARATION, role=R.DOCTOR, is_treating_doctor=True) == []
    assert available_targets(S.APPROVED_FOR_SURGERY, role=R.DOCTOR, is_treating_doctor=True) == [
        S.CALLED_TO_OR
    ]
    assert set(
        available_targets(
            S.APPROVED_FOR_SURGERY, role=R.HEAD_OF_DEPARTMENT, is_treating_doctor=False
        )
    ) == {
        S.CALLED_TO_OR,
        S.IN_PREPARATION,
    }
    assert available_targets(S.CALLED_TO_OR, role=R.NURSE, is_treating_doctor=False) == [
        S.LEFT_WARD
    ]
    assert (
        available_targets(S.DISCHARGED, role=R.HEAD_OF_DEPARTMENT, is_treating_doctor=False) == []
    )
    assert available_targets(S.ADMITTED, role=R.ADMIN, is_treating_doctor=False) == []
