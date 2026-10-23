"""Production start-up: no demo data, a first administrator, and retired demo accounts.

Runs from `python -m app.predeploy` when DEMO_MODE=false, so a deployment without shell access
(e.g. Render free/starter) can still be set up from environment variables alone.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.domain.enums import CaseStatus, Role
from app.models.case import Case, Patient
from app.models.user import User
from app.seed import DEMO_USERS
from app.settings import Settings

MIN_PASSWORD_LENGTH = 10
DEMO_RECORD_PREFIXES = ("DEMO-", "LOAD-")


def retire_demo_data(session: Session) -> tuple[int, int]:
    """Deactivates the seeded demo users and takes demo cases off the board.

    Nothing is deleted (audit rows still reference these users). Returns (users, cases) changed.
    """
    demo_logins = {login for login, _, _ in DEMO_USERS}
    users = [
        u
        for u in session.scalars(select(User).where(User.login.in_(demo_logins)))
        if u.is_active and u.full_name.startswith("Демо")
    ]
    for user in users:
        user.is_active = False
    cases = [
        c
        for c in session.scalars(
            select(Case)
            .join(Patient, Patient.id == Case.patient_id)
            .where(Case.status != CaseStatus.DISCHARGED.value)
        )
        if c.patient.medical_record_number.startswith(DEMO_RECORD_PREFIXES)
    ]
    for case in cases:
        case.status = CaseStatus.DISCHARGED.value
    session.flush()
    return len(users), len(cases)


def has_real_admin(session: Session) -> bool:
    demo_logins = {login for login, _, _ in DEMO_USERS}
    return any(
        u.is_active and u.login not in demo_logins
        for u in session.scalars(select(User).where(User.role == Role.ADMIN.value))
    )


def ensure_first_admin(session: Session, settings: Settings) -> str:
    """Creates the first administrator from ADMIN_LOGIN / ADMIN_PASSWORD when no active real
    admin exists. Never changes the password of an existing account. Returns a status message
    (it never contains the password)."""
    if has_real_admin(session):
        return "an administrator already exists; ADMIN_PASSWORD is ignored"
    if not settings.admin_password:
        return (
            "NO ADMINISTRATOR EXISTS and ADMIN_PASSWORD is not set: nobody can log in. "
            "Set ADMIN_PASSWORD (and optionally ADMIN_LOGIN) and redeploy."
        )
    if len(settings.admin_password) < MIN_PASSWORD_LENGTH:
        return f"ADMIN_PASSWORD must be at least {MIN_PASSWORD_LENGTH} characters; no admin created"
    if session.scalars(select(User).where(User.login == settings.admin_login)).first():
        return (
            f"login {settings.admin_login!r} is taken by a non-admin account; "
            "choose another ADMIN_LOGIN"
        )
    session.add(
        User(
            login=settings.admin_login,
            full_name=settings.admin_full_name,
            role=Role.ADMIN.value,
            password_hash=hash_password(settings.admin_password),
        )
    )
    session.flush()
    return f"administrator {settings.admin_login!r} created"
