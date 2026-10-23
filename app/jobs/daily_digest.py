"""18:00 Asia/Tashkent digest of tomorrow's cases that are not Ready. Implemented in Phase 3."""

import logging

from app.logging_config import configure_logging

logger = logging.getLogger("jobs.daily_digest")


def main() -> None:
    configure_logging()
    logger.info("daily_digest: not implemented yet (Phase 3)")


if __name__ == "__main__":
    main()
