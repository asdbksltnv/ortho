import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.domain.enums import CaseStatus, ConsentType, ItemStatus, Role


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- auth / users ----
class LoginIn(BaseModel):
    login: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(min_length=10, max_length=256)


class UserOut(ORMModel):
    id: uuid.UUID
    login: str
    full_name: str
    role: Role
    is_active: bool


class StaffOut(ORMModel):
    id: uuid.UUID
    full_name: str
    role: Role


class UserCreate(BaseModel):
    login: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9._-]+$")
    full_name: str = Field(min_length=2, max_length=200)
    role: Role
    password: str = Field(min_length=10, max_length=256)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    role: Role | None = None
    is_active: bool | None = None


class PasswordReset(BaseModel):
    password: str = Field(min_length=10, max_length=256)


# ---- wards ----
class BedOut(ORMModel):
    id: uuid.UUID
    label: str
    is_active: bool


class RoomOut(ORMModel):
    id: uuid.UUID
    name: str
    floor: int
    position_x: int | None
    position_y: int | None
    beds: list[BedOut]


class WardOut(ORMModel):
    id: uuid.UUID
    name: str
    rooms: list[RoomOut]


class WardCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class RoomCreate(BaseModel):
    ward_id: uuid.UUID
    name: str = Field(min_length=1, max_length=100)
    floor: int = 1
    position_x: int | None = None
    position_y: int | None = None


class RoomUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    floor: int | None = None
    position_x: int | None = None
    position_y: int | None = None


class BedCreate(BaseModel):
    room_id: uuid.UUID
    label: str = Field(min_length=1, max_length=50)


class BedUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=50)
    is_active: bool | None = None


# ---- cases ----
Side = Literal["left", "right", "both"]


class PatientIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=300)
    birth_date: date
    sex: Literal["M", "F"]
    medical_record_number: str = Field(min_length=1, max_length=64)


class CaseCreate(BaseModel):
    patient: PatientIn
    procedure_key: str
    side: Side | None = None
    bed_id: uuid.UUID | None = None
    treating_doctor_id: uuid.UUID | None = None
    planned_surgery_date: date | None = None
    is_emergency: bool = False


class CaseUpdate(BaseModel):
    procedure_key: str | None = None
    side: Side | None = None
    bed_id: uuid.UUID | None = None
    treating_doctor_id: uuid.UUID | None = None
    planned_surgery_date: date | None = None
    is_emergency: bool | None = None
    takes_anticoagulant: bool | None = None


class ChecklistUpdate(BaseModel):
    status: ItemStatus
    note: str | None = Field(default=None, max_length=1000)
    # Optimistic concurrency: the item's updated_at as the client last saw it.
    expected_updated_at: AwareDatetime | None = None


class ItemOut(BaseModel):
    key: str
    status: ItemStatus
    note: str | None
    updated_at: datetime
    updated_by: str | None


class ReadinessOut(BaseModel):
    ready: bool
    blocking: list[str]


class PatientOut(ORMModel):
    full_name: str
    birth_date: date
    sex: str
    medical_record_number: str


class CaseOut(BaseModel):
    id: uuid.UUID
    status: CaseStatus
    patient: PatientOut
    bed_id: uuid.UUID | None
    room_name: str | None
    bed_label: str | None
    treating_doctor: StaffOut
    procedure_key: str
    procedure_label: str
    side: str | None
    planned_surgery_date: date | None
    is_emergency: bool
    takes_anticoagulant: bool
    admitted_at: datetime
    override_reason: str | None
    items: list[ItemOut]
    readiness: ReadinessOut
    can_edit: bool


class LabResultCreate(BaseModel):
    lab_code: str = Field(max_length=64)
    result_text: str = Field(min_length=1, max_length=2000)
    collected_at: AwareDatetime


class LabResultOut(ORMModel):
    id: uuid.UUID
    lab_code: str
    result_text: str
    collected_at: datetime
    valid_until: date | None


class ConsentCreate(BaseModel):
    type: ConsentType
    signed_at: AwareDatetime


class ConsentOut(ORMModel):
    id: uuid.UUID
    type: str
    signed_at: datetime


# ---- board ----
class BoardItem(BaseModel):
    status: ItemStatus
    note: str | None
    updated_at: datetime
    updated_by: str | None


class BoardRow(BaseModel):
    case_id: uuid.UUID
    bed_id: uuid.UUID | None
    initials: str
    room_id: uuid.UUID | None
    room_name: str | None
    bed_label: str | None
    status: CaseStatus
    procedure_label: str
    planned_surgery_date: date | None
    is_emergency: bool
    treating_doctor_id: uuid.UUID
    treating_doctor_name: str
    ready: bool
    blocking: list[str]
    override_reason: str | None
    items: dict[str, BoardItem]


class ColumnDef(BaseModel):
    key: str
    label_ru: str
    short_label_ru: str
    owner_role: Role


class BoardOut(BaseModel):
    columns: list[ColumnDef]
    rows: list[BoardRow]
    generated_at: datetime


# ---- audit / config ----
class AuditOut(ORMModel):
    id: uuid.UUID
    created_at: datetime
    user_id: uuid.UUID | None
    action: str
    entity: str
    entity_id: uuid.UUID | None
    diff: dict[str, object] | None
    ip: str | None


class AuditPage(BaseModel):
    items: list[AuditOut]
    next_cursor: str | None


class ConfigFileOut(BaseModel):
    name: str
    version: int
    requires_clinical_validation: bool


class ProcedureOut(BaseModel):
    id: str
    label_ru: str


class DefinitionsOut(BaseModel):
    checklist: list[ColumnDef]
    procedures: list[ProcedureOut]
