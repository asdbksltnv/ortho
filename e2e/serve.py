"""Starts OrthoReady for the Playwright run: fresh SQLite database, demo seed, known passwords.

Test-only: the seeded users get a fixed password so the browser tests can log in.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

PASSWORD = "E2e!Passw0rd12"
PORT = int(os.environ.get("E2E_PORT", "8099"))
DB = ROOT / "e2e" / ".tmp" / f"e2e-{PORT}.db"
DB.parent.mkdir(exist_ok=True)
DB.unlink(missing_ok=True)

os.environ.update(
    DATABASE_URL=f"sqlite+pysqlite:///{DB}",
    DEMO_MODE="true",
    ENV="development",
    SECRET_KEY="e2e-secret-key-that-is-long-enough-1234567890",
    COOKIE_SECURE="false",
    FRONTEND_DIST=str(ROOT / "frontend" / "dist"),
    LOG_LEVEL="WARNING",
)

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.auth import hash_password  # noqa: E402
from app.db import get_session_factory  # noqa: E402
from app.models.user import User  # noqa: E402
from app.seed import seed_extra_cases, seed_if_empty  # noqa: E402
from app.services.config_loader import get_config  # noqa: E402

command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
seed_if_empty()
with get_session_factory()() as session:
    if int(os.environ.get("E2E_CASES", "0")):
        seed_extra_cases(session, get_config(), int(os.environ["E2E_CASES"]))
        session.commit()
    for user in session.scalars(select(User)):
        user.password_hash = hash_password(PASSWORD)
    session.commit()

import uvicorn  # noqa: E402

uvicorn.run(
    "app.main:app",
    host="127.0.0.1",
    port=PORT,
    log_level="warning",
)
