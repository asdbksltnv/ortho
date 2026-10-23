import uuid

from sqlalchemy.orm import Session

from app.domain.enums import AuditAction
from app.models.case import AuditLog


def record(
    session: Session,
    *,
    user_id: uuid.UUID | None,
    action: AuditAction,
    entity: str,
    entity_id: uuid.UUID | None = None,
    diff: dict[str, object] | None = None,
    ip: str | None = None,
) -> None:
    """Append an audit row. `diff` must never hold free-text clinical content or identifiers."""
    session.add(
        AuditLog(
            user_id=user_id,
            action=action.value,
            entity=entity,
            entity_id=entity_id,
            diff=diff,
            ip=ip,
        )
    )
