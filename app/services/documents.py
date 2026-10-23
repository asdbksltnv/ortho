import uuid
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ApiError, not_found
from app.auth import CurrentUser
from app.domain.emr import (
    RenderedField,
    RenderInput,
    TemplateSpec,
    render_template,
)
from app.domain.emr_facts import FactsInput, build_facts
from app.domain.enums import AuditAction, ItemStatus, Role
from app.domain.intake import IntakeData
from app.models.base import utcnow
from app.models.case import AiNoteDraft, Case, GeneratedDocument, PostOpEntry
from app.models.user import User
from app.services import audit
from app.services.clock import local_today
from app.services.config_loader import TEMPLATES_DIR, AppConfig
from app.services.intake import (
    columbia_logic,
    compute_caprini_for,
    compute_nutrition_for,
    latest_vitals,
    load_intake,
)
from app.settings import get_settings

_PASSING = {ItemStatus.DONE.value, ItemStatus.NOT_APPLICABLE.value}


@lru_cache
def jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=False,  # noqa: S701 - plain-text clinical documents, never HTML
        undefined=StrictUndefined,
        trim_blocks=False,
        keep_trailing_newline=False,
    )


@dataclass
class Rendering:
    spec: TemplateSpec
    fields: list[RenderedField]
    problems: list[dict[str, str]]  # why generation is blocked (empty = can generate)


def _head_name(session: Session) -> str | None:
    head = session.scalars(
        select(User)
        .where(User.role == Role.HEAD_OF_DEPARTMENT.value, User.is_active.is_(True))
        .order_by(User.full_name)
    ).first()
    return head.full_name if head else None


def _studies(case: Case, config: AppConfig) -> list[str]:
    """Completed investigations only: planned or pending ones are never cited."""
    done = {i.key for i in case.checklist_items if i.status == ItemStatus.DONE.value}
    template = config.procedures.get(case.procedure_key)
    studies: list[str] = []
    if "labs_core" in done:
        studies += [lab.name_ru for lab in config.labs.labs if lab.group == "core"]
    if "labs_optional" in done and template is not None:
        studies += [lab.name_ru for lab in config.labs.labs if lab.code in template.optional_labs]
    return studies


def note_draft(session: Session, entry: PostOpEntry) -> AiNoteDraft | None:
    return session.scalars(
        select(AiNoteDraft).where(AiNoteDraft.postop_entry_id == entry.id)
    ).one_or_none()


def build_render_input(
    session: Session,
    case: Case,
    config: AppConfig,
    author: CurrentUser,
    entry: PostOpEntry | None = None,
) -> tuple[RenderInput, IntakeData]:
    data, _row = load_intake(session, case, config)
    settings = get_settings()
    today = local_today()
    template = config.procedures.get(case.procedure_key)
    segments = {s.key: (s.name_ru, s.gen_ru) for s in config.defaults.segments}
    vitals = latest_vitals(data)
    caprini = compute_caprini_for(data, case.patient.birth_date, config, today)
    nutrition = compute_nutrition_for(data, config)
    from app.domain.caprini import age_on
    from app.domain.numbers import bmi

    facts = build_facts(
        FactsInput(
            data=data,
            age=age_on(case.patient.birth_date, today),
            side=case.side,
            operation_name=template.operation_name_ru if template else "",
            segments=segments,
            nutrition=nutrition,
            columbia=columbia_logic(config),
            bmi_value=bmi(vitals.weight, vitals.height),
            caprini_total=caprini.total,
            caprini_category=caprini.category_label_ru,
            studies=_studies(case, config),
            separator=settings.decimal_separator,
        )
    )
    payload = data.model_dump(mode="json")
    payload["latest_vitals"] = vitals.model_dump(mode="json")

    schedule: datetime | None = None
    if case.planned_surgery_date and case.planned_surgery_time:
        schedule = datetime.combine(case.planned_surgery_date, case.planned_surgery_time)
    notes: dict[str, str | None] = {}
    approved = False
    if entry is not None:
        # T6: the examination time is the entry time, vitals come from the post-op form.
        payload["postop"] = entry.data
        schedule = entry.entered_at.astimezone(ZoneInfo(settings.tz_display)).replace(tzinfo=None)
        draft = note_draft(session, entry)
        if draft is not None:
            notes = dict(draft.output)
            approved = draft.approved_at is not None

    texts = template.surgery_texts.model_dump() if template else {}
    inp = RenderInput(
        env=jinja_env(),
        templates=config.emr_templates,
        data=payload,
        facts=facts,
        separator=settings.decimal_separator,
        staff={
            "treating_doctor": case.treating_doctor.full_name,
            "head": _head_name(session),
            "author": author.full_name,
        },
        schedule=schedule,
        procedure_texts=texts,
        case_values={"anaesthesia_type": case.anaesthesia_type},
        studies=facts["studies"],
        system_defaults={k: v.normal_ru for k, v in config.defaults.systems.items()},
        notes=notes,
        notes_approved=approved,
    )
    return inp, data


