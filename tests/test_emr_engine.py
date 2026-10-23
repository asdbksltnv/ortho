"""Pure rendering-engine behaviour, independent of the real EMR templates."""

from typing import Any

from app.domain.emr import (
    PREFILL_HINT,
    EmrType,
    FieldSpec,
    RenderInput,
    TemplateSpec,
    format_datetime_ru,
    get_path,
    render_template,
)
from app.services.documents import jinja_env


def spec(*fields: FieldSpec, tid: str = "t") -> TemplateSpec:
    return TemplateSpec(tid, "T", 1, "ready", tuple(fields))


def field(key: str, typ: EmrType = EmrType.TEXT, **kw: Any) -> FieldSpec:
    return FieldSpec(key=key, section="S", label=key.upper(), emr_type=typ, **kw)


def render(template: TemplateSpec, data: dict[str, Any], **kw: Any) -> dict[str, Any]:
    templates = {template.id: template, **kw.pop("others", {})}
    inp = RenderInput(
        env=jinja_env(), templates=templates, data=data, facts=kw.pop("facts", {}), **kw
    )
    return {f.key: f for f in render_template(template, inp)}


def test_get_path() -> None:
    assert get_path({"a": {"b": 1}}, "a.b") == 1
    assert get_path({"a": {"b": 1}}, "a.c") is None
    assert get_path({"a": 1}, None) is None


def test_number_uses_configured_separator_and_no_units() -> None:
    f = render(spec(field("t", EmrType.NUMBER, path="v.t")), {"v": {"t": 36.6}}, separator=",")
    assert f["t"].value == "36,6"
    f = render(spec(field("t", EmrType.NUMBER, path="v.t")), {"v": {"t": 36.6}}, separator=".")
    assert f["t"].value == "36.6"


def test_critical_empty_field_is_missing_but_optional_is_not() -> None:
    f = render(
        spec(
            field("a", critical=True, path="x"),
            field("b", path="x"),
            field("c", required=True, path="x"),
        ),
        {},
    )
    assert (f["a"].missing, f["b"].missing, f["c"].missing) == (True, False, True)


def test_calculate_skip_and_checkcombo_have_no_value() -> None:
    f = render(
        spec(
            field("bmi", EmrType.CALCULATE, source="skip"),
            field("e", source="skip"),
            field("combo", EmrType.CHECKCOMBO),
        ),
        {},
    )
    assert f["bmi"].display == "calculate" and f["bmi"].value is None
    assert f["e"].display == "skip"
    assert f["combo"].display == "manual" and not f["combo"].missing


def test_critical_calculate_is_never_missing() -> None:
    f = render(spec(field("bmi", EmrType.CALCULATE, critical=True, source="skip")), {})
    assert f["bmi"].missing is False


def test_default_and_fallback_paths() -> None:
    f = render(
        spec(
            field("hr", EmrType.NUMBER, path="v.hr", fallback_path="v.pulse"),
            field("d", path="x", default_ru="Сверено"),
        ),
        {"v": {"pulse": 70}},
    )
    assert f["hr"].value == "70" and f["d"].value == "Сверено"


def test_override_replaces_copied_value() -> None:
    base = spec(field("g", path="g"), tid="a")
    other = spec(field("g", source="copy:a.g", override_path="o"), tid="b")
    f = render(other, {"g": "старое", "o": "новое"}, others={"a": base})
    assert f["g"].value == "новое"
    f = render(other, {"g": "старое", "o": ""}, others={"a": base})
    assert f["g"].value == "старое"


def test_copy_cycles_resolve_to_empty_instead_of_looping() -> None:
    a = spec(field("x", source="copy:b.x"), tid="a")
    b = spec(field("x", source="copy:a.x"), tid="b")
    f = render(a, {}, others={"b": b})
    assert f["x"].value is None


def test_system_finding_prefill_rules() -> None:
    sys_field = field("skin", path="systems.skin", format="system", emr_prefill=True)
    plain = field("skin", path="systems.skin", format="system")
    data_normal = {"systems": {"skin": {"normal": True, "text": ""}}}
    data_changed = {"systems": {"skin": {"normal": False, "text": "Сыпь"}}}
    assert render(spec(sys_field), data_normal)["skin"].display == "keep_emr"
    changed = render(spec(sys_field), data_changed)["skin"]
    assert (changed.display, changed.value, changed.hint) == ("value", "Сыпь", PREFILL_HINT)
    # without EMR prefill the configured normal sentence is the value
    f = render(spec(plain), data_normal, system_defaults={"skin": "Кожа чистая"})
    assert f["skin"].value == "Кожа чистая"
    f = render(spec(plain), data_normal, system_defaults={"skin": None})
    assert f["skin"].value is None


def test_keep_if_empty_prefill() -> None:
    a = spec(field("e", path="e"), tid="a")
    b = spec(field("e", source="copy:a.e", emr_prefill=True, keep_if_empty=True), tid="b")
    assert render(b, {"e": ""}, others={"a": a})["e"].display == "keep_emr"
    kept = render(b, {"e": "гепатит"}, others={"a": a})["e"]
    assert (kept.display, kept.value, kept.hint) == ("value", "гепатит", PREFILL_HINT)


def test_icd_and_service_and_medication_items() -> None:
    f = render(
        spec(
            field("dx", EmrType.ICD10, path="dx"),
            field("dxs", EmrType.ICD10, path="dxs"),
            field("lab", EmrType.SERVICE, path="lab"),
            field("med", EmrType.MEDICATION, path="med"),
        ),
        {
            "dx": {"code": "A1", "text": "Текст"},
            "dxs": [{"code": "B", "text": ""}, {"code": "", "text": ""}],
            "lab": ["ОАК", " "],
            "med": [{"name": "Х", "note": "1 р/д"}, {"name": "", "note": "?"}],
        },
    )
    assert f["dx"].icd == [{"code": "A1", "text": "Текст"}]
    assert f["dxs"].icd == [{"code": "B", "text": ""}]
    assert f["lab"].items == ["ОАК"] and f["med"].items == ["Х — 1 р/д"]


def test_staff_schedule_and_case_sources() -> None:
    from datetime import datetime

    f = render(
        spec(
            field("doc", EmrType.STAFF, source="staff", staff="head"),
            field("when", EmrType.DATETIME, source="schedule"),
            field("an", source="case", path="anaesthesia_type"),
            field("risk", source="procedure", path="surgery_texts.risks"),
        ),
        {},
        staff={"head": "Иванов"},
        schedule=datetime(2026, 3, 1, 8, 5),
        case_values={"anaesthesia_type": " Спинальная "},
        procedure_texts={"risks": None},
    )
    assert f["doc"].value == "Иванов" and f["when"].value == "01.03.2026 08:05"
    assert f["an"].value == "Спинальная" and f["risk"].value is None
    assert format_datetime_ru(None) == ""


def test_followup_fields_hidden_by_facts() -> None:
    q = field("q3", path="c.q3", format="yesno", only_if="columbia_followup")
    hidden = render(spec(q), {"c": {"q3": False}}, facts={"columbia_followup_visible": False})["q3"]
    shown = render(spec(q), {"c": {"q3": False}}, facts={"columbia_followup_visible": True})["q3"]
    assert hidden.display == "skip" and shown.value == "Нет"


def test_generated_text_is_whitespace_normalised() -> None:
    f = render(
        spec(field("g", source="generated", generator="general_condition")),
        {"general": {"severity": "средней  тяжести", "consciousness": "ясное", "position": None}},
    )
    assert f["g"].value == "Состояние средней тяжести. Сознание ясное."
