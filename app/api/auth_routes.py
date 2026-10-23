from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select

from app.api.deps import SessionDep, UserDep, ip_of
from app.api.errors import ApiError, unauthorized
from app.auth import (
    clear_session_cookies,
    hash_password,
    new_csrf_token,
    rate_limiter,
    set_session_cookies,
    verify_password,
)
from app.domain.enums import AuditAction
from app.models.user import User
from app.schemas.api import ChangePasswordIn, LoginIn, UserOut
from app.services import audit
from app.settings import Settings, get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.post("/login", response_model=UserOut)
def login(
    data: LoginIn, request: Request, response: Response, session: SessionDep, settings: SettingsDep
) -> User:
    ip = ip_of(request)
    key = f"{ip}|{data.login.lower()}"
    window = settings.login_window_min * 60
    if rate_limiter.is_blocked(key, settings.login_max_failures, window):
        raise ApiError(429, "rate_limited", "Слишком много попыток входа. Попробуйте позже")

    user = session.scalars(select(User).where(User.login == data.login)).one_or_none()
    valid = verify_password(data.password, user.password_hash if user else None)
    if user is None or not valid or not user.is_active:
        rate_limiter.record_failure(key, window)
        audit.record(
            session,
            user_id=None,
            action=AuditAction.LOGIN,
            entity="session",
            diff={"success": False},
            ip=ip,
        )
        session.commit()
        raise ApiError(401, "invalid_credentials", "Неверный логин или пароль")

    rate_limiter.reset(key)
    audit.record(
        session,
        user_id=user.id,
        action=AuditAction.LOGIN,
        entity="session",
        entity_id=user.id,
        diff={"success": True},
        ip=ip,
    )
    session.commit()
    set_session_cookies(response, user.id, new_csrf_token(), settings)
    return user


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    clear_session_cookies(response)


@router.get("/me", response_model=UserOut)
def me(user: UserDep, session: SessionDep) -> User:
    result = session.get(User, user.id)
    if result is None:
        raise unauthorized()
    return result


@router.post("/change-password", status_code=204)
def change_password(
    data: ChangePasswordIn, user: UserDep, session: SessionDep, request: Request
) -> None:
    row = session.get(User, user.id)
    if row is None:
        raise unauthorized()
    if not verify_password(data.current_password, row.password_hash):
        raise ApiError(422, "wrong_password", "Текущий пароль указан неверно")
    row.password_hash = hash_password(data.new_password)
    audit.record(
        session,
        user_id=user.id,
        action=AuditAction.UPDATE,
        entity="user_password",
        entity_id=user.id,
        ip=ip_of(request),
    )
    session.commit()
