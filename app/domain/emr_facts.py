"""Derives sentence-ready facts from the intake form. Only recorded values are used."""

from dataclasses import dataclass, field
from typing import Any

from app.domain.columbia import ColumbiaLogic, visible_questions
from app.domain.emr import format_date_ru
from app.domain.intake import IntakeData
from app.domain.numbers import format_number
from app.domain.nutrition import NutritionResult

SIDE_ADVERB = {"left": "слева", "right": "справа", "both": "с обеих сторон"}


@dataclass(frozen=True)
class FactsInput:
    data: IntakeData
    age: int | None
    side: str | None
    operation_name: str
    segments: dict[str, tuple[str, str]]  # key -> (nominative, genitive)
    nutrition: NutritionResult
    columbia: ColumbiaLogic
    bmi_value: float | None
    caprini_total: int | None
    caprini_category: str | None
    studies: list[str] = field(default_factory=list)
    separator: str = ","
    # (key, label) of the location questions for the complaint segment, in display order
    detail_questions: list[tuple[str, str]] = field(default_factory=list)


def _yes_no(value: bool | None) -> str:
    return {True: "Да", False: "Нет"}.get(value, "") if value is not None else ""


def build_facts(fi: FactsInput) -> dict[str, Any]:
    d = fi.data
    side_adv = SIDE_ADVERB.get(fi.side or "", "")
    segment = fi.segments.get(d.complaints.segment or "")
    local_segment = fi.segments.get(d.local_status.segment or d.complaints.segment or "")

    complaint_items: list[str] = []
    if d.complaints.pain_vas:
        where = f" в области {segment[1]}" if segment else ""
        side = f" {side_adv}" if segment and side_adv else ""
        complaint_items.append(f"боль{where}{side} (ВАШ {d.complaints.pain_vas} из 10)")
    if d.complaints.limitation:
        complaint_items.append("ограничение движений")
    if d.complaints.deformity:
        complaint_items.append("деформацию")
    if d.complaints.swelling:
        complaint_items.append("отёк")

    complaint_details: list[str] = []
    for key, label in fi.detail_questions:
        answer = d.complaints.details.get(key)
        values = [answer] if isinstance(answer, str) else list(answer or [])
        values = [v for v in values if v]
        if values:
            complaint_details.append(f"{label}: {', '.join(values)}")

    rom_items = [f"{r.movement} {r.degrees}°" for r in d.local_status.rom]
    stability_items = [f"{s.test} — {s.result}" for s in d.local_status.stability]
    nv = d.local_status.neurovascular
    neuro_items = [
        part
        for part in (
            f"пульсация {nv.pulsation}" if nv.pulsation else "",
            f"чувствительность {nv.sensation}" if nv.sensation else "",
            f"движения {nv.motor}" if nv.motor else "",
        )
        if part
    ]
    positive_tests = [s.test for s in d.local_status.stability if s.result == "положительный"]
    local_key = "; ".join(
        [
            *d.local_status.inspection,
            *rom_items,
            *[f"тест {t} положительный" for t in positive_tests],
        ]
    )

    history_core = "; ".join(
        part
        for part in (
            f"начало {format_date_ru(d.history.onset_date)}" if d.history.onset_date else "",
            d.history.mechanism,
            d.history.duration,
            d.history.prior_treatment,
        )
        if part
    )
    dx = d.diagnosis.main
    dx_main = f"{dx.text} ({dx.code})" if dx.text and dx.code else (dx.text or dx.code)
    nutrition = fi.nutrition
    answers = visible_questions(
        fi.columbia,
        {i: getattr(d.columbia, f"q{i}") for i in range(1, 8)},
    )
    return {
        "age": fi.age,
        "side_adv": side_adv,
        "operation_full": f"{fi.operation_name} {side_adv}".strip(),
        "operation": fi.operation_name,
        "complaint_items": complaint_items,
        "complaint_details": complaint_details,
        "history_core": history_core,
        "onset_date_ru": format_date_ru(d.history.onset_date),
        "past_items": [f"{i.text} ({i.year} г.)" if i.year else i.text for i in d.past.items],
        "epi_items": list(d.past.epidemiological),
        "med_items": [
            " ".join(p for p in (m.name, m.dose, m.frequency) if p) for m in d.medications
        ],
        "anticoagulants": [m.name for m in d.medications if m.is_anticoagulant],
        "local": {
            "segment": (local_segment[0][:1].upper() + local_segment[0][1:])
            if local_segment
            else "",
            "side_adv": side_adv,
            "inspection": list(d.local_status.inspection),
            "rom": rom_items,
            "stability": stability_items,
            "neuro": neuro_items,
        },
        "local_key": local_key,
        "dx_main": dx_main,
        "comorbid": [e.text or e.code for e in d.diagnosis.comorbid],
        "studies": list(fi.studies),
        # Cited in the conclusion: completed board items plus the recorded imaging result.
        "studies_cited": [*fi.studies, *([d.preop.imaging] if d.preop.imaging else [])],
        "bmi_text": format_number(round(fi.bmi_value, 1), fi.separator) if fi.bmi_value else "",
        "caprini": {"total": fi.caprini_total, "category": fi.caprini_category},
        "plan_meds": {
            "antibiotic": [m for m in d.plan.medications if m.kind == "антибиотикопрофилактика"],
            "vte": [m for m in d.plan.medications if m.kind == "профилактика ВТЭ"],
        },
        "nutrition": {
            "bmi_low": _yes_no(nutrition.bmi_low),
            "total": str(nutrition.total) if nutrition.complete else "",
        },
        "columbia_followup_visible": any(n in answers for n in (3, 4, 5, 6)),
    }
