from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from app.api.deps import ConfigDep, KpiReader, SessionDep, ip_of
from app.api.errors import ApiError
from app.domain.enums import AuditAction
from app.schemas.api import KpiOut
from app.services import audit, kpi
from app.services.clock import local_today

FromParam = Annotated[date | None, Query(alias="from")]
ToParam = Annotated[date | None, Query(alias="to")]

router = APIRouter(prefix="/kpi", tags=["kpi"])


def _period(start: date | None, end: date | None) -> tuple[date, date]:
    end = end or local_today()
    start = start or end - timedelta(days=89)
    if start > end:
        raise ApiError(422, "bad_period", "Начало периода позже конца")
    if (end - start).days > 730:
        raise ApiError(422, "bad_period", "Период не может быть длиннее двух лет")
    return start, end


@router.get("", response_model=KpiOut)
def get_kpi(
    _: KpiReader,
    session: SessionDep,
    config: ConfigDep,
    date_from: FromParam = None,
    date_to: ToParam = None,
) -> KpiOut:
    start, end = _period(date_from, date_to)
    return KpiOut.model_validate(
        kpi.compute_kpis(session, config, start, end), from_attributes=True
    )


@router.get("/export.csv")
def export_csv(
    request: Request,
    user: KpiReader,
    session: SessionDep,
    config: ConfigDep,
    date_from: FromParam = None,
    date_to: ToParam = None,
) -> Response:
    start, end = _period(date_from, date_to)
    body = kpi.to_csv(kpi.compute_kpis(session, config, start, end))
    audit.record(
        session,
        user_id=user.id,
        action=AuditAction.EXPORT,
        entity="kpi_csv",
        diff={"from": start.isoformat(), "to": end.isoformat()},
        ip=ip_of(request),
    )
    session.commit()
    return Response(
        body,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="kpi_{start}_{end}.csv"',
            "Cache-Control": "no-store",
        },
    )
