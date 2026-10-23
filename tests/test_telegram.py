import json
from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from app.domain.enums import Role
from app.models.base import utcnow
from app.models.user import User
from app.services import telegram
from app.services.telegram import TelegramClient, TelegramError, handle_update, webhook_secret
from tests.conftest import Api, FakeTelegram


def message(text: str, chat: int = 4242) -> dict[str, Any]:
    return {
        "update_id": 1,
        "message": {"chat": {"id": chat}, "text": text, "from": {"first_name": "Тест"}},
    }


def user(db: Any, login: str) -> User:
    with db() as s:
        return s.scalars(select(User).where(User.login == login)).one()


def request_code(role: Role = Role.NURSE) -> str:
    resp = Api().as_role(role).post("/telegram/link-code")
    assert resp.status_code == 200
    body = resp.json()
    assert body["command"] == f"/start {body['code']}" and len(body["code"]) == 8
    return str(body["code"])


def test_linking_flow_connects_the_chat_and_uses_the_code_once(
    api: Api, db: Any, telegram_fake: FakeTelegram
) -> None:
    code = request_code()
    with db() as s:
        handle_update(s, message(f"/start {code}"), telegram_fake)  # type: ignore[arg-type]
    assert (
        user(db, "nurse").telegram_chat_id == "4242"
        and user(db, "nurse").telegram_link_code is None
    )
    assert telegram_fake.sent == [("4242", telegram.LINKED_TEXT)]
    assert Api().as_role(Role.NURSE).get("/auth/me").json()["telegram_linked"] is True
    with db() as s:
        handle_update(s, message(f"/start {code}", chat=999), telegram_fake)  # type: ignore[arg-type]
    assert user(db, "nurse").telegram_chat_id == "4242"  # a replayed code does nothing
    assert telegram_fake.sent[-1] == ("999", telegram.UNKNOWN_CODE_TEXT)


def test_codes_expire_and_are_case_insensitive(
    api: Api, db: Any, telegram_fake: FakeTelegram
) -> None:
    code = request_code()
    with db() as s:
        row = s.scalars(select(User).where(User.login == "nurse")).one()
        row.telegram_link_expires = utcnow() - timedelta(seconds=1)
        s.commit()
        handle_update(s, message(f"/start {code}"), telegram_fake)  # type: ignore[arg-type]
    assert user(db, "nurse").telegram_chat_id is None
    code = request_code()
    with db() as s:
        handle_update(s, message(f"/start {code.lower()}"), telegram_fake)  # type: ignore[arg-type]
    assert user(db, "nurse").telegram_chat_id == "4242"


def test_bad_input_gets_a_help_reply_and_changes_nothing(
    api: Api, db: Any, telegram_fake: FakeTelegram
) -> None:
    for text in ("/start", "/start WRONG123", "привет", ""):
        with db() as s:
            handle_update(s, message(text), telegram_fake)  # type: ignore[arg-type]
    assert [t for _, t in telegram_fake.sent] == [
        telegram.UNKNOWN_CODE_TEXT,
        telegram.UNKNOWN_CODE_TEXT,
        telegram.HELP_TEXT,
        telegram.HELP_TEXT,
    ]
    with db() as s:
        handle_update(s, {"update_id": 2}, telegram_fake)  # type: ignore[arg-type]  # no message
    assert len(telegram_fake.sent) == 4


def test_replies_never_contain_names(api: Api, db: Any, telegram_fake: FakeTelegram) -> None:
    code = request_code()
    with db() as s:
        handle_update(s, message(f"/start {code}"), telegram_fake)  # type: ignore[arg-type]
    for _, text in telegram_fake.sent:
        assert "Тест" not in text and "nurse" not in text


def test_unlinking(api: Api, db: Any, telegram_fake: FakeTelegram) -> None:
    code = request_code()
    with db() as s:
        handle_update(s, message(f"/start {code}"), telegram_fake)  # type: ignore[arg-type]
    assert Api().as_role(Role.NURSE).delete("/telegram/link").status_code == 204
    assert user(db, "nurse").telegram_chat_id is None


def test_webhook_requires_the_secret_header(api: Api, db: Any, telegram_fake: FakeTelegram) -> None:
    code = request_code()
    client = Api().client
    update = message(f"/start {code}")
    assert client.post("/api/v1/telegram/webhook", json=update).status_code == 403
    assert (
        client.post(
            "/api/v1/telegram/webhook",
            json=update,
            headers={"X-Telegram-Bot-Api-Secret-Token": "nope"},
        ).status_code
        == 403
    )
    assert user(db, "nurse").telegram_chat_id is None
    ok = client.post(
        "/api/v1/telegram/webhook",
        json=update,
        headers={"X-Telegram-Bot-Api-Secret-Token": webhook_secret()},
    )
    assert ok.status_code == 200 and user(db, "nurse").telegram_chat_id == "4242"


def test_webhook_secret_is_stable_and_depends_on_the_server_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.settings import get_settings

    first = webhook_secret()
    assert first == webhook_secret() and len(first) == 48
    monkeypatch.setenv("SECRET_KEY", "another-secret-key-that-is-long-enough-123")
    get_settings.cache_clear()
    assert webhook_secret() != first


# ---- the Bot API client itself ----


def client_with(handler: Any) -> TelegramClient:
    return TelegramClient("123:SECRET-TOKEN", httpx.Client(transport=httpx.MockTransport(handler)))


def test_send_message_posts_to_the_bot_api() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True, "result": {}})

    client_with(handler).send_message("42", "Пал. 3, к. 2 (А. Д.): анализы готовы")
    assert str(seen[0].url) == "https://api.telegram.org/bot123:SECRET-TOKEN/sendMessage"
    assert json.loads(seen[0].content) == {
        "chat_id": "42",
        "text": "Пал. 3, к. 2 (А. Д.): анализы готовы",
    }


@pytest.mark.parametrize(
    "handler",
    [
        lambda r: httpx.Response(500),
        lambda r: httpx.Response(200, json={"ok": False, "error_code": 400}),
        lambda r: (_ for _ in ()).throw(
            httpx.ConnectError("boom: https://api.telegram.org/bot123:SECRET-TOKEN")
        ),
    ],
)
def test_delivery_errors_never_leak_the_token(handler: Any) -> None:
    with pytest.raises(TelegramError) as exc:
        client_with(handler).send_message("42", "x")
    assert "SECRET-TOKEN" not in str(exc.value) and "telegram.org" not in str(exc.value)


def test_get_updates_and_webhook_registration() -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.url.path.rsplit("/", 1)[-1], json.loads(request.content)))
        return httpx.Response(200, json={"ok": True, "result": [{"update_id": 7}]})

    client = client_with(handler)
    assert client.get_updates(5, timeout=1) == [{"update_id": 7}]
    client.set_webhook("https://example.org/api/v1/telegram/webhook", "s3cret")
    client.delete_webhook()
    assert calls[0] == ("getUpdates", {"timeout": 1, "allowed_updates": ["message"], "offset": 5})
    assert calls[1] == (
        "setWebhook",
        {"url": "https://example.org/api/v1/telegram/webhook", "secret_token": "s3cret"},
    )
    assert calls[2][0] == "deleteWebhook"


def test_no_client_without_a_token() -> None:
    telegram.set_client_for_tests(None)
    assert telegram.get_client() is None
