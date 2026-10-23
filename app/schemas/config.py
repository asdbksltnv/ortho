"""Pydantic models for everything under config/. Validated at startup (fail fast)."""

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import Blocking, Role


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConfigMeta(_Strict):
    version: int
    requires_clinical_validation: bool = True


class ChecklistItemDefinition(_Strict):
    key: str
    label_ru: str
    short_label_ru: str
    owner_role: Role
    blocking: Blocking
    auto_applies_flag: str | None = None


class ChecklistConfig(ConfigMeta):
    items: list[ChecklistItemDefinition]


class LabDefinition(_Strict):
    code: str
    name_ru: str
    group: str  # core | optional
    validity_days: int | None = None


class LabsConfig(ConfigMeta):
    labs: list[LabDefinition]


class MainDiagnosis(_Strict):
    icd10: str | None = None
    text_ru: str | None = None


class SurgeryTexts(_Strict):
    risks: str | None = None
    tactics: str | None = None
    technical_difficulties: str | None = None
    likely_complications: str | None = None
    prevention: str | None = None
    expected_blood_loss: str | None = None


class ProcedureDefaults(_Strict):
    complaints: dict[str, str | None] = Field(default_factory=dict)
    local_status: dict[str, str | None] = Field(default_factory=dict)
    plan: dict[str, str | None] = Field(default_factory=dict)


class ProcedureTemplate(ConfigMeta):
    id: str
    label_ru: str
    operation_name_ru: str
    blocking_items: list[str] = Field(default_factory=list)
    optional_labs: list[str] = Field(default_factory=list)
    instrumental: list[str] = Field(default_factory=list)
    main_diagnosis: MainDiagnosis = Field(default_factory=MainDiagnosis)
    defaults: ProcedureDefaults = Field(default_factory=ProcedureDefaults)
    surgery_texts: SurgeryTexts = Field(default_factory=SurgeryTexts)
