"""Flags lab results that expire before the planned surgery date. Implemented in Phase 3."""

import logging

from app.logging_config import configure_logging

logger = logging.getLogger("jobs.lab_expiry")


def main() -> None:
    configure_logging()
    logger.info("lab_expiry: not implemented yet (Phase 3)")


if __name__ == "__main__":
    main()
