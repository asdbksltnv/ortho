import uuid
from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.auth import hash_password, rate_limiter
from app.db import Base, get_session
from app.domain.enums import Role
from app.main import app
from app.models.user import User
from app.models.ward import Bed, Room, Ward
from app.settings import get_settings

PASSWORD = "Passw0rd!12345"  # noqa: S105 - test fixture
LOGINS = {
    Role.DOCTOR: "doctor",
    Role.NURSE: "nurse",
    Role.ANAESTHESIOLOGIST: "anaesth",
    Role.HEAD_OF_DEPARTMENT: "head",
    Role.HEAD_NURSE: "headnurse",
    Role.ADMIN: "admin",
}


@pytest.fixture(autouse=True)
def _settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    import app.auth as auth_module

    # Cheap argon2 parameters keep the suite fast; production uses the library defaults.
    monkeypatch.setattr(
        auth_module, "_hasher", PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
    )
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-that-is-long-enough-123456")
    get_settings.cache_clear()
    rate_limiter.reset()
    yield
    get_settings.cache_clear()


@pytest.fixture
def db() -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_session] = override
    yield factory
    app.dependency_overrides.clear()
    engine.dispose()


class Api:
    """Test client wrapper that logs in and echoes the CSRF token like the SPA does."""

    def __init__(self) -> None:
        self.client = TestClient(app)

    def login(self, login: str, password: str = PASSWORD) -> Any:
        self.client.cookies.clear()
        return self.client.post("/api/v1/auth/login", json={"login": login, "password": password})

    def as_role(self, role: Role) -> "Api":
        assert self.login(LOGINS[role]).status_code == 200
        return self

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = kwargs.pop("headers", {})
        csrf = self.client.cookies.get("csrf_token")
        if csrf and "x-csrf-token" not in {k.lower() for k in headers}:
            headers["X-CSRF-Token"] = csrf
        return self.client.request(method, f"/api/v1{path}", headers=headers, **kwargs)

    def get(self, path: str, **kw: Any) -> Any:
        return self.request("GET", path, **kw)

    def post(self, path: str, **kw: Any) -> Any:
        return self.request("POST", path, **kw)

    def patch(self, path: str, **kw: Any) -> Any:
        return self.request("PATCH", path, **kw)

    def put(self, path: str, **kw: Any) -> Any:
        return self.request("PUT", path, **kw)

    def delete(self, path: str, **kw: Any) -> Any:
        return self.request("DELETE", path, **kw)


@pytest.fixture
def world(db: sessionmaker[Session]) -> dict[str, Any]:
    """Users for every role (+ a second doctor), one ward with one room and three beds."""
    ids: dict[str, Any] = {}
    with db() as s:
        for role, login in LOGINS.items():
            user = User(
                login=login,
                full_name=f"Тест {login}",
                role=role.value,
                password_hash=hash_password(PASSWORD),
            )
            s.add(user)
            s.flush()
            ids[login] = user.id
        other = User(
            login="doctor2",
            full_name="Тест doctor2",
            role=Role.DOCTOR.value,
            password_hash=hash_password(PASSWORD),
        )
        s.add(other)
        ward = Ward(name="Тестовое отделение")
        s.add(ward)
        s.flush()
        room = Room(ward_id=ward.id, name="Пал. 1", floor=1)
        s.add(room)
        s.flush()
        beds = [Bed(room_id=room.id, label=f"к. {n}") for n in (1, 2, 3)]
        s.add_all(beds)
        s.flush()
        ids["doctor2"] = other.id
        ids["beds"] = [b.id for b in beds]
        ids["room"] = room.id
        s.commit()
    return ids


def case_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "patient": {
            "full_name": "Иванов Алишер Дилшодович",
            "birth_date": date(1960, 5, 17).isoformat(),
            "sex": "M",
            "medical_record_number": "T-0001",
        },
        "procedure_key": "tka",
        "side": "left",
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def api(world: dict[str, Any]) -> Api:
    return Api()


@pytest.fixture
def case_id(api: Api, world: dict[str, Any]) -> uuid.UUID:
    """A TKA case treated by `doctor`, in bed 1."""
    api.as_role(Role.DOCTOR)
    resp = api.post("/cases", json=case_payload(bed_id=str(world["beds"][0])))
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["id"])


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class FakeTelegram:
    """Records outgoing messages instead of calling the Bot API."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.fail = False

    def send_message(self, chat_id: str, text: str) -> None:
        from app.services.telegram import TelegramError

        if self.fail:
            raise TelegramError("HTTP 500")
        self.sent.append((chat_id, text))


@pytest.fixture
def telegram_fake() -> Iterator[FakeTelegram]:
    from app.services import telegram

    fake = FakeTelegram()
    telegram.set_client_for_tests(fake)  # type: ignore[arg-type]
    yield fake
    telegram.set_client_for_tests(None)


def link_telegram(db: sessionmaker[Session], login: str, chat_id: str) -> None:
    from sqlalchemy import select

    with db() as s:
        user = s.scalars(select(User).where(User.login == login)).one()
        user.telegram_chat_id = chat_id
        s.commit()
