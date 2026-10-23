import csv
import io
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.enums import CaseStatus
from app.domain.kpi import (
    median_hours,
    most_frequent,
    was_not_ready_the_evening_before,
)
from app.models.case import Case, CaseStatusEvent
from app.models.ward import Bed
from app.services.cases import compute_case_readiness
from app.services.config_loader import AppConfig
from app.services.notify import case_label
from app.settings import get_settings

PROCEEDED = {
    CaseStatus.CALLED_TO_OR.value,
    CaseStatus.LEFT_WARD.value,
    CaseStatus.IN_OR.value,
    CaseStatus.RETURNED_TO_WARD.value,
    CaseStatus.TRANSFERRED_ICU.value,
    CaseStatus.POST_OP.value,
    CaseStatus.DISCHARGED.value,
}


@dataclass
class Kpis:
    period_from: date
    period_to: date
    cases_total: int = 0
    ready_cases: int = 0
    median_hours_to_ready: float | None = None
    blocking_items: list[dict[str, object]] = field(default_factory=list)
    overrides: list[dict[str, object]] = field(default_factory=list)
    not_ready_eve: list[dict[str, object]] = field(default_factory=list)
    surgeries_checked: int = 0


def compute_kpis(session: Session, config: AppConfig, start: date, end: date) -> Kpis:
    tz = ZoneInfo(get_settings().tz_display)
    lo = datetime.combine(start, time.min, tzinfo=tz).astimezone(UTC)
    hi = datetime.combine(end + timedelta(days=1), time.min, tzinfo=tz).astimezone(UTC)
    cases = list(
        session.scalars(
            select(Case)
            .where(Case.admitted_at >= lo, Case.admitted_at < hi)
            .options(
                selectinload(Case.checklist_items),
                selectinload(Case.patient),
                selectinload(Case.bed).selectinload(Bed.room),
            )
        )
    )
    kpis = Kpis(period_from=start, period_to=end, cases_total=len(cases))
    labels = {d.key: d.short_label_ru for d in config.checklist.items}

    deltas = [c.first_ready_at - c.admitted_at for c in cases if c.first_ready_at is not None]
    kpis.ready_cases = len(deltas)
    kpis.median_hours_to_ready = median_hours(deltas)

    blocking: list[str] = []
    for case in cases:
        if case.status == CaseStatus.DISCHARGED.value:
            continue
        readiness = compute_case_readiness(case, config)
        blocking.extend(readiness.blocking)
    kpis.blocking_items = [
        {"key": k, "label": labels.get(k, k), "count": n} for k, n in most_frequent(blocking)
    ]

    case_by_id = {c.id: c for c in cases}
    events = session.scalars(
        select(CaseStatusEvent)
        .where(CaseStatusEvent.is_override.is_(True), CaseStatusEvent.case_id.in_(case_by_id))
        .order_by(CaseStatusEvent.created_at.desc())
    )
    kpis.overrides = [
        {
            "at": e.created_at,
            "case_id": e.case_id,
            "case_label": case_label(case_by_id[e.case_id]),
            "reason": e.reason,
        }
        for e in events
    ]

    today = datetime.now(tz).date()
    for case in cases:
        planned = case.planned_surgery_date
        if planned is None or planned > today or case.is_emergency or case.status not in PROCEEDED:
            continue
        kpis.surgeries_checked += 1
        if was_not_ready_the_evening_before(case.first_ready_at, planned, tz):
            kpis.not_ready_eve.append(
                {"case_id": case.id, "case_label": case_label(case), "planned": planned}
            )
    return kpis


def to_csv(kpis: Kpis) -> str:
    """Aggregates only: no patient, bed or reason text."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["metric", "key", "value"])
    writer.writerow(["period_from", "", kpis.period_from.isoformat()])
    writer.writerow(["period_to", "", kpis.period_to.isoformat()])
    writer.writerow(["cases_total", "", kpis.cases_total])
    writer.writerow(["cases_reached_ready", "", kpis.ready_cases])
    writer.writerow(
        [
            "median_hours_admission_to_ready",
            "",
            "" if kpis.median_hours_to_ready is None else kpis.median_hours_to_ready,
        ]
    )
    writer.writerow(["overrides_count", "", len(kpis.overrides)])
    writer.writerow(["surgeries_checked", "", kpis.surgeries_checked])
    writer.writerow(["not_ready_evening_before_count", "", len(kpis.not_ready_eve)])
    for item in kpis.blocking_items:
        writer.writerow(["blocking_item_cases", item["key"], item["count"]])
    return out.getvalue()
