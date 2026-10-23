"""Flags lab results that expire before the planned surgery date."""

import logging

from app.db import get_session_factory
from app.logging_config import configure_logging
from app.services.config_loader import get_config
from app.services.jobs import run_lab_expiry

logger = logging.getLogger("jobs.lab_expiry")


def main() -> None:
    configure_logging()
    with get_session_factory()() as session:
        count = run_lab_expiry(session, get_config())
        session.commit()
    logger.info("lab_expiry: %d notification(s) sent", count)


if __name__ == "__main__":
    main()
