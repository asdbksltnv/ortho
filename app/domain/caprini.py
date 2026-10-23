"""Caprini VTE risk score. Factors and categories come from config/caprini.yaml."""

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class AutoRule:
    type: str  # "age" | "bmi_over"
    min: int | None = None
    max: int | None = None
    value: float | None = None


@dataclass(frozen=True)
class Factor:
    key: str
    points: int
    label_ru: str
    auto: AutoRule | None = None


@dataclass(frozen=True)
class Category:
    key: str
    label_ru: str
    min: int
    max: int | None


@dataclass(frozen=True)
class CapriniResult:
    total: int
    category_key: str
    category_label_ru: str
    selected: tuple[str, ...]  # factor keys that count (manual + automatic)
    automatic: tuple[str, ...]


def age_on(birth_date: date, on: date) -> int:
    years = on.year - birth_date.year
    if (on.month, on.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def _auto_applies(rule: AutoRule, age: int | None, bmi_value: float | None) -> bool | None:
    """True/False when the rule can be evaluated, None when the input is missing."""
    if rule.type == "age":
        if age is None:
            return None
        return (rule.min is None or age >= rule.min) and (rule.max is None or age <= rule.max)
    if rule.type == "bmi_over":
        if bmi_value is None or rule.value is None:
            return None
        return bmi_value > rule.value
    return None


def categorize(total: int, categories: Iterable[Category]) -> Category:
    for category in categories:
        if total >= category.min and (category.max is None or total <= category.max):
            return category
    raise ValueError(f"no Caprini category for score {total}")


def compute_caprini(
    factors: Collection[Factor],
    categories: Iterable[Category],
    *,
    manual: Collection[str],
    age: int | None,
    bmi_value: float | None,
) -> CapriniResult:
    """Automatic factors (age, BMI) override manual ticks when their input is known; when it is
    missing (e.g. no height yet) a manual tick of that factor still counts."""
    counted: list[str] = []
    automatic: list[str] = []
    total = 0
    for factor in factors:
        if factor.auto is not None:
            applies = _auto_applies(factor.auto, age, bmi_value)
            if applies is None:
                applies = factor.key in manual
            elif applies:
                automatic.append(factor.key)
        else:
            applies = factor.key in manual
        if applies:
            counted.append(factor.key)
            total += factor.points
    category = categorize(total, categories)
    return CapriniResult(total, category.key, category.label_ru, tuple(counted), tuple(automatic))
