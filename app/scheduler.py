"""In-process scheduler for development (SCHEDULER_ENABLED=true). Production uses cron jobs."""

import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

from app.jobs import alert_scan, daily_digest, lab_expiry, postop_reminder
from app.settings import get_settings

logger = logging.getLogger("scheduler")


def _hm(value: str) -> tuple[int, int]:
    hour, minute = value.split(":")
    return int(hour), int(minute)


def start_scheduler() -> BackgroundScheduler:
    settings = get_settings()
    scheduler = BackgroundScheduler(timezone=ZoneInfo(settings.tz_display))
    hour, minute = _hm(settings.digest_time)
    scheduler.add_job(daily_digest.main, "cron", hour=hour, minute=minute, id="daily_digest")
    scheduler.add_job(lab_expiry.main, "cron", hour=2, minute=0, id="lab_expiry")
    hour, minute = _hm(settings.postop_reminder_time)
    scheduler.add_job(postop_reminder.main, "cron", hour=hour, minute=minute, id="postop_reminder")
    scheduler.add_job(alert_scan.main, "interval", minutes=30, id="alert_scan")
    scheduler.start()
    logger.info("scheduler started")
    return scheduler
