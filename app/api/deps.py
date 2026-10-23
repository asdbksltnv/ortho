from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.auth import CurrentUser, client_ip, current_user, require_perm
from app.db import get_session
from app.domain.permissions import Perm
from app.services.config_loader import AppConfig, get_config

SessionDep = Annotated[Session, Depends(get_session)]
UserDep = Annotated[CurrentUser, Depends(current_user)]
ConfigDep = Annotated[AppConfig, Depends(get_config)]


def ip_of(request: Request) -> str | None:
    return client_ip(request)


CaseReader = Annotated[CurrentUser, Depends(require_perm(Perm.CASE_READ))]
CaseCreator = Annotated[CurrentUser, Depends(require_perm(Perm.CASE_CREATE))]
CaseEditor = Annotated[CurrentUser, Depends(require_perm(Perm.CASE_EDIT))]
LabsWriter = Annotated[CurrentUser, Depends(require_perm(Perm.LABS_WRITE))]
ConsentWriter = Annotated[CurrentUser, Depends(require_perm(Perm.CONSENT_WRITE))]
UsersAdmin = Annotated[CurrentUser, Depends(require_perm(Perm.USERS_MANAGE))]
WardsAdmin = Annotated[CurrentUser, Depends(require_perm(Perm.WARDS_MANAGE))]
AuditReader = Annotated[CurrentUser, Depends(require_perm(Perm.AUDIT_READ))]
KpiReader = Annotated[CurrentUser, Depends(require_perm(Perm.KPI_READ))]
