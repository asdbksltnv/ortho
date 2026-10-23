import contextlib
import uuid
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select

from app.api.deps import ConfigDep, SessionDep, UserDep, ip_of
from app.api.errors import ApiError, forbidden, not_found
from app.domain.enums import AuditAction, Role
from app.domain.permissions import can_edit_case
from app.domain.postop import PostOpData
from app.models.case import AiNoteDraft, PostOpEntry
from app.models.user import User
from app.schemas.api import (
    DocumentOut,
    NoteApproveIn,
    NoteOut,
    PostOpEntryOut,
    PostOpIn,
    PostOpListOut,
)
from app.services import audit, storage
from app.services import cases as case_service
from app.services import documents as docs
from app.services import postop as postop_service
from app.services.clock import local_today

router = APIRouter(tags=["postop"])
T6 = "t6_progress_note"


def _no_admin(user: Any) -> None:
    if user.role is Role.ADMIN:
        raise forbidden()


def _note(session: Any, entry: PostOpEntry) -> NoteOut | None:
    draft = session.scalars(
        select(AiNoteDraft).where(AiNoteDraft.postop_entry_id == entry.id)
    ).one_or_none()
    if draft is None:
        return None
    approver = session.get(User, draft.approved_by) if draft.approved_by else None
    return NoteOut(
        generator=draft.generator,
        general_condition=draft.output["general_condition"],
        local_status=draft.output["local_status"],
        approved=draft.approved_at is not None,
        approved_at=draft.approved_at,
        approved_by_name=approver.full_name if approver else None,
    )


def _entry_out(session: Any, entry: PostOpEntry) -> PostOpEntryOut:
    data = PostOpData.model_validate(entry.data)
    return PostOpEntryOut(
        id=entry.id,
        case_id=entry.case_id,
        entered_at=entry.entered_at,
        entry_date=entry.entry_date,
        post_op_day=entry.post_op_day,
        data=data,
        alerts=list(entry.alerts or []),
        note=_note(session, entry),
        has_photo=data.photo_key is not None,
    )


@router.get("/cases/{case_id}/postop", response_model=PostOpListOut)
def list_entries(case_id: uuid.UUID, user: UserDep, session: SessionDep) -> PostOpListOut:
    _no_admin(user)
    case = case_service.load_case(session, case_id)
    entries = postop_service.entries_for(session, case_id)
    today = local_today()
    todays = next((e for e in entries if e.entry_date == today), None)
    return PostOpListOut(
        entries=[_entry_out(session, e) for e in reversed(entries)],
        trends=postop_service.trends(entries),
        can_record=case.status in postop_service.RECORDING_STATUSES
        and case.operated_on is not None,
        can_edit=can_edit_case(user.role, is_treating_doctor=case.treating_doctor_id == user.id),
        photo_enabled=storage.get_storage().__class__ is not storage.DisabledStorage,
        today_entry_id=todays.id if todays else None,
    )


@router.post("/cases/{case_id}/postop", response_model=PostOpEntryOut, status_code=201)
def create_entry(
    case_id: uuid.UUID,
    body: PostOpIn,
    request: Request,
    user: UserDep,
    session: SessionDep,
    config: ConfigDep,
) -> PostOpEntryOut:
    _no_admin(user)
    case = case_service.load_case(session, case_id)
    entry = postop_service.create_entry(session, case, body.data, user, config, ip_of(request))
    session.commit()
    return _entry_out(session, entry)


@router.put("/cases/{case_id}/postop/{entry_id}", response_model=PostOpEntryOut)
def update_entry(
    case_id: uuid.UUID,
    entry_id: uuid.UUID,
    body: PostOpIn,
    request: Request,
    user: UserDep,
    session: SessionDep,
    config: ConfigDep,
) -> PostOpEntryOut:
    _no_admin(user)
    case = case_service.load_case(session, case_id)
    entry = postop_service.load_entry(session, case_id, entry_id)
    postop_service.update_entry(session, case, entry, body.data, user, config, ip_of(request))
    session.commit()
    return _entry_out(session, entry)


