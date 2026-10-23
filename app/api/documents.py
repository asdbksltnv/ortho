import uuid
from typing import Any

from fastapi import APIRouter, Request

from app.api.deps import CaseReader, ConfigDep, SessionDep, ip_of
from app.api.errors import forbidden
from app.domain.enums import AuditAction
from app.domain.permissions import can_edit_case
from app.schemas.api import CopiedIn, DocumentOut, DocumentSummary
from app.services import audit
from app.services import cases as case_service
from app.services import documents as docs

router = APIRouter(tags=["documents"])


def _summary(state: dict[str, Any]) -> dict[str, Any]:
    return {k: state[k] for k in DocumentSummary.model_fields}


def _full(state: dict[str, Any]) -> DocumentOut:
    return DocumentOut(**{**state, "all_text": docs.all_text(state["fields"])})


def _require_editor(case, user) -> None:  # type: ignore[no-untyped-def]
    if not can_edit_case(user.role, is_treating_doctor=case.treating_doctor_id == user.id):
        raise forbidden()


@router.get("/cases/{case_id}/documents", response_model=list[DocumentSummary])
def list_documents(
    case_id: uuid.UUID, user: CaseReader, session: SessionDep, config: ConfigDep
) -> list[dict[str, Any]]:
    case = case_service.load_case(session, case_id)
    inp, _ = docs.build_render_input(session, case, config, user)
    out = [
        _summary(docs.document_state(session, case, spec, inp))
        for spec in config.emr_templates.values()
    ]
    session.commit()  # persists refreshed is_outdated flags
    return out


@router.get("/cases/{case_id}/documents/{template_id}", response_model=DocumentOut)
def get_document(
    case_id: uuid.UUID, template_id: str, user: CaseReader, session: SessionDep, config: ConfigDep
) -> DocumentOut:
    spec = docs.spec_or_404(config, template_id)
    case = case_service.load_case(session, case_id)
    inp, _ = docs.build_render_input(session, case, config, user)
    state = docs.document_state(session, case, spec, inp)
    session.commit()
    return _full(state)


@router.post("/cases/{case_id}/documents/{template_id}/generate", response_model=DocumentOut)
def generate_document(
    case_id: uuid.UUID,
    template_id: str,
    request: Request,
    user: CaseReader,
    session: SessionDep,
    config: ConfigDep,
) -> DocumentOut:
    spec = docs.spec_or_404(config, template_id)
    case = case_service.load_case(session, case_id)
    _require_editor(case, user)
    inp, _ = docs.build_render_input(session, case, config, user)
    docs.generate(session, case, spec, inp, user, ip_of(request))
    session.commit()
    return _full(docs.document_state(session, case, spec, inp))


@router.post(
    "/cases/{case_id}/documents/{template_id}/fields/{key}/copied", response_model=DocumentOut
)
def mark_copied(
    case_id: uuid.UUID,
    template_id: str,
    key: str,
    body: CopiedIn,
    request: Request,
    user: CaseReader,
    session: SessionDep,
    config: ConfigDep,
) -> DocumentOut:
    spec = docs.spec_or_404(config, template_id)
    case = case_service.load_case(session, case_id)
    _require_editor(case, user)
    docs.set_copied(session, case, spec, key, body.copied, user, ip_of(request))
    session.commit()
    inp, _ = docs.build_render_input(session, case, config, user)
    return _full(docs.document_state(session, case, spec, inp))


@router.post("/cases/{case_id}/documents/{template_id}/copy-all", response_model=DocumentOut)
def copy_all(
    case_id: uuid.UUID,
    template_id: str,
    request: Request,
    user: CaseReader,
    session: SessionDep,
    config: ConfigDep,
) -> DocumentOut:
    spec = docs.spec_or_404(config, template_id)
    case = case_service.load_case(session, case_id)
    _require_editor(case, user)
    inp, _ = docs.build_render_input(session, case, config, user)
    state = docs.document_state(session, case, spec, inp)
    audit.record(
        session,
        user_id=user.id,
        action=AuditAction.COPY,
        entity="generated_document",
        entity_id=case.id,
        diff={"template_id": spec.id, "key": "*"},
        ip=ip_of(request),
    )
    session.commit()
    return _full(state)
