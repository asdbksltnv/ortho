"""EMR (AccuracyMed) document rendering: field by field, in the exact order of the EMR screen.

Pure and deterministic: no database, no clock, no LLM. Sentences come from Jinja2 templates
(`app/templates_ru`) fed only with facts recorded in the intake form.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from jinja2 import Environment

from app.domain.numbers import format_number

KEEP_EMR_LABEL = "Оставить текст EMR"
PREFILL_HINT = "Выделите всё в поле EMR перед вставкой"
CALCULATE_LABEL = "Рассчитывается в EMR"


class EmrType(StrEnum):
    TEXT = "text"
    LINE = "line"
    NUMBER = "number"
    CALCULATE = "calculate"
    ICD10 = "icd10"
    SERVICE = "service"
    MEDICATION = "medication"
    STAFF = "staff"
    CHECKCOMBO = "checkcombo"
    DATETIME = "datetime"


@dataclass(frozen=True)
class FieldSpec:
    key: str
    section: str
    label: str
    emr_type: EmrType
    critical: bool = False
    source: str = "form"
    generator: str | None = None
    path: str | None = None
    fallback_path: str | None = None
    override_path: str | None = None
    format: str | None = None
    emr_prefill: bool = False
    keep_if_empty: bool = False
    default_ru: str | None = None
    staff: str | None = None
    hint: str | None = None
    required: bool = False  # required by the app (not by the EMR) before generation
    only_if: str | None = None


@dataclass(frozen=True)
class TemplateSpec:
    id: str
    title_ru: str
    version: int
    status: str  # ready | awaiting_template
    fields: tuple[FieldSpec, ...]
    gating_items: tuple[str, ...] = ()
    scope: str = "case"  # case | postop_entry


@dataclass
class RenderedField:
    key: str
    section: str
    label: str
    emr_type: str
    critical: bool
    display: str  # value | keep_emr | calculate | manual | skip
    value: str | None = None
    items: list[str] | None = None
    icd: list[dict[str, str]] | None = None
    hint: str | None = None
    missing: bool = False
    locked: bool = False  # AI/template draft not yet marked «Проверено»: copying is disabled

    def comparable(self) -> tuple[Any, ...]:
        """What the doctor would paste; used to detect that a stored document is outdated."""
        icd = tuple((e["code"], e["text"]) for e in self.icd) if self.icd else None
        items = tuple(self.items) if self.items else None
        return (self.display, self.value, items, icd)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "section": self.section,
            "label": self.label,
            "emr_type": self.emr_type,
            "critical": self.critical,
            "display": self.display,
            "value": self.value,
            "items": self.items,
            "icd": self.icd,
            "hint": self.hint,
            "missing": self.missing,
            "locked": self.locked,
        }


@dataclass
class RenderInput:
    env: Environment
    templates: dict[str, TemplateSpec]
    data: dict[str, Any]  # IntakeData as JSON-compatible dict
    facts: dict[str, Any]  # derived values for sentence templates
    separator: str = ","
    staff: dict[str, str | None] = field(default_factory=dict)
    schedule: datetime | None = None  # planned OR start, already in the display time zone
    procedure_texts: dict[str, str | None] = field(default_factory=dict)
    case_values: dict[str, str | None] = field(default_factory=dict)
    studies: list[str] = field(default_factory=list)
    system_defaults: dict[str, str | None] = field(default_factory=dict)
    notes: dict[str, str | None] = field(default_factory=dict)  # NoteGenerator output
    notes_approved: bool = False
    _cache: dict[str, list[RenderedField]] = field(default_factory=dict)


# ------------------------------------------------------------------ helpers


def get_path(data: dict[str, Any], path: str | None) -> Any:
    if not path:
        return None
    node: Any = data
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _blank(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def join_ru(items: list[str], sep: str = ", ") -> str:
    return sep.join(i for i in items if i)


def format_date_ru(value: date | str | None) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        value = date.fromisoformat(value[:10])
    return value.strftime("%d.%m.%Y")


def format_datetime_ru(value: datetime | None) -> str:
    return value.strftime("%d.%m.%Y %H:%M") if value else ""


def _yesno(value: Any) -> str | None:
    if value is True:
        return "Да"
    if value is False:
        return "Нет"
    return None


def _clean(text: str | None) -> str | None:
    if text is None:
        return None
    text = " ".join(text.split())
    return text or None


# ------------------------------------------------------------------ rendering


def render_template(spec: TemplateSpec, inp: RenderInput) -> list[RenderedField]:
    cached = inp._cache.get(spec.id)
    if cached is not None:
        return cached
    inp._cache[spec.id] = []  # cycle guard: a copy of itself resolves to nothing
    rendered = [_render_field(f, inp) for f in spec.fields]
    inp._cache[spec.id] = rendered
    return rendered


def _base(spec: FieldSpec, **kw: Any) -> RenderedField:
    kw.setdefault("hint", spec.hint)
    return RenderedField(
        key=spec.key,
        section=spec.section,
        label=spec.label,
        emr_type=spec.emr_type.value,
        critical=spec.critical,
        **kw,
    )


def _render_field(spec: FieldSpec, inp: RenderInput) -> RenderedField:
    if spec.only_if == "columbia_followup" and not inp.facts.get("columbia_followup_visible"):
        return _base(spec, display="skip", hint="Не задаётся: ответы на вопросы 1 и 2 — «Нет»")
    if spec.emr_type is EmrType.CALCULATE:
        return _base(spec, display="calculate", hint=CALCULATE_LABEL)
    if spec.source == "skip":
        return _base(spec, display="skip", hint=spec.hint or "Оставить пустым")
    if spec.emr_type is EmrType.CHECKCOMBO:
        return _base(
            spec, display="manual", hint=spec.hint or "Варианты не заданы: заполните в EMR"
        )

    result = _resolve(spec, inp)
    if spec.override_path:
        override = _clean(get_path(inp.data, spec.override_path))
        if override:
            result.value, result.display = override, "value"
    if spec.emr_prefill:
        _apply_prefill(spec, result)
    if result.display == "value" and (spec.critical or spec.required):
        result.missing = _is_empty(result)
    return result


def _is_empty(result: RenderedField) -> bool:
    return _blank(result.value) and _blank(result.items) and _blank(result.icd)


def _apply_prefill(spec: FieldSpec, result: RenderedField) -> None:
    if result.display == "keep_emr":
        return
    if spec.keep_if_empty and _is_empty(result):
        result.display, result.hint = "keep_emr", KEEP_EMR_LABEL
    elif not _is_empty(result):
        result.hint = PREFILL_HINT


def _resolve(spec: FieldSpec, inp: RenderInput) -> RenderedField:
    source = spec.source
    if source.startswith("copy:"):
        return _copy(spec, inp, source.removeprefix("copy:"))
    if source == "generated":
        return _generated(spec, inp)
    if source == "staff":
        return _base(spec, display="value", value=inp.staff.get(spec.staff or ""))
    if source == "schedule":
        return _base(spec, display="value", value=format_datetime_ru(inp.schedule) or None)
    if source == "board":
        return _base(spec, display="value", items=list(inp.studies))
    if source == "note":
        return _base(
            spec,
            display="value",
            value=_clean(inp.notes.get(spec.path or "")),
            locked=not inp.notes_approved,
        )
    if source == "procedure":
        key = (spec.path or "").removeprefix("surgery_texts.")
        return _base(spec, display="value", value=_clean(inp.procedure_texts.get(key)))
    if source == "case":
        return _base(spec, display="value", value=_clean(inp.case_values.get(spec.path or "")))
    return _from_form(spec, inp)


def _copy(spec: FieldSpec, inp: RenderInput, ref: str) -> RenderedField:
    template_id, key = ref.split(".", 1)
    source_fields = render_template(inp.templates[template_id], inp)
    origin = next((f for f in source_fields if f.key == key), None)
    result = _base(spec, display="value")
    if origin is not None and origin.display == "value":
        result.value, result.items, result.icd = origin.value, origin.items, origin.icd
    return result


def _generated(spec: FieldSpec, inp: RenderInput) -> RenderedField:
    template = inp.env.get_template(f"{spec.generator}.j2")
    text = template.render(facts=inp.facts, data=inp.data, sep=inp.separator)
    return _base(spec, display="value", value=_clean(text))


def _from_form(spec: FieldSpec, inp: RenderInput) -> RenderedField:
    raw = get_path(inp.data, spec.path)
    if _blank(raw) and spec.fallback_path:
        raw = get_path(inp.data, spec.fallback_path)
    fmt = spec.format or _default_format(spec.emr_type)
    result = _base(spec, display="value")

    if fmt == "system":
        return _system(spec, inp, raw, result)
    if fmt == "yesno":
        result.value = _yesno(raw)
    elif fmt == "number":
        result.value = format_number(raw, inp.separator) or None
    elif fmt == "list_text":
        result.value = join_ru([str(i) for i in raw]) if isinstance(raw, list) and raw else None
    elif fmt == "items":
        result.items = _items(raw)
    elif fmt == "icd":
        result.icd = _icd(raw)
    elif fmt == "fact":
        result.value = _clean(_fact(inp.facts, spec.path))
    else:
        result.value = _clean(str(raw)) if not _blank(raw) else None

    if result.value is None and result.items is None and result.icd is None and spec.default_ru:
        result.value = spec.default_ru
    return result


def _default_format(emr_type: EmrType) -> str:
    return {
        EmrType.NUMBER: "number",
        EmrType.ICD10: "icd",
        EmrType.SERVICE: "items",
        EmrType.MEDICATION: "items",
    }.get(emr_type, "text")


def _fact(facts: dict[str, Any], path: str | None) -> str | None:
    value = get_path(facts, path)
    return None if value is None else str(value)


def _items(raw: Any) -> list[str]:
    out: list[str] = []
    for entry in raw or []:
        if isinstance(entry, dict):
            name = str(entry.get("name", "")).strip()
            note = str(entry.get("note", "")).strip()
            if name:
                out.append(f"{name} — {note}" if note else name)
        elif str(entry).strip():
            out.append(str(entry).strip())
    return out


def _icd(raw: Any) -> list[dict[str, str]]:
    entries = raw if isinstance(raw, list) else [raw]
    out: list[dict[str, str]] = []
    for entry in entries:
        if isinstance(entry, dict) and (entry.get("code") or entry.get("text")):
            out.append({"code": str(entry.get("code", "")), "text": str(entry.get("text", ""))})
    return out


def _system(spec: FieldSpec, inp: RenderInput, raw: Any, result: RenderedField) -> RenderedField:
    finding = raw if isinstance(raw, dict) else {}
    system_key = (spec.path or "").rsplit(".", 1)[-1]
    if finding.get("normal") is True:
        if spec.emr_prefill:
            result.display, result.hint = "keep_emr", KEEP_EMR_LABEL
        else:
            result.value = _clean(inp.system_defaults.get(system_key))
    elif finding.get("normal") is False:
        result.value = _clean(finding.get("text"))
    return result
