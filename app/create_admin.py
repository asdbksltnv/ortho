"""Creates the first administrator on a fresh (non-demo) installation.

    python -m app.create_admin --login admin --full-name "Администратор"

The password is read from ADMIN_PASSWORD or prompted; it is never printed.
"""

import argparse
import getpass
import os
import sys

from sqlalchemy import select

from app.auth import hash_password
from app.db import get_session_factory
from app.domain.enums import Role
from app.models.user import User

MIN_PASSWORD_LENGTH = 10


def create_admin(login: str, full_name: str, password: str) -> bool:
    """Returns False when the login already exists."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    with get_session_factory()() as session:
        if session.scalars(select(User).where(User.login == login)).first():
            return False
        session.add(
            User(
                login=login,
                full_name=full_name,
                role=Role.ADMIN.value,
                password_hash=hash_password(password),
            )
        )
        session.commit()
        return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the first administrator")
    parser.add_argument("--login", required=True)
    parser.add_argument("--full-name", required=True)
    args = parser.parse_args()
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password: ")
    try:
        created = create_admin(args.login, args.full_name, password)
    except ValueError as exc:
        sys.exit(str(exc))
    print("created" if created else "login already exists; nothing changed")


if __name__ == "__main__":
    main()