@router.post("/cases/{case_id}/postop/{entry_id}/note/regenerate", response_model=PostOpEntryOut)
def regenerate_note(
    case_id: uuid.UUID, entry_id: uuid.UUID, user: UserDep, session: SessionDep
) -> PostOpEntryOut:
    _no_admin(user)
    case = case_service.load_case(session, case_id)
    postop_service.require_editor(case, user)
    entry = postop_service.load_entry(session, case_id, entry_id)
    postop_service.regenerate_draft(session, entry)
    session.commit()
    return _entry_out(session, entry)


@router.post("/cases/{case_id}/postop/{entry_id}/note/approve", response_model=PostOpEntryOut)
def approve_note(
    case_id: uuid.UUID,
    entry_id: uuid.UUID,
    body: NoteApproveIn,
    request: Request,
    user: UserDep,
    session: SessionDep,
    config: ConfigDep,
) -> PostOpEntryOut:
    """«Проверено»: the doctor confirms (and may have edited) the draft; copying unlocks."""
    _no_admin(user)
    case = case_service.load_case(session, case_id)
    entry = postop_service.load_entry(session, case_id, entry_id)
    postop_service.approve_note(
        session, case, entry, body.general_condition, body.local_status, user, ip_of(request)
    )
    # Keep an existing T6 document in step with the approved wording.
    spec = docs.spec_or_404(config, T6)
    inp, _ = docs.build_render_input(session, case, config, user, entry)
    if docs.document_state(session, case, spec, inp, entry)["status"] != "not_generated":
        # Missing vitals etc.: the doctor sees the reasons on the document page.
        with contextlib.suppress(ApiError):
            docs.generate(session, case, spec, inp, user, ip_of(request), entry)
    session.commit()
    return _entry_out(session, entry)


# ---- T6 document for one entry (same copy-cell behaviour as T1-T3) ----


def _doc_context(session: Any, case_id: uuid.UUID, entry_id: uuid.UUID, user: Any, config: Any):  # type: ignore[no-untyped-def]
    case = case_service.load_case(session, case_id)
    entry = postop_service.load_entry(session, case_id, entry_id)
    spec = docs.spec_or_404(config, T6)
    inp, _ = docs.build_render_input(session, case, config, user, entry)
    return case, entry, spec, inp


def _full(state: dict[str, Any]) -> DocumentOut:
    return DocumentOut(**{**state, "all_text": docs.all_text(state["fields"])})


@router.get("/cases/{case_id}/postop/{entry_id}/document", response_model=DocumentOut)
def get_document(
    case_id: uuid.UUID, entry_id: uuid.UUID, user: UserDep, session: SessionDep, config: ConfigDep
) -> DocumentOut:
    _no_admin(user)
    case, entry, spec, inp = _doc_context(session, case_id, entry_id, user, config)
    state = docs.document_state(session, case, spec, inp, entry)
    session.commit()
    return _full(state)


@router.post("/cases/{case_id}/postop/{entry_id}/document/generate", response_model=DocumentOut)
def generate_document(
    case_id: uuid.UUID,
    entry_id: uuid.UUID,
    request: Request,
    user: UserDep,
    session: SessionDep,
    config: ConfigDep,
) -> DocumentOut:
    _no_admin(user)
    case, entry, spec, inp = _doc_context(session, case_id, entry_id, user, config)
    postop_service.require_editor(case, user)
    docs.generate(session, case, spec, inp, user, ip_of(request), entry)
    session.commit()
    return _full(docs.document_state(session, case, spec, inp, entry))


