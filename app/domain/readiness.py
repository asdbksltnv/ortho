"""Readiness is always computed from checklist state; it is never stored as an editable flag."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date

from app.domain.enums import Blocking, ItemStatus

_ENGAGED = frozenset({ItemStatus.PENDING, ItemStatus.PROBLEM})
_PASSING = frozenset({ItemStatus.DONE, ItemStatus.NOT_APPLICABLE})


@dataclass(frozen=True)
class ItemDef:
    key: str
    blocking: Blocking
    auto_applies_flag: str | None = None


@dataclass(frozen=True)
class ReadinessContext:
    today: date
    planned_surgery_date: date | None = None
    procedure_blocking_items: frozenset[str] = frozenset()
    flags: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Readiness:
    ready: bool
    blocking: tuple[str, ...]  # keys of applicable items that are not done / not_applicable
    applicable: tuple[str, ...]  # keys of items whose blocking rule applies


def item_applies(defn: ItemDef, status: ItemStatus, ctx: ReadinessContext) -> bool:
    """Whether the item's blocking rule applies to this case right now."""
    if status is ItemStatus.NOT_APPLICABLE:
        return False
    if defn.blocking is Blocking.ALWAYS:
        return True
    if defn.blocking is Blocking.DAY_OF_SURGERY:
        return ctx.planned_surgery_date is not None and ctx.today >= ctx.planned_surgery_date
    if defn.blocking is Blocking.PER_PROCEDURE:
        required = defn.key in ctx.procedure_blocking_items
    else:  # IF_APPLICABLE
        required = defn.auto_applies_flag is not None and defn.auto_applies_flag in ctx.flags
    # Someone who set a not-yet-required item to pending/problem has engaged it: wait for it.
    return required or status in _ENGAGED


def compute_readiness(
    defs: Iterable[ItemDef],
    statuses: Mapping[str, ItemStatus],
    ctx: ReadinessContext,
) -> Readiness:
    applicable: list[str] = []
    blocking: list[str] = []
    for defn in defs:
        status = statuses.get(defn.key, ItemStatus.NOT_STARTED)
        if not item_applies(defn, status, ctx):
            continue
        applicable.append(defn.key)
        if status not in _PASSING:
            blocking.append(defn.key)
    return Readiness(ready=not blocking, blocking=tuple(blocking), applicable=tuple(applicable))
