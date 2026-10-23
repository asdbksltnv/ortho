from datetime import date

import pytest

from app.domain.postop import (
    PostOpData,
    Thresholds,
    evaluate_alerts,
    llm_safe,
    note_input,
    post_op_day,
)


def test_post_op_day_counts_from_the_day_of_surgery() -> None:
    surgery = date(2026, 3, 10)
    assert post_op_day(surgery, date(2026, 3, 10)) == 0
    assert post_op_day(surgery, date(2026, 3, 12)) == 2
    assert post_op_day(surgery, date(2026, 3, 9)) == 0  # never negative


def data(**kw: object) -> PostOpData:
    return PostOpData.model_validate(kw)


def test_no_alerts_when_every_threshold_is_unset() -> None:
    d = data(
        vitals={"temp": 41},
        drain={"present": True, "output_ml": 4000},
        pain_vas=10,
        wound={"discharge": "гнойное"},
    )
    assert evaluate_alerts(d, Thresholds()) == []


def test_each_threshold_alerts_only_when_crossed() -> None:
    t = Thresholds(
        temperature_max=37.5, drain_output_ml_max=300, pain_vas_max=6, purulent_discharge=True
    )
    assert evaluate_alerts(data(vitals={"temp": 37.5}), t) == []  # equal is not above
    assert [a.code for a in evaluate_alerts(data(vitals={"temp": 37.6}), t)] == ["temperature"]
    assert [
        a.code for a in evaluate_alerts(data(drain={"present": True, "output_ml": 301}), t)
    ] == ["drain_output"]
    assert [a.code for a in evaluate_alerts(data(pain_vas=7), t)] == ["pain"]
    assert [a.code for a in evaluate_alerts(data(wound={"discharge": "гнойное"}), t)] == [
        "purulent_discharge"
    ]
    assert evaluate_alerts(data(wound={"discharge": "серозное"}), t) == []


def test_purulent_rule_can_be_switched_off_explicitly() -> None:
    assert (
        evaluate_alerts(data(wound={"discharge": "гнойное"}), Thresholds(purulent_discharge=False))
        == []
    )


def test_missing_values_never_alert() -> None:
    t = Thresholds(
        temperature_max=37, drain_output_ml_max=10, pain_vas_max=1, purulent_discharge=True
    )
    assert evaluate_alerts(data(), t) == []


@pytest.mark.parametrize("field", ["bp"])
def test_blood_pressure_format_is_validated(field: str) -> None:
    with pytest.raises(ValueError):
        data(vitals={field: "бред"})


def test_note_input_has_no_identifiers_and_llm_input_has_no_free_text() -> None:
    d = data(
        complaints="Иванов Алишер жалуется на боль", therapy={"analgesia": "препарат X"}, pain_vas=3
    )
    full = note_input(d, 2)
    assert full["complaints"] == "Иванов Алишер жалуется на боль"  # kept for the local template
    safe = llm_safe(full)
    assert "complaints" not in safe and "analgesia" not in safe["therapy"]
    assert safe["therapy"]["analgesia_given"] is True
    assert "Иванов" not in str(safe) and "препарат" not in str(safe)
    assert safe["post_op_day"] == 2 and safe["pain_vas"] == 3
    assert set(safe) == {
        "post_op_day",
        "pain_vas",
        "consciousness",
        "vitals",
        "wound",
        "drain",
        "neurovascular",
        "calf_tenderness",
        "mobilization",
        "therapy",
    }


def test_photo_key_is_part_of_the_schema_but_not_the_llm_input() -> None:
    d = data(photo_key="wound/x.jpg")
    assert "photo_key" not in llm_safe(note_input(d, 1))
