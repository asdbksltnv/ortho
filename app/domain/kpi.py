"""Pure helpers for the KPI page (head of department / head nurse)."""

from collections import Counter
from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta
from statistics import median
from zoneinfo import ZoneInfo

EVE_HOUR = 18  # «the evening before surgery» = 18:00 local time on the previous day


def median_hours(deltas: Iterable[timedelta]) -> float | None:
    hours = [d.total_seconds() / 3600 for d in deltas if d.total_seconds() >= 0]
    return round(median(hours), 1) if hours else None


def eve_cutoff(planned: date, tz: ZoneInfo) -> datetime:
    """18:00 local on the day before surgery, as an aware UTC instant."""
    local = datetime.combine(planned - timedelta(days=1), time(EVE_HOUR), tzinfo=tz)
    return local.astimezone(UTC)


def was_not_ready_the_evening_before(
    first_ready_at: datetime | None, planned: date, tz: ZoneInfo
) -> bool:
    """Not Ready by the cutoff: never became Ready, or only after it."""
    return first_ready_at is None or first_ready_at > eve_cutoff(planned, tz)


def most_frequent(keys: Iterable[str]) -> list[tuple[str, int]]:
    """Most common first; ties keep a stable (alphabetical) order."""
    counted = Counter(keys)
    return sorted(counted.items(), key=lambda kv: (-kv[1], kv[0]))
