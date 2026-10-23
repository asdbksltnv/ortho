import uuid

from fastapi import APIRouter, Request
from sqlalchemy import select

from app.api.deps import CaseReader, SessionDep, UsersAdmin, ip_of
from app.api.errors import ApiError, not_found
from app.auth import hash_password
from app.domain.enums import AuditAction, Role
from app.models.user import User
from app.schemas.api import PasswordReset, StaffOut, UserCreate, UserOut, UserUpdate
from app.services import audit

router = APIRouter(tags=["users"])


@router.get("/users", response_model=list[UserOut])
def list_users(session: SessionDep, _: UsersAdmin) -> list[User]:
    return list(session.scalars(select(User).order_by(User.full_name)))


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    data: UserCreate,
    request: Request,
    session: SessionDep,
    admin: UsersAdmin,
) -> User:
    if session.scalars(select(User).where(User.login == data.login)).first():
        raise ApiError(409, "login_taken", "Такой логин уже существует")
    user = User(
        login=data.login,
        full_name=data.full_name,
        role=data.role.value,
        password_hash=hash_password(data.password),
    )
    session.add(user)
    session.flush()
    audit.record(
        session,
        user_id=admin.id,
        action=AuditAction.CREATE,
        entity="user",
        entity_id=user.id,
        diff={"role": data.role.value},
        ip=ip_of(request),
    )
    session.commit()
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    request: Request,
    session: SessionDep,
    admin: UsersAdmin,
) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise not_found("Пользователь")
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if user.id == admin.id and (changes.get("is_active") is False or "role" in changes):
        raise ApiError(
            409, "self_lockout", "Нельзя изменить собственную роль или заблокировать себя"
        )
    diff: dict[str, object] = {}
    for field, value in changes.items():
        value = value.value if isinstance(value, Role) else value
        if getattr(user, field) != value:
            diff[field] = [getattr(user, field), value] if field != "full_name" else "changed"
            setattr(user, field, value)
    if diff:
        audit.record(
            session,
            user_id=admin.id,
            action=AuditAction.UPDATE,
            entity="user",
            entity_id=user.id,
            diff=diff,
            ip=ip_of(request),
        )
    session.commit()
    return user


@router.post("/users/{user_id}/reset-password", status_code=204)
def reset_password(
    user_id: uuid.UUID,
    data: PasswordReset,
    request: Request,
    session: SessionDep,
    admin: UsersAdmin,
) -> None:
    user = session.get(User, user_id)
    if user is None:
        raise not_found("Пользователь")
    user.password_hash = hash_password(data.password)
    audit.record(
        session,
        user_id=admin.id,
        action=AuditAction.UPDATE,
        entity="user_password",
        entity_id=user.id,
        ip=ip_of(request),
    )
    session.commit()


@router.get("/staff", response_model=list[StaffOut])
def staff(
    session: SessionDep,
    _: CaseReader,
) -> list[User]:
    """Active clinical staff for pickers (treating doctor, assignees). No credentials."""
    return list(
        session.scalars(
            select(User)
            .where(User.is_active.is_(True), User.role != Role.ADMIN.value)
            .order_by(User.full_name)
        )
    )
