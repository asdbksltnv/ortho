import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.cases import _case_out
from app.api.deps import ConfigDep, SessionDep, UserDep, ip_of
from app.api.errors import forbidden, not_found
from app.auth import CurrentUser, require_perm
from app.domain.enums import CaseStatus, Role
from app.domain.permissions import Perm, can_edit_case
from app.models.case import Case, CaseStatusEvent, Notification, Order
from app.models.user import User
from app.schemas.api import (
    CaseOut,
    NotificationOut,
    OrderFromSetIn,
    OrderIn,
    OrderOut,
    OrderSetOut,
    OrderStatusIn,
    StatusEventOut,
    TransitionIn,
)
from app.services import cases as case_service
from app.services import orders as order_service
from app.services.notify import case_label
from app.services.transitions import transition_case

router = APIRouter(tags=["workflow"])
OrderCreator = Annotated[CurrentUser, Depends(require_perm(Perm.ORDER_CREATE))]


# ---------------------------------------------------------------- status flow


@router.post("/cases/{case_id}/transition", response_model=CaseOut)
def transition(
    case_id: uuid.UUID,
    body: TransitionIn,
    request: Request,
    user: UserDep,
    session: SessionDep,
    config: ConfigDep,
) -> CaseOut:
    if user.role is Role.ADMIN:
        raise forbidden()
    case = case_service.load_case(session, case_id)
    transition_case(
        session,
        case,
        body.to,
        user,
        config,
        reason=body.reason,
        planned_date=body.planned_surgery_date,
        planned_time=body.planned_surgery_time,
        ip=ip_of(request),
    )
    session.commit()
    return _case_out(session, case_service.load_case(session, case_id), user, config)


@router.get("/cases/{case_id}/events", response_model=list[StatusEventOut])
def status_events(case_id: uuid.UUID, user: UserDep, session: SessionDep) -> list[StatusEventOut]:
    if user.role is Role.ADMIN:
        raise forbidden()
    names = {u.id: u.full_name for u in session.scalars(select(User))}
    rows = session.scalars(
        select(CaseStatusEvent)
        .where(CaseStatusEvent.case_id == case_id)
        .order_by(CaseStatusEvent.created_at)
    )
    return [
        StatusEventOut(
            from_status=CaseStatus(r.from_status) if r.from_status else None,
            to_status=CaseStatus(r.to_status),
            user_name=names.get(r.user_id),
            reason=r.reason,
            is_override=r.is_override,
            created_at=r.created_at,
        )
        for r in rows
    ]


# ---------------------------------------------------------------- orders


def _order_out(
    order: Order, case: Case, names: dict[uuid.UUID, str], viewer: CurrentUser
) -> OrderOut:
    next_statuses = list(order_service.NEXT.get(order.status, ()))
    is_doctor = can_edit_case(viewer.role, is_treating_doctor=case.treating_doctor_id == viewer.id)
    if not is_doctor:
        next_statuses = [s for s in next_statuses if s not in order_service.DOCTOR_ONLY]
    return OrderOut(
        id=order.id,
        case_id=order.case_id,
        type=order.type,
        item=order.item,
        assignee_id=order.assignee_id,
        assignee_name=names.get(order.assignee_id, ""),
        status=order.status,
        linked_checklist_key=order.linked_checklist_key,
        created_at_round=order.created_at_round,
        created_at=order.created_at,
        case_label=case_label(case),
        next_statuses=next_statuses,
    )


def _names(session: Session) -> dict[uuid.UUID, str]:
    return {u.id: u.full_name for u in session.scalars(select(User))}


@router.get("/order-sets", response_model=list[OrderSetOut])
def order_sets(_: UserDep, config: ConfigDep) -> list[OrderSetOut]:
    return [
        OrderSetOut(key=s.key, name_ru=s.name_ru, orders=[o.model_dump() for o in s.orders])
        for s in config.order_sets.sets
    ]


@router.get("/cases/{case_id}/orders", response_model=list[OrderOut])
def case_orders(case_id: uuid.UUID, user: UserDep, session: SessionDep) -> list[OrderOut]:
    if user.role is Role.ADMIN:
        raise forbidden()
    case = case_service.load_case(session, case_id)
    names = _names(session)
    rows = session.scalars(
        select(Order).where(Order.case_id == case_id).order_by(Order.created_at.desc())
    )
    return [_order_out(o, case, names, user) for o in rows]


@router.post("/cases/{case_id}/orders", response_model=OrderOut, status_code=201)
def create_order(
    case_id: uuid.UUID,
    body: OrderIn,
    request: Request,
    user: OrderCreator,
    session: SessionDep,
    config: ConfigDep,
) -> OrderOut:
    case = case_service.load_case(session, case_id)
    order = order_service.create_order(
        session,
        case,
        type_=body.type,
        item=body.item,
        assignee_id=body.assignee_id,
        linked_checklist_key=body.linked_checklist_key,
        at_round=body.created_at_round,
        user=user,
        config=config,
        ip=ip_of(request),
    )
    session.commit()
    return _order_out(order, case, _names(session), user)


