"""Pre-deploy step: apply migrations, then seed demo data (DEMO_MODE) or bootstrap production."""

from alembic import command
from alembic.config import Config

from app.bootstrap import ensure_first_admin, has_real_admin, retire_demo_data
from app.db import get_session_factory
from app.floorplan import apply_plan, load_plan
from app.seed import apply_demo_password, print_credentials, seed_if_empty
from app.settings import get_settings


def main() -> None:
    command.upgrade(Config("alembic.ini"), "head")
    settings = get_settings()
    with get_session_factory()() as session:
        _, rooms, beds = apply_plan(session, load_plan())
        session.commit()
    if rooms or beds:
        print(f"predeploy: floor plan added {rooms} room(s) and {beds} bed(s)", flush=True)
    if settings.demo_mode:
        credentials = seed_if_empty()
        if credentials:
            print_credentials(credentials)
        else:
            print("predeploy: demo data already present", flush=True)
        if settings.demo_password and apply_demo_password(settings.demo_password):
            print("predeploy: demo users now use the password from DEMO_PASSWORD", flush=True)

    else:
        with get_session_factory()() as session:
            message = ensure_first_admin(session, settings)
            # Demo accounts are switched off only once a real administrator exists, so a missing
            # ADMIN_PASSWORD can never lock everyone out.
            users, cases = retire_demo_data(session) if has_real_admin(session) else (0, 0)
            session.commit()
        if users or cases:
            print(f"predeploy: retired {users} demo user(s) and {cases} demo case(s)", flush=True)
        print(f"predeploy: {message}", flush=True)


if __name__ == "__main__":
    main()
