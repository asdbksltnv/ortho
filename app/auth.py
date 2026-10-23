import secrets
import threading
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.errors import ApiError, forbidden, unauthorized
from app.db import get_session
from app.domain.enums import Role
from app.domain.permissions import Perm, has_perm
from app.models.user import User
from app.settings import Settings, get_settings

ACCESS_COOKIE = "access_token"
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "x-csrf-token"
_JWT_ALG = "HS256"
_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}

_hasher = PasswordHasher()
# Verifying against this when the login is unknown keeps timing similar to a real check.
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def new_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def create_access_token(user_id: uuid.UUID, csrf: str, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "csrf": csrf,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.session_timeout_min)).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_JWT_ALG)


def decode_access_token(token: str, settings: Settings) -> dict[str, object] | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[_JWT_ALG])
    except jwt.PyJWTError:
        return None


def set_session_cookies(
    response: Response, user_id: uuid.UUID, csrf: str, settings: Settings
) -> None:
    max_age = settings.session_timeout_min * 60
    response.set_cookie(
        ACCESS_COOKIE,
        create_access_token(user_id, csrf, settings),
        max_age=max_age,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )
    # Readable by JS so the SPA can echo it in X-CSRF-Token; the signed copy is inside the JWT.
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=max_age,
        httponly=False,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


class LoginRateLimiter:
    """In-memory sliding window per (ip, login). Per-process: enough for a single-instance pilot."""

    def __init__(self) -> None:
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, window_s: float) -> deque[float]:
        bucket = self._failures[key]
        cutoff = time.monotonic() - window_s
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        return bucket

    def is_blocked(self, key: str, max_failures: int, window_s: float) -> bool:
        with self._lock:
            return len(self._prune(key, window_s)) >= max_failures

    def record_failure(self, key: str, window_s: float) -> None:
        with self._lock:
            self._prune(key, window_s).append(time.monotonic())

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._failures.clear()
            else:
                self._failures.pop(key, None)


rate_limiter = LoginRateLimiter()


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    login: str
    full_name: str
    role: Role


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def current_user(
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
) -> CurrentUser:
    settings = get_settings()
    token = request.cookies.get(ACCESS_COOKIE)
    claims = decode_access_token(token, settings) if token else None
    if claims is None:
        raise unauthorized()

    if request.method in _MUTATING:
        header = request.headers.get(CSRF_HEADER, "")
        if not header or not secrets.compare_digest(header, str(claims["csrf"])):
            raise ApiError(403, "csrf_failed", "Сессия устарела, обновите страницу")

    user = session.get(User, uuid.UUID(str(claims["sub"])))
    if user is None or not user.is_active:
        raise unauthorized()

    # Sliding expiry: auto-logout happens only after SESSION_TIMEOUT_MIN of inactivity.
    set_session_cookies(response, user.id, str(claims["csrf"]), settings)
    session.info["user_id"] = user.id
    return CurrentUser(user.id, user.login, user.full_name, Role(user.role))


def require_perm(perm: Perm) -> Callable[..., CurrentUser]:
    def dependency(user: Annotated[CurrentUser, Depends(current_user)]) -> CurrentUser:
        if not has_perm(user.role, perm):
            raise forbidden()
        return user

    return dependency
