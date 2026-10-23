"""Notifications: an in-app row for everyone, plus Telegram where linked.

Messages contain no names or record numbers: only room/bed, initials and the event, e.g.
«Пал. 3, к. 2 (А. Д.): анализы готовы». Delivery failures are stored and never block the caller.
"""

import logging
from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import Role
from app.domain.privacy import initials
from app.models.base import utcnow
from app.models.case import Case, Notification
from app.models.user import User
from app.services import telegram

logger = logging.getLogger("notify")


def case_label(case: Case) -> str:
    """'Пал. 3, к. 2 (А. Д.)': the only way a patient is referred to in messages."""
    who = initials(case.patient.full_name)
    if case.bed is not None:
        return f"{case.bed.room.name}, {case.bed.label} ({who})"
    return f"без койки ({who})"


def notify(
    session: Session,
    users: Iterable[User],
    event: str,
    text: str,
    *,
    case: Case | None = None,
    extra: dict[str, Any] | None = None,
) -> list[Notification]:
    payload: dict[str, Any] = {"text": text, **(extra or {})}
    if case is not None:
        payload["case_id"] = str(case.id)  # opaque id, so the app can link to the case
    client = telegram.get_client()
    created: list[Notification] = []
    seen: set[Any] = set()
    for user in users:
        if user.id in seen or not user.is_active:
            continue
        seen.add(user.id)
        now = utcnow()
        created.append(_add(session, user, "app", event, payload, sent_at=now, error=None))
        if user.telegram_chat_id and client is not None:
            row = _add(session, user, "telegram", event, payload, sent_at=None, error=None)
            try:
                client.send_message(user.telegram_chat_id, text)
                row.sent_at = utcnow()
            except telegram.TelegramError as exc:
                row.error = str(exc)  # class/status only; never blocks the user's action
                logger.warning("telegram delivery failed: %s", exc)
            except Exception as exc:  # noqa: BLE001 - a notification must never break the request
                row.error = type(exc).__name__
                logger.warning("telegram delivery failed: %s", type(exc).__name__)
            created.append(row)
    session.flush()
    return created


def _add(
    session: Session,
    user: User,
    channel: str,
    event: str,
    payload: dict[str, Any],
    *,
    sent_at: Any,
    error: str | None,
) -> Notification:
    row = Notification(
        user_id=user.id,
        channel=channel,
        event=event,
        payload=dict(payload),
        sent_at=sent_at,
        error=error,
    )
    session.add(row)
    return row


def users_with_roles(session: Session, *roles: Role) -> list[User]:
    return list(
        session.scalars(
            select(User).where(User.role.in_([r.value for r in roles]), User.is_active.is_(True))
        )
    )
