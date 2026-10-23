"""Columbia screen display logic and the (configurable) urgent-consultation alert."""

from collections.abc import Collection, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class UrgentRule:
    all_yes: tuple[int, ...] = ()
    any_yes: tuple[int, ...] = ()


@dataclass(frozen=True)
class ColumbiaLogic:
    always_ask: tuple[int, ...]
    follow_up: tuple[int, ...]
    follow_up_trigger: tuple[int, ...]
    urgent: UrgentRule


def visible_questions(logic: ColumbiaLogic, answers: Mapping[int, bool | None]) -> list[int]:
    """Questions to show: always-asked ones, plus the follow-ups once a trigger answer is «да»."""
    triggered = any(answers.get(n) is True for n in logic.follow_up_trigger)
    shown = set(logic.always_ask) | (set(logic.follow_up) if triggered else set())
    return sorted(shown)


def urgent_consult_alert(logic: ColumbiaLogic, answers: Mapping[int, bool | None]) -> bool:
    """True when the configured rule is met. Hidden questions never count as «да»."""
    shown = set(visible_questions(logic, answers))

    def yes(n: int) -> bool:
        return n in shown and answers.get(n) is True

    rule = logic.urgent
    if not rule.all_yes and not rule.any_yes:
        return False
    all_ok = all(yes(n) for n in rule.all_yes)
    any_ok = not rule.any_yes or any(yes(n) for n in rule.any_yes)
    return all_ok and any_ok


def answered_yes(answers: Mapping[int, bool | None], visible: Collection[int]) -> list[int]:
    return [n for n in sorted(visible) if answers.get(n) is True]
