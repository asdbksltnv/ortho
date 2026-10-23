import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Uuid, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, Session, mapped_column
from sqlalchemy.types import TypeDecorator

from app.db import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """Timezone-aware UTC datetimes on every backend (SQLite drops tzinfo)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("naive datetime is not allowed")
        return value.astimezone(UTC) if value is not None else None

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class IdMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class ClinicalMixin(IdMixin, TimestampMixin):
    """id + created_at/updated_at + created_by/updated_by on every clinical table."""

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )


def stamp_authorship(session: Session, flush_context: Any, instances: Any) -> None:
    # session.info['user_id'] is set by the auth dependency; fills created_by / updated_by.
    user_id = session.info.get("user_id")
    if user_id is None:
        return
    for obj in session.new:
        if isinstance(obj, ClinicalMixin):
            obj.created_by = obj.created_by or user_id
            obj.updated_by = user_id
    for obj in session.dirty:
        if isinstance(obj, ClinicalMixin) and session.is_modified(obj):
            obj.updated_by = user_id


event.listen(Session, "before_flush", stamp_authorship)

__all__ = ["Base", "ClinicalMixin", "IdMixin", "JSONType", "TimestampMixin", "UTCDateTime"]
