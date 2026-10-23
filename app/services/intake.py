import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.auth import CurrentUser
from app.domain.caprini import (
    AutoRule,
    CapriniResult,
    Category,
    Factor,
    age_on,
    compute_caprini,
)
from app.domain.columbia import ColumbiaLogic, UrgentRule, urgent_consult_alert, visible_questions
from app.domain.enums import AuditAction
from app.domain.intake import SCHEMA_VERSION, IntakeData, Vitals
from app.domain.numbers import bmi
from app.domain.nutrition import NutritionResult, compute_nutrition
from app.models.case import Case, IdempotencyKey, IntakeForm
from app.services import audit
from app.services.cases import refresh_first_ready
from app.services.clock import local_today
from app.services.config_loader import AppConfig


def columbia_logic(config: AppConfig) -> ColumbiaLogic:
    c = config.columbia
    return ColumbiaLogic(
        always_ask=tuple(c.always_ask),
        follow_up=tuple(c.follow_up),
        follow_up_trigger=tuple(c.follow_up_trigger),
        urgent=UrgentRule(
            all_yes=tuple(c.urgent_consult_rule.all_yes),
            any_yes=tuple(c.urgent_consult_rule.any_yes),
        ),
    )


def caprini_factors(config: AppConfig) -> list[Factor]:
    return [
        Factor(
            key=f.key,
            points=f.points,
            label_ru=f.label_ru,
            auto=AutoRule(f.auto.type, f.auto.min, f.auto.max, f.auto.value) if f.auto else None,
        )
        for f in config.caprini.factors
    ]


def caprini_categories(config: AppConfig) -> list[Category]:
    return [Category(c.key, c.label_ru, c.min, c.max) for c in config.caprini.risk_categories]


def latest_vitals(data: IntakeData) -> Vitals:
    """Admission vitals overridden by the fresh pre-operative measurement where present."""
    merged = data.vitals.model_dump()
    merged.update({k: v for k, v in data.preop.vitals.model_dump().items() if v is not None})
    return Vitals(**merged)


def compute_caprini_for(
    data: IntakeData, birth_date: date, config: AppConfig, today: date
) -> CapriniResult:
    vitals = latest_vitals(data)
    return compute_caprini(
        caprini_factors(config),
        caprini_categories(config),
        manual=data.caprini.factors,
        age=age_on(birth_date, today),
        bmi_value=bmi(vitals.weight, vitals.height),
    )


def compute_nutrition_for(data: IntakeData, config: AppConfig) -> NutritionResult:
    vitals = latest_vitals(data)
    return compute_nutrition(
        bmi_value=bmi(vitals.weight, vitals.height),
        bmi_threshold=config.nutrition.bmi_threshold,
        weight_loss=data.nutrition.weight_loss,
        reduced_intake=data.nutrition.reduced_intake,
        stress_factor=data.nutrition.stress_factor,
    )


def derived(data: IntakeData, birth_date: date, config: AppConfig, today: date) -> dict[str, Any]:
    caprini = compute_caprini_for(data, birth_date, config, today)
    nutrition = compute_nutrition_for(data, config)
    logic = columbia_logic(config)
    answers = {i: getattr(data.columbia, f"q{i}") for i in range(1, 8)}
    vitals = latest_vitals(data)
    bmi_value = bmi(vitals.weight, vitals.height)
    return {
        "age": age_on(birth_date, today),
        "bmi": round(bmi_value, 1) if bmi_value else None,
        "caprini": {
            "total": caprini.total,
            "category_key": caprini.category_key,
            "category_label_ru": caprini.category_label_ru,
            "selected": list(caprini.selected),
            "automatic": list(caprini.automatic),
        },
        "nutrition": {
            "bmi_low": nutrition.bmi_low,
            "total": nutrition.total,
            "complete": nutrition.complete,
        },
        "columbia": {
            "visible": visible_questions(logic, answers),
            "urgent_alert": urgent_consult_alert(logic, answers),
            "rule_text_ru": config.columbia.urgent_consult_rule.rule_text_ru,
        },
    }


def default_intake(case: Case, config: AppConfig) -> IntakeData:
    """Pre-fill from the procedure template. Contains only values the config supplies."""
    template = config.procedures.get(case.procedure_key)
    raw: dict[str, Any] = {}
    if template is not None:
        raw["complaints"] = dict(template.defaults.complaints)
        raw["local_status"] = dict(template.defaults.local_status)
        plan = dict(template.defaults.plan)
        core = [lab.name_ru for lab in config.labs.labs if lab.group == "core"]
        optional = [
            lab.name_ru for lab in config.labs.labs if lab.code in set(template.optional_labs)
        ]
        plan.setdefault("labs", core + optional)
        plan.setdefault("instrumental", list(template.instrumental))
        if config.diets.default:
            plan.setdefault("diet", config.diets.default)
        raw["plan"] = plan
        raw["caprini"] = {"factors": list(template.caprini_defaults)}
    return IntakeData.model_validate(raw)


def load_intake(
    session: Session, case: Case, config: AppConfig
) -> tuple[IntakeData, IntakeForm | None]:
    row = session.scalars(select(IntakeForm).where(IntakeForm.case_id == case.id)).one_or_none()
    if row is None:
        return default_intake(case, config), None
    return IntakeData.model_validate(row.data), row


def save_intake(
    session: Session,
    case: Case,
    data: IntakeData,
    *,
    user: CurrentUser,
    request_id: uuid.UUID,
    base_updated_at: datetime | None,
    completed: bool,
    config: AppConfig,
    ip: str | None,
) -> IntakeForm | None:
    """Idempotent, conflict-checked save. Returns None when the request id was already applied."""
    if session.get(IdempotencyKey, request_id) is not None:
        return None
    row = session.scalars(select(IntakeForm).where(IntakeForm.case_id == case.id)).one_or_none()
    stale = (
        row is not None
        and base_updated_at is not None
        and row.updated_at != base_updated_at
        and row.updated_by != user.id
    )
    if stale and row is not None:
        raise ApiError(
            409,
            "conflict",
            "Форма уже изменена другим пользователем",
            {"current_updated_at": row.updated_at.isoformat()},
        )
    payload = data.model_dump(mode="json")
    if row is None:
        row = IntakeForm(case_id=case.id, schema_version=SCHEMA_VERSION, data=payload)
        session.add(row)
    else:
        row.data = payload
        row.schema_version = SCHEMA_VERSION
    if completed and row.completed_at is None:
        row.completed_at = datetime.now(UTC)
    session.add(IdempotencyKey(key=request_id, case_id=case.id))

    # The medication list is the source of the anticoagulant flag, which drives the `anticoag` item.
    if case.takes_anticoagulant != data.takes_anticoagulant:
        case.takes_anticoagulant = data.takes_anticoagulant
        refresh_first_ready(case, config)
    audit.record(
        session,
        user_id=user.id,
        action=AuditAction.UPDATE,
        entity="intake_form",
        entity_id=case.id,
        diff={"completed": completed, "schema_version": SCHEMA_VERSION},
        ip=ip,
    )
    session.flush()
    session.refresh(row)
    return row


def today() -> date:
    return local_today()
