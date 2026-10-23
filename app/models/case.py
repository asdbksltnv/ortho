import uuid
from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, ForeignKey, String, Text, Time, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.domain.enums import CaseStatus, ItemStatus
from app.models.base import ClinicalMixin, JSONType, UTCDateTime, utcnow
from app.models.user import User
from app.models.ward import Bed


class Patient(Base, ClinicalMixin):
    __tablename__ = "patients"

    full_name: Mapped[str] = mapped_column(String(300))
    birth_date: Mapped[date] = mapped_column(Date)
    sex: Mapped[str] = mapped_column(String(1))  # M | F
    medical_record_number: Mapped[str] = mapped_column(String(64), index=True)


class Case(Base, ClinicalMixin):
    """One hospital stay with a planned procedure."""

    __tablename__ = "cases"

    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("patients.id"), index=True)
    bed_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("beds.id"), nullable=True)
    treating_doctor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    procedure_key: Mapped[str] = mapped_column(String(64))
    side: Mapped[str | None] = mapped_column(String(16), nullable=True)  # left | right | both
    planned_surgery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_surgery_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    anaesthesia_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    anaesthesia_remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=CaseStatus.ADMITTED.value, index=True)
    is_emergency: Mapped[bool] = mapped_column(Boolean, default=False)
    takes_anticoagulant: Mapped[bool] = mapped_column(Boolean, default=False)
    admitted_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    first_ready_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient: Mapped[Patient] = relationship()
    bed: Mapped[Bed | None] = relationship()
    treating_doctor: Mapped[User] = relationship(foreign_keys=[treating_doctor_id])
    checklist_items: Mapped[list["ChecklistItem"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )


class ChecklistItem(Base, ClinicalMixin):
    __tablename__ = "checklist_items"
    __table_args__ = (UniqueConstraint("case_id", "key", name="uq_checklist_case_key"),)

    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cases.id"), index=True)
    key: Mapped[str] = mapped_column(String(64))  # references config/checklist_items.yaml
    status: Mapped[str] = mapped_column(String(32), default=ItemStatus.NOT_STARTED.value)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    case: Mapped[Case] = relationship(back_populates="checklist_items")


class LabResult(Base, ClinicalMixin):
    __tablename__ = "lab_results"

    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cases.id"), index=True)
    lab_code: Mapped[str] = mapped_column(String(64))
    result_text: Mapped[str] = mapped_column(Text)
    collected_at: Mapped[datetime] = mapped_column(UTCDateTime)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)


class Consent(Base, ClinicalMixin):
    __tablename__ = "consents"

    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cases.id"), index=True)
    type: Mapped[str] = mapped_column(String(16))  # surgical | anaesthesia
    signed_at: Mapped[datetime] = mapped_column(UTCDateTime)
    recorded_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))


class CaseStatusEvent(Base, ClinicalMixin):
    __tablename__ = "case_status_events"

    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cases.id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_override: Mapped[bool] = mapped_column(Boolean, default=False)


class AuditLog(Base):
    """Append-only. No code path updates or deletes rows."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(16))
    entity: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    diff: Mapped[dict[str, object] | None] = mapped_column(JSONType, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)


class IntakeForm(Base, ClinicalMixin):
    """Bedside intake form; `data` follows app.domain.intake.IntakeData."""

    __tablename__ = "intake_forms"

    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("cases.id"), unique=True, index=True
    )
    schema_version: Mapped[int] = mapped_column(default=1)
    data: Mapped[dict[str, object]] = mapped_column(JSONType)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class GeneratedDocument(Base, ClinicalMixin):
    __tablename__ = "generated_documents"
    __table_args__ = (UniqueConstraint("case_id", "template_id", name="uq_document_case_template"),)

    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cases.id"), index=True)
    template_id: Mapped[str] = mapped_column(String(64))
    template_version: Mapped[int] = mapped_column(default=1)
    # list of rendered fields in EMR order; each has a "copied" flag
    fields: Mapped[list[dict[str, object]]] = mapped_column(JSONType)
    generated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    is_outdated: Mapped[bool] = mapped_column(Boolean, default=False)


class IdempotencyKey(Base):
    """Client-generated request ids so queued offline saves are applied at most once."""

    __tablename__ = "idempotency_keys"

    key: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cases.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