@router.post(
    "/cases/{case_id}/postop/{entry_id}/document/fields/{key}/copied", response_model=DocumentOut
)
def mark_copied(
    case_id: uuid.UUID,
    entry_id: uuid.UUID,
    key: str,
    body: dict[str, bool],
    request: Request,
    user: UserDep,
    session: SessionDep,
    config: ConfigDep,
) -> DocumentOut:
    _no_admin(user)
    case, entry, spec, inp = _doc_context(session, case_id, entry_id, user, config)
    postop_service.require_editor(case, user)
    docs.set_copied(
        session,
        case,
        spec,
        key,
        bool(body.get("copied")),
        user,
        ip_of(request),
        entry,
        notes_approved=inp.notes_approved,
    )
    session.commit()
    return _full(docs.document_state(session, case, spec, inp, entry))


@router.post("/cases/{case_id}/postop/{entry_id}/document/copy-all", response_model=DocumentOut)
def copy_all(
    case_id: uuid.UUID,
    entry_id: uuid.UUID,
    request: Request,
    user: UserDep,
    session: SessionDep,
    config: ConfigDep,
) -> DocumentOut:
    _no_admin(user)
    case, entry, spec, inp = _doc_context(session, case_id, entry_id, user, config)
    postop_service.require_editor(case, user)
    state = docs.document_state(session, case, spec, inp, entry)
    audit.record(
        session,
        user_id=user.id,
        action=AuditAction.COPY,
        entity="generated_document",
        entity_id=case.id,
        diff={"template_id": T6, "key": "*"},
        ip=ip_of(request),
    )
    session.commit()
    return _full(state)


# ---- optional wound photo (storage interface; disabled in demo mode) ----


def _sniff(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


@router.put("/cases/{case_id}/postop/{entry_id}/photo", response_model=PostOpEntryOut)
async def upload_photo(
    case_id: uuid.UUID,
    entry_id: uuid.UUID,
    request: Request,
    user: UserDep,
    session: SessionDep,
    config: ConfigDep,
) -> PostOpEntryOut:
    body = await request.body()
    declared = (request.headers.get("content-type") or "").split(";")[0].strip()

    def work() -> PostOpEntryOut:
        _no_admin(user)
        case = case_service.load_case(session, case_id)
        postop_service.require_editor(case, user)
        entry = postop_service.load_entry(session, case_id, entry_id)
        store = storage.get_storage()
        if isinstance(store, storage.DisabledStorage):
            raise ApiError(409, "storage_disabled", "Загрузка фото отключена")
        if len(body) == 0 or len(body) > storage.MAX_BYTES:
            raise ApiError(413, "photo_size", "Фото должно быть не более 5 МБ")
        sniffed = _sniff(body)
        if sniffed is None or sniffed != declared:
            raise ApiError(415, "photo_type", "Допустимы только JPEG, PNG или WebP")
        key = storage.new_photo_key(case_id, sniffed)
        store.put(key, body, sniffed)
        data = PostOpData.model_validate(entry.data).model_copy(update={"photo_key": key})
        entry.data = data.model_dump(mode="json")
        audit.record(
            session,
            user_id=user.id,
            action=AuditAction.CREATE,
            entity="wound_photo",
            entity_id=entry.id,
            diff={"bytes": len(body)},
            ip=ip_of(request),
        )
        session.commit()
        return _entry_out(session, entry)

    return await run_in_threadpool(work)


@router.get("/cases/{case_id}/postop/{entry_id}/photo")
def get_photo(
    case_id: uuid.UUID, entry_id: uuid.UUID, request: Request, user: UserDep, session: SessionDep
) -> Response:
    _no_admin(user)
    entry = postop_service.load_entry(session, case_id, entry_id)
    key = PostOpData.model_validate(entry.data).photo_key
    if key is None:
        raise not_found("Фото")
    try:
        found = storage.get_storage().get(key)
    except storage.StorageDisabled:
        raise ApiError(409, "storage_disabled", "Загрузка фото отключена") from None
    if found is None:
        raise not_found("Фото")
    audit.record(
        session,
        user_id=user.id,
        action=AuditAction.VIEW,
        entity="wound_photo",
        entity_id=entry.id,
        ip=ip_of(request),
    )
    session.commit()
    content, content_type = found
    return Response(
        content, media_type=content_type, headers={"Cache-Control": "private, no-store"}
    )
