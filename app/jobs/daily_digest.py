"""18:00 Asia/Tashkent digest of tomorrow's cases that are not Ready."""

import logging

from app.db import get_session_factory
from app.logging_config import configure_logging
from app.services.clock import local_today
from app.services.config_loader import get_config
from app.services.jobs import run_daily_digest

logger = logging.getLogger("jobs.daily_digest")


def main() -> None:
    configure_logging()
    with get_session_factory()() as session:
        count = run_daily_digest(session, get_config(), local_today())
        session.commit()
    logger.info("daily_digest: %d notification(s) sent", count)


if __name__ == "__main__":
    main()