@router.post("/cases/{case_id}/orders/from-set", response_model=list[OrderOut], status_code=201)
def create_from_set(
    case_id: uuid.UUID,
    body: OrderFromSetIn,
    request: Request,
    user: OrderCreator,
    session: SessionDep,
    config: ConfigDep,
) -> list[OrderOut]:
    order_set = next((s for s in config.order_sets.sets if s.key == body.set_key), None)
    if order_set is None:
        raise not_found("Набор назначений")
    case = case_service.load_case(session, case_id)
    created = [
        order_service.create_order(
            session,
            case,
            type_=o.type,
            item=o.item,
            assignee_id=body.assignee_id,
            linked_checklist_key=None,
            at_round=body.created_at_round,
            user=user,
            config=config,
            ip=ip_of(request),
        )
        for o in order_set.orders
    ]
    session.commit()
    names = _names(session)
    return [_order_out(o, case, names, user) for o in created]


@router.patch("/orders/{order_id}/status", response_model=OrderOut)
def order_status(
    order_id: uuid.UUID,
    body: OrderStatusIn,
    request: Request,
    user: UserDep,
    session: SessionDep,
) -> OrderOut:
    if user.role is Role.ADMIN:
        raise forbidden()
    order = order_service.load_order(session, order_id)
    case = case_service.load_case(session, order.case_id)
    order_service.update_status(session, order, case, body.status, user, ip_of(request))
    session.commit()
    return _order_out(order, case, _names(session), user)


@router.get("/tasks", response_model=list[OrderOut])
def my_tasks(user: UserDep, session: SessionDep) -> list[OrderOut]:
    """«Мои задачи»: open orders assigned to me, plus results waiting for a doctor to review."""
    if user.role is Role.ADMIN:
        raise forbidden()
    names = _names(session)
    assigned = list(
        session.scalars(
            select(Order).where(
                Order.assignee_id == user.id, Order.status.in_(("ordered", "in_progress"))
            )
        )
    )
    to_review: list[Order] = []
    if user.role in (Role.DOCTOR, Role.HEAD_OF_DEPARTMENT):
        stmt = (
            select(Order)
            .join(Case, Case.id == Order.case_id)
            .where(Order.status == "result_available")
        )
        if user.role is Role.DOCTOR:
            stmt = stmt.where(Case.treating_doctor_id == user.id)
        to_review = list(session.scalars(stmt))
    out: list[OrderOut] = []
    seen: set[uuid.UUID] = set()
    for order in [*assigned, *to_review]:
        if order.id in seen:
            continue
        seen.add(order.id)
        case = case_service.load_case(session, order.case_id)
        out.append(_order_out(order, case, names, user))
    return out


@router.get("/orders/round-summary", response_model=list[OrderOut])
def round_summary(
    user: UserDep,
    session: SessionDep,
    since: Annotated[datetime, Query()],
) -> list[OrderOut]:
    """Orders I made at rounds since `since`; the UI groups them by patient and by assignee."""
    if user.role not in (Role.DOCTOR, Role.HEAD_OF_DEPARTMENT):
        raise forbidden()
    if since.tzinfo is None:
        since = since.replace(tzinfo=UTC)
    names = _names(session)
    rows = session.scalars(
        select(Order)
        .where(
            Order.created_by == user.id,
            Order.created_at_round.is_(True),
            Order.created_at >= since,
        )
        .order_by(Order.created_at)
    )
    out: list[OrderOut] = []
    for order in rows:
        case = case_service.load_case(session, order.case_id)
        out.append(_order_out(order, case, names, user))
    return out


# ---------------------------------------------------------------- notifications


@router.get("/notifications", response_model=list[NotificationOut])
def my_notifications(
    user: UserDep, session: SessionDep, limit: int = Query(30, ge=1, le=100)
) -> list[NotificationOut]:
    rows = session.scalars(
        select(Notification)
        .where(Notification.user_id == user.id, Notification.channel == "app")
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return [
        NotificationOut(
            id=n.id,
            event=n.event,
            text=str(n.payload.get("text", "")),
            case_id=uuid.UUID(str(n.payload["case_id"])) if n.payload.get("case_id") else None,
            created_at=n.created_at,
            read=n.read_at is not None,
        )
        for n in rows
    ]


@router.post("/notifications/read-all", status_code=204)
def read_all(user: UserDep, session: SessionDep) -> None:
    from app.models.base import utcnow

    for n in session.scalars(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.channel == "app",
            Notification.read_at.is_(None),
        )
    ):
        n.read_at = utcnow()
    session.commit()