def render_document(case: Case, spec: TemplateSpec, inp: RenderInput) -> Rendering:
    fields = render_template(spec, inp)
    problems: list[dict[str, str]] = []
    if spec.status != "ready":
        problems.append({"code": "awaiting_template", "message": "Шаблон ожидается"})
        return Rendering(spec, fields, problems)
    status = {i.key: i.status for i in case.checklist_items}
    for key in spec.gating_items:
        if status.get(key) not in _PASSING:
            problems.append(
                {
                    "code": "gating",
                    "key": key,
                    "message": "Документ можно создать после выполнения пункта подготовки",
                }
            )
    for f in fields:
        if f.missing:
            problems.append(
                {"code": "missing", "key": f.key, "message": f"Заполните поле: {f.label}"}
            )
    return Rendering(spec, fields, problems)


def spec_or_404(config: AppConfig, template_id: str) -> TemplateSpec:
    spec = config.emr_templates.get(template_id)
    if spec is None:
        raise not_found("Шаблон")
    return spec


def _stored(
    session: Session,
    case_id: uuid.UUID,
    template_id: str,
    *,
    lock: bool = False,
    entry_id: uuid.UUID | None = None,
) -> GeneratedDocument | None:
    stmt = select(GeneratedDocument).where(
        GeneratedDocument.case_id == case_id, GeneratedDocument.template_id == template_id
    )
    if entry_id is None:
        stmt = stmt.where(GeneratedDocument.postop_entry_id.is_(None))
    else:
        stmt = stmt.where(GeneratedDocument.postop_entry_id == entry_id)
    if lock:
        # Concurrent "copied" ticks rewrite the whole JSON list; serialise them on Postgres.
        stmt = stmt.with_for_update()
    return session.scalars(stmt).one_or_none()


def _stored_comparable(item: dict[str, Any]) -> tuple[Any, ...]:
    icd = tuple((e["code"], e["text"]) for e in item["icd"]) if item.get("icd") else None
    items = tuple(item["items"]) if item.get("items") else None
    return (item["display"], item.get("value"), items, icd)


def changed_keys(stored: list[dict[str, Any]], fresh: list[RenderedField]) -> list[str]:
    old = {f["key"]: _stored_comparable(f) for f in stored}
    new = {f.key: f.comparable() for f in fresh}
    return [k for k in new if old.get(k) != new[k]] + [k for k in old if k not in new]


def generate(
    session: Session,
    case: Case,
    spec: TemplateSpec,
    inp: RenderInput,
    user: CurrentUser,
    ip: str | None,
    entry: PostOpEntry | None = None,
) -> GeneratedDocument:
    rendering = render_document(case, spec, inp)
    if rendering.problems:
        raise ApiError(
            422,
            "generation_blocked",
            "Документ нельзя создать: не хватает данных",
            {"problems": rendering.problems},
        )
    existing = _stored(session, case.id, spec.id, entry_id=entry.id if entry else None)
    previous = {f["key"]: f for f in existing.fields} if existing else {}
    new_fields: list[dict[str, Any]] = []
    for f in rendering.fields:
        row = f.to_dict()
        old = previous.get(f.key)
        # Keep the "copied" tick only for fields whose pasted value did not change.
        row["copied"] = bool(
            old and old.get("copied") and _stored_comparable(old) == f.comparable()
        )
        new_fields.append(row)
    if existing is None:
        existing = GeneratedDocument(
            case_id=case.id,
            postop_entry_id=entry.id if entry else None,
            template_id=spec.id,
            template_version=spec.version,
            fields=new_fields,
        )
        session.add(existing)
    else:
        existing.fields = new_fields
        existing.template_version = spec.version
    existing.generated_at = utcnow()
    existing.is_outdated = False
    audit.record(
        session,
        user_id=user.id,
        action=AuditAction.CREATE,
        entity="generated_document",
        entity_id=case.id,
        diff={"template_id": spec.id, "template_version": spec.version},
        ip=ip,
    )
    session.flush()
    return existing


