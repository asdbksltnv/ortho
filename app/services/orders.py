import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ApiError, forbidden, not_found
from app.auth import CurrentUser
from app.domain.enums import AuditAction, ItemStatus, Role
from app.domain.permissions import can_edit_case
from app.models.case import Case, ChecklistItem, Order
from app.models.user import User
from app.services import audit
from app.services.cases import refresh_first_ready
from app.services.config_loader import AppConfig
from app.services.notify import case_label, notify

ORDER_TYPES = ("lab", "imaging", "consult", "other")
TYPE_LABEL = {
    "lab": "анализы",
    "imaging": "исследование",
    "consult": "консультация",
    "other": "назначение",
}

# Allowed moves; "cancelled" is reachable from every open status.
NEXT = {
    "ordered": ("in_progress", "cancelled"),
    "in_progress": ("result_available", "cancelled"),
    "result_available": ("reviewed", "cancelled"),
    "reviewed": (),
    "cancelled": (),
}
OPEN = ("ordered", "in_progress", "result_available")
DOCTOR_ONLY = {"reviewed", "cancelled"}
RESULT_STAFF = {Role.NURSE, Role.HEAD_NURSE, Role.DOCTOR, Role.HEAD_OF_DEPARTMENT}


def _assignee(session: Session, assignee_id: uuid.UUID) -> User:
    user = session.get(User, assignee_id)
    if user is None or not user.is_active or user.role == Role.ADMIN.value:
        raise ApiError(422, "assignee_invalid", "Исполнитель не найден")
    return user


def create_order(
    session: Session,
    case: Case,
    *,
    type_: str,
    item: str,
    assignee_id: uuid.UUID,
    linked_checklist_key: str | None,
    at_round: bool,
    user: CurrentUser,
    config: AppConfig,
    ip: str | None,
) -> Order:
    if type_ not in ORDER_TYPES:
        raise ApiError(422, "order_type_invalid", "Неизвестный тип назначения")
    if not can_edit_case(user.role, is_treating_doctor=case.treating_doctor_id == user.id):
        raise forbidden()
    assignee = _assignee(session, assignee_id)
    if linked_checklist_key is not None and linked_checklist_key not in config.checklist_by_key:
        raise ApiError(422, "checklist_key_invalid", "Неизвестный пункт чек-листа")

    order = Order(
        case_id=case.id,
        type=type_,
        item=item.strip(),
        assignee_id=assignee.id,
        linked_checklist_key=linked_checklist_key,
        created_at_round=at_round,
    )
    session.add(order)
    if linked_checklist_key is not None:
        # A pre-operative order keeps its checklist item pending until the doctor reviews it.
        row = next((i for i in case.checklist_items if i.key == linked_checklist_key), None)
        if row is not None and row.status != ItemStatus.PENDING.value:
            row.status = ItemStatus.PENDING.value
        refresh_first_ready(case, config)
    session.flush()
    audit.record(
        session,
        user_id=user.id,
        action=AuditAction.CREATE,
        entity="order",
        entity_id=order.id,
        diff={"case_id": str(case.id), "type": type_, "round": at_round},
        ip=ip,
    )
    if assignee.id != user.id:
        notify(
            session,
            [assignee],
            "order_assigned",
            f"{case_label(case)}: новое назначение ({TYPE_LABEL[type_]})",
            case=case,
        )
    return order


def pending_linked_orders(session: Session, case_id: uuid.UUID, key: str) -> int:
    rows = session.scalars(
        select(Order.id).where(
            Order.case_id == case_id,
            Order.linked_checklist_key == key,
            Order.status.in_(OPEN),
        )
    )
    return len(list(rows))


def update_status(
    session: Session,
    order: Order,
    case: Case,
    target: str,
    user: CurrentUser,
    ip: str | None,
) -> Order:
    if target not in NEXT.get(order.status, ()):
        raise ApiError(409, "order_transition_not_allowed", "Такой переход статуса недоступен")
    is_doctor = can_edit_case(user.role, is_treating_doctor=case.treating_doctor_id == user.id)
    if target in DOCTOR_ONLY:
        if not is_doctor:
            raise forbidden()  # only a doctor reviews results or cancels
    elif user.role not in RESULT_STAFF and order.assignee_id != user.id:
        raise forbidden()
    old = order.status
    order.status = target
    audit.record(
        session,
        user_id=user.id,
        action=AuditAction.UPDATE,
        entity="order",
        entity_id=order.id,
        diff={"status": [old, target]},
        ip=ip,
    )
    if target == "result_available":
        creator = session.get(User, order.created_by) if order.created_by else case.treating_doctor
        text = "анализы готовы" if order.type == "lab" else "результат готов"
        notify(
            session,
            [creator or case.treating_doctor],
            "result_ready",
            f"{case_label(case)}: {text}",
            case=case,
        )
    session.flush()
    return order


def load_order(session: Session, order_id: uuid.UUID) -> Order:
    order = session.get(Order, order_id)
    if order is None:
        raise not_found("Назначение")
    return order


def checklist_item(case: Case, key: str) -> ChecklistItem | None:
    return next((i for i in case.checklist_items if i.key == key), None)
