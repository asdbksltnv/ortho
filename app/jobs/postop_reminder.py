"""Reminds doctors when a post-operative case has no entry today (default 12:00)."""

import logging

from app.db import get_session_factory
from app.logging_config import configure_logging
from app.services.clock import local_today
from app.services.jobs import run_postop_reminder

logger = logging.getLogger("jobs.postop_reminder")


def main() -> None:
    configure_logging()
    with get_session_factory()() as session:
        count = run_postop_reminder(session, local_today())
        session.commit()
    logger.info("postop_reminder: %d notification(s) sent", count)


if __name__ == "__main__":
    main()