def _with_locks(
    fields: list[dict[str, Any]], spec: TemplateSpec, inp: RenderInput
) -> list[dict[str, Any]]:
    """Note-sourced fields stay locked (no copying) until the doctor presses «Проверено»."""
    note_keys = {f.key for f in spec.fields if f.source == "note"}
    return [{**f, "locked": f["key"] in note_keys and not inp.notes_approved} for f in fields]


def document_state(
    session: Session,
    case: Case,
    spec: TemplateSpec,
    inp: RenderInput,
    entry: PostOpEntry | None = None,
) -> dict[str, Any]:
    """Stored document + whether it is outdated against the current intake data."""
    rendering = render_document(case, spec, inp)
    stored = _stored(session, case.id, spec.id, entry_id=entry.id if entry else None)
    state: dict[str, Any] = {
        "template_id": spec.id,
        "title_ru": spec.title_ru,
        "status": "awaiting_template" if spec.status != "ready" else "not_generated",
        "can_generate": not rendering.problems,
        "problems": rendering.problems,
        "generated_at": None,
        "is_outdated": False,
        "changed_keys": [],
        "fields": [],
    }
    if stored is None:
        return state
    keys = changed_keys(stored.fields, rendering.fields)
    outdated = bool(keys) or stored.template_version != spec.version
    if outdated != stored.is_outdated:
        stored.is_outdated = outdated
    state.update(
        status="outdated" if outdated else "generated",
        generated_at=stored.generated_at,
        is_outdated=outdated,
        changed_keys=keys,
        fields=_with_locks(stored.fields, spec, inp),
    )
    return state


def set_copied(
    session: Session,
    case: Case,
    spec: TemplateSpec,
    key: str,
    copied: bool,
    user: CurrentUser,
    ip: str | None,
    entry: PostOpEntry | None = None,
    notes_approved: bool = True,
) -> GeneratedDocument:
    stored = _stored(session, case.id, spec.id, lock=True, entry_id=entry.id if entry else None)
    if stored is None:
        raise not_found("Документ")
    fields = [dict(f) for f in stored.fields]
    target = next((f for f in fields if f["key"] == key), None)
    if target is None:
        raise not_found("Поле")
    is_note = any(f.key == key and f.source == "note" for f in spec.fields)
    if is_note and not notes_approved:
        raise ApiError(409, "note_not_approved", "Сначала проверьте текст и нажмите «Проверено»")
    target["copied"] = copied
    stored.fields = fields  # reassign so the JSON column change is detected
    if copied:
        audit.record(
            session,
            user_id=user.id,
            action=AuditAction.COPY,
            entity="generated_document",
            entity_id=case.id,
            diff={"template_id": spec.id, "key": key},
            ip=ip,
        )
    session.flush()
    return stored


def all_text(fields: list[dict[str, Any]]) -> str:
    """Fallback «Скопировать всё одним текстом»: labelled plain text, in EMR order."""
    lines: list[str] = []
    for f in fields:
        if f.get("locked"):
            continue  # an unapproved draft is never put on the clipboard
        display = f["display"]
        if display == "value":
            if f.get("value"):
                body = f["value"]
            elif f.get("items"):
                body = "; ".join(f["items"])
            elif f.get("icd"):
                body = "; ".join(f"{e['code']} {e['text']}".strip() for e in f["icd"])
            else:
                continue
        elif display == "keep_emr":
            body = "(оставить текст EMR)"
        else:
            continue
        lines.append(f"{f['label']}: {body}")
    return "\n".join(lines)
