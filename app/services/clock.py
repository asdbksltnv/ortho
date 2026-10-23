from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.settings import get_settings


def local_today() -> date:
    """Today's date in the display time zone (Asia/Tashkent by default)."""
    return datetime.now(ZoneInfo(get_settings().tz_display)).date()
