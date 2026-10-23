"""Render pre-deploy step: apply migrations, then seed demo data (demo mode only, once)."""

from alembic import command
from alembic.config import Config

from app.seed import print_credentials, seed_if_empty
from app.settings import get_settings


def main() -> None:
    command.upgrade(Config("alembic.ini"), "head")
    if get_settings().demo_mode:
        credentials = seed_if_empty()
        if credentials:
            print_credentials(credentials)
        else:
            print("predeploy: demo data already present", flush=True)


if __name__ == "__main__":
    main()
