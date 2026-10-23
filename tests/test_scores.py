from datetime import date
from pathlib import Path

import pytest

from app.domain.caprini import Category, Factor, age_on, categorize, compute_caprini
from app.domain.columbia import ColumbiaLogic, UrgentRule, urgent_consult_alert, visible_questions
from app.domain.numbers import bmi, format_number
from app.domain.nutrition import compute_nutrition
from app.services.config_loader import load_config
from app.services.intake import caprini_categories, caprini_factors, columbia_logic

CONFIG = load_config(Path(__file__).resolve().parents[1] / "config")
FACTORS = caprini_factors(CONFIG)
CATEGORIES = caprini_categories(CONFIG)


def score(manual: list[str], age: int | None = 30, bmi_value: float | None = 22.0):  # type: ignore[no-untyped-def]
    return compute_caprini(FACTORS, CATEGORIES, manual=manual, age=age, bmi_value=bmi_value)


@pytest.mark.parametrize(
    ("manual", "total", "category"),
    [
        ([], 0, "very_low"),
        (["minor_surgery"], 1, "low"),
        (["arthroscopic_surgery"], 2, "low"),
        (["minor_surgery", "swollen_legs"], 2, "low"),
        (["vte_history"], 3, "moderate"),
        (["arthroscopic_surgery", "varicose_veins"], 3, "moderate"),
        (["arthroscopic_surgery", "malignancy"], 4, "moderate"),
        (["hip_pelvis_leg_fracture"], 5, "high"),
        (["vte_history", "arthroscopic_surgery", "minor_surgery"], 6, "high"),
    ],
)
def test_category_boundaries_0_to_5(manual: list[str], total: int, category: str) -> None:
    result = score(manual)
    assert (result.total, result.category_key) == (total, category)


@pytest.mark.parametrize(
    ("age", "points"),
    [(40, 0), (41, 1), (60, 1), (61, 2), (74, 2), (75, 3), (99, 3)],
)
def test_age_factors_are_automatic_and_exclusive(age: int, points: int) -> None:
    assert score([], age=age).total == points


def test_bmi_factor_is_strictly_over_25() -> None:
    assert score([], bmi_value=25.0).total == 0
    assert score([], bmi_value=25.1).total == 1


def test_manual_age_and_bmi_ticks_are_overridden_by_known_values() -> None:
    result = score(["age_75_plus", "bmi_over_25"], age=30, bmi_value=20.0)
    assert result.total == 0


def test_manual_bmi_counts_only_when_bmi_is_unknown() -> None:
    assert score(["bmi_over_25"], bmi_value=None).total == 1


def test_automatic_factors_are_reported() -> None:
    result = score([], age=65, bmi_value=30)
    assert set(result.automatic) == {"age_61_74", "bmi_over_25"}
    assert result.total == 3


def test_unknown_manual_keys_are_ignored() -> None:
    assert score(["nonsense"]).total == 0


def test_caprini_points_match_the_build_prompt() -> None:
    points = {f.key: f.points for f in FACTORS}
    assert sum(1 for p in points.values() if p == 1) == 15
    assert sum(1 for p in points.values() if p == 2) == 8
    assert sum(1 for p in points.values() if p == 3) == 10
    assert sum(1 for p in points.values() if p == 5) == 4


def test_age_on_birthday_boundaries() -> None:
    born = date(1985, 3, 10)
    assert age_on(born, date(2026, 3, 9)) == 40
    assert age_on(born, date(2026, 3, 10)) == 41
    assert age_on(date(2000, 2, 29), date(2026, 2, 28)) == 25


def test_categorize_rejects_scores_outside_every_range() -> None:
    with pytest.raises(ValueError):
        categorize(-1, [Category("a", "A", 0, None)])
    assert Factor("k", 1, "x").auto is None


LOGIC = columbia_logic(CONFIG)


def answers(**kw: bool | None) -> dict[int, bool | None]:
    return {i: kw.get(f"q{i}") for i in range(1, 8)}


def test_columbia_followups_hidden_until_q1_or_q2_is_yes() -> None:
    assert visible_questions(LOGIC, answers()) == [1, 2, 7]
    assert visible_questions(LOGIC, answers(q1=False, q2=False)) == [1, 2, 7]
    assert visible_questions(LOGIC, answers(q1=True)) == [1, 2, 3, 4, 5, 6, 7]
    assert visible_questions(LOGIC, answers(q2=True)) == [1, 2, 3, 4, 5, 6, 7]


def test_columbia_q7_is_always_asked() -> None:
    assert 7 in visible_questions(LOGIC, answers())


@pytest.mark.parametrize(
    ("a", "alert"),
    [
        (answers(q1=True, q4=True, q5=True), True),
        (answers(q2=True, q4=True, q6=True), True),
        (answers(q1=True, q4=True), False),
        (answers(q1=True, q5=True, q6=True), False),
        (answers(q4=True, q5=True), False),  # follow-ups hidden: never counted
        (answers(), False),
    ],
)
def test_columbia_default_urgent_rule(a: dict[int, bool | None], alert: bool) -> None:
    assert urgent_consult_alert(LOGIC, a) is alert


def test_columbia_rule_is_configurable() -> None:
    logic = ColumbiaLogic((1, 2, 7), (3, 4, 5, 6), (1, 2), UrgentRule(any_yes=(7,)))
    assert urgent_consult_alert(logic, answers(q7=True)) is True
    assert (
        urgent_consult_alert(ColumbiaLogic((1,), (), (1,), UrgentRule()), answers(q1=True)) is False
    )


def test_nutrition_bmi_answered_automatically() -> None:
    low = compute_nutrition(
        bmi_value=20.4,
        bmi_threshold=20.5,
        weight_loss=False,
        reduced_intake=False,
        stress_factor=False,
    )
    assert low.bmi_low is True and low.total == 1 and low.complete
    edge = compute_nutrition(
        bmi_value=20.5,
        bmi_threshold=20.5,
        weight_loss=True,
        reduced_intake=None,
        stress_factor=None,
    )
    assert edge.bmi_low is False and edge.total == 1 and not edge.complete
    unknown = compute_nutrition(
        bmi_value=None,
        bmi_threshold=20.5,
        weight_loss=True,
        reduced_intake=True,
        stress_factor=True,
    )
    assert unknown.bmi_low is None and unknown.total == 3 and not unknown.complete


@pytest.mark.parametrize(
    ("value", "sep", "expected"),
    [
        (36.6, ",", "36,6"),
        (36.60, ".", "36.6"),
        (85, ",", "85"),
        (85.0, ",", "85"),
        (0.5, ",", "0,5"),
        (100, ",", "100"),
        (None, ",", ""),
        ("", ",", ""),
        ("abc", ",", ""),
        (1e-7, ",", "0,0000001"),
    ],
)
def test_format_number(value: object, sep: str, expected: str) -> None:
    assert format_number(value, sep) == expected  # type: ignore[arg-type]


def test_bmi_calculation() -> None:
    assert bmi(92, 170) == pytest.approx(31.83, abs=0.01)
    assert bmi(None, 170) is None and bmi(80, 0) is None
