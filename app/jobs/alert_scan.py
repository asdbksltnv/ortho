"""Re-checks the latest post-operative entries against the alert thresholds."""

import logging

from app.db import get_session_factory
from app.logging_config import configure_logging
from app.services.config_loader import get_config
from app.services.jobs import run_alert_scan

logger = logging.getLogger("jobs.alert_scan")


def main() -> None:
    configure_logging()
    with get_session_factory()() as session:
        count = run_alert_scan(session, get_config())
        session.commit()
    logger.info("alert_scan: %d notification(s) sent", count)


if __name__ == "__main__":
    main()
