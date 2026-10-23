"""Telegram Bot API over HTTPS (httpx). Messages never carry names: see app.services.notify."""

import contextlib
import hashlib
import hmac
import logging
import secrets
import threading
from datetime import timedelta
from functools import lru_cache
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.user import User
from app.settings import get_settings

logger = logging.getLogger("telegram")

LINK_CODE_TTL = timedelta(minutes=15)
LINKED_TEXT = "Telegram подключён. Здесь будут приходить уведомления отделения."
UNKNOWN_CODE_TEXT = "Код не найден или устарел. Получите новый код в профиле OrthoReady."
HELP_TEXT = "Отправьте /start и код из профиля OrthoReady, чтобы подключить уведомления."


class TelegramError(Exception):
    """Delivery failed. The message never contains the request URL (it holds the bot token)."""


class TelegramClient:
    def __init__(self, token: str, http: httpx.Client | None = None) -> None:
        self._base = f"https://api.telegram.org/bot{token}"
        self._http = http or httpx.Client(timeout=15.0)

    def _call(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._http.post(f"{self._base}/{method}", json=payload)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
        except httpx.HTTPStatusError as exc:
            raise TelegramError(f"HTTP {exc.response.status_code}") from None
        except httpx.HTTPError as exc:
            raise TelegramError(type(exc).__name__) from None
        if not data.get("ok"):
            raise TelegramError(f"api error {data.get('error_code', '')}")
        return data

    def send_message(self, chat_id: str, text: str) -> None:
        self._call("sendMessage", {"chat_id": chat_id, "text": text})

    def get_updates(self, offset: int | None, timeout: int = 25) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"timeout": timeout, "allowed_updates": ["message"]}
        if offset is not None:
            payload["offset"] = offset
        result: list[dict[str, Any]] = self._call("getUpdates", payload).get("result", [])
        return result

    def set_webhook(self, url: str, secret_token: str) -> None:
        self._call("setWebhook", {"url": url, "secret_token": secret_token})

    def delete_webhook(self) -> None:
        self._call("deleteWebhook", {})


_override: TelegramClient | None = None


def set_client_for_tests(client: TelegramClient | None) -> None:
    global _override
    _override = client


@lru_cache
def _configured_client(token: str) -> TelegramClient:
    return TelegramClient(token)


def get_client() -> TelegramClient | None:
    if _override is not None:
        return _override
    token = get_settings().telegram_bot_token
    return _configured_client(token) if token else None


def webhook_secret() -> str:
    """Header secret Telegram echoes back; derived so nothing extra needs configuring."""
    key = get_settings().secret_key.encode()
    return hmac.new(key, b"telegram-webhook", hashlib.sha256).hexdigest()[:48]


def create_link_code(session: Session, user: User) -> tuple[str, str]:
    """One-time code the user sends to the bot as «/start <code>». Returns (code, expires_iso)."""
    code = secrets.token_hex(4).upper()
    user.telegram_link_code = code
    user.telegram_link_expires = utcnow() + LINK_CODE_TTL
    session.flush()
    return code, user.telegram_link_expires.isoformat()


def handle_update(session: Session, update: dict[str, Any], client: TelegramClient | None) -> None:
    """Handles `/start <code>`; replies without any patient or staff names."""
    message = update.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    text = (message.get("text") or "").strip()
    if chat_id is None:
        return
    reply = HELP_TEXT
    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        code = parts[1].strip().upper() if len(parts) == 2 else ""
        user = (
            session.scalars(select(User).where(User.telegram_link_code == code)).one_or_none()
            if code
            else None
        )
        if user and user.telegram_link_expires and user.telegram_link_expires > utcnow():
            user.telegram_chat_id = str(chat_id)
            user.telegram_link_code = None
            user.telegram_link_expires = None
            session.commit()
            reply = LINKED_TEXT
        else:
            reply = UNKNOWN_CODE_TEXT
    if client is not None:
        try:
            client.send_message(str(chat_id), reply)
        except TelegramError as exc:
            logger.warning("reply failed: %s", exc)


def start_background_worker() -> None:
    """Webhook registration or long polling, chosen by TELEGRAM_MODE. No-op without a token."""
    settings = get_settings()
    client = get_client()
    if client is None:
        return
    if settings.telegram_mode == "webhook":
        if settings.public_url:
            try:
                client.set_webhook(
                    f"{settings.public_url.rstrip('/')}/api/v1/telegram/webhook", webhook_secret()
                )
            except TelegramError as exc:
                logger.warning("setWebhook failed: %s", exc)
        return
    threading.Thread(
        target=_poll_forever, args=(client,), daemon=True, name="telegram-poll"
    ).start()


def _poll_forever(client: TelegramClient) -> None:  # pragma: no cover - network loop
    from app.db import get_session_factory

    with contextlib.suppress(TelegramError):
        client.delete_webhook()
    offset: int | None = None
    while True:
        try:
            for update in client.get_updates(offset):
                offset = int(update["update_id"]) + 1
                with get_session_factory()() as session:
                    handle_update(session, update, client)
        except TelegramError as exc:
            logger.warning("poll failed: %s", exc)
            threading.Event().wait(5)
