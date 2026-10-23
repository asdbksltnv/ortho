import hmac
from typing import Any

from fastapi import APIRouter, Header, Request, Response

from app.api.deps import SessionDep, UserDep, ip_of
from app.api.errors import ApiError, not_found
from app.domain.enums import AuditAction
from app.models.user import User
from app.schemas.api import TelegramLinkOut
from app.services import audit, telegram

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/link-code", response_model=TelegramLinkOut)
def link_code(user: UserDep, session: SessionDep, request: Request) -> TelegramLinkOut:
    """One-time code; the user then sends «/start <code>» to the bot."""
    row = session.get(User, user.id)
    if row is None:
        raise not_found("Пользователь")
    code, expires = telegram.create_link_code(session, row)
    audit.record(
        session,
        user_id=user.id,
        action=AuditAction.UPDATE,
        entity="telegram_link",
        entity_id=user.id,
        ip=ip_of(request),
    )
    session.commit()
    from datetime import datetime

    return TelegramLinkOut(
        code=code, expires_at=datetime.fromisoformat(expires), command=f"/start {code}"
    )


@router.delete("/link", status_code=204)
def unlink(user: UserDep, session: SessionDep) -> None:
    row = session.get(User, user.id)
    if row is None:
        raise not_found("Пользователь")
    row.telegram_chat_id = None
    row.telegram_link_code = None
    row.telegram_link_expires = None
    session.commit()


@router.post("/webhook", status_code=200)
def webhook(
    update: dict[str, Any],
    session: SessionDep,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> Response:
    """Telegram → us (TELEGRAM_MODE=webhook). Authenticated by the secret token header."""
    expected = telegram.webhook_secret()
    if not x_telegram_bot_api_secret_token or not hmac.compare_digest(
        x_telegram_bot_api_secret_token, expected
    ):
        raise ApiError(403, "forbidden", "Недостаточно прав для этого действия")
    telegram.handle_update(session, update, telegram.get_client())
    return Response(status_code=200)
