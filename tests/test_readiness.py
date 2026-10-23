from datetime import date

import pytest

from app.domain.enums import Blocking, ItemStatus
from app.domain.readiness import ItemDef, ReadinessContext, compute_readiness, item_applies

TODAY = date(2026, 3, 10)
D = ItemStatus


def ctx(**kw: object) -> ReadinessContext:
    return ReadinessContext(today=TODAY, **kw)  # type: ignore[arg-type]


ALWAYS = ItemDef("a", Blocking.ALWAYS)
PROC = ItemDef("p", Blocking.PER_PROCEDURE)
COND = ItemDef("c", Blocking.IF_APPLICABLE)
FLAG = ItemDef("f", Blocking.IF_APPLICABLE, auto_applies_flag="takes_anticoagulant")
DAY = ItemDef("d", Blocking.DAY_OF_SURGERY)


@pytest.mark.parametrize("status", list(ItemStatus))
def test_always_applies_unless_not_applicable(status: ItemStatus) -> None:
    assert item_applies(ALWAYS, status, ctx()) is (status is not D.NOT_APPLICABLE)


def test_per_procedure_blocks_only_when_template_requires_it() -> None:
    assert not item_applies(PROC, D.NOT_STARTED, ctx())
    assert item_applies(PROC, D.NOT_STARTED, ctx(procedure_blocking_items=frozenset({"p"})))
    assert not item_applies(PROC, D.NOT_APPLICABLE, ctx(procedure_blocking_items=frozenset({"p"})))


@pytest.mark.parametrize("status", [D.PENDING, D.PROBLEM])
def test_engaged_optional_items_block_until_resolved(status: ItemStatus) -> None:
    assert item_applies(PROC, status, ctx())
    assert item_applies(COND, status, ctx())


def test_if_applicable_without_flag_does_not_block() -> None:
    assert not item_applies(COND, D.NOT_STARTED, ctx())
    assert not item_applies(COND, D.DONE, ctx())


def test_if_applicable_auto_applies_from_case_flag() -> None:
    assert not item_applies(FLAG, D.NOT_STARTED, ctx())
    assert item_applies(FLAG, D.NOT_STARTED, ctx(flags=frozenset({"takes_anticoagulant"})))
    assert not item_applies(FLAG, D.NOT_APPLICABLE, ctx(flags=frozenset({"takes_anticoagulant"})))


def test_day_of_surgery_rule_boundaries() -> None:
    from datetime import timedelta

    assert not item_applies(DAY, D.NOT_STARTED, ctx())  # no planned date
    assert not item_applies(DAY, D.NOT_STARTED, ctx(planned_surgery_date=TODAY + timedelta(days=1)))
    assert item_applies(DAY, D.NOT_STARTED, ctx(planned_surgery_date=TODAY))
    assert item_applies(DAY, D.NOT_STARTED, ctx(planned_surgery_date=TODAY - timedelta(days=1)))


def test_ready_when_all_applicable_items_pass() -> None:
    result = compute_readiness([ALWAYS, PROC, COND], {"a": D.DONE}, ctx())
    assert result.ready and result.blocking == () and result.applicable == ("a",)


def test_not_ready_lists_blocking_keys_in_definition_order() -> None:
    defs = [ALWAYS, ItemDef("b", Blocking.ALWAYS), ItemDef("z", Blocking.ALWAYS)]
    result = compute_readiness(defs, {"a": D.DONE, "z": D.PROBLEM}, ctx())
    assert not result.ready and result.blocking == ("b", "z")


def test_not_applicable_counts_as_passing() -> None:
    assert compute_readiness([ALWAYS], {"a": D.NOT_APPLICABLE}, ctx()).ready


def test_missing_status_means_not_started() -> None:
    assert not compute_readiness([ALWAYS], {}, ctx()).ready


def test_no_definitions_is_ready() -> None:
    assert compute_readiness([], {}, ctx()).ready
