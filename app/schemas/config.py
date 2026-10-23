"""Pydantic models for everything under config/. Validated at startup (fail fast)."""

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.emr import EmrType, FieldSpec, TemplateSpec
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
    """Pre-fill for the intake form; keys follow app.domain.intake.IntakeData."""

    complaints: dict[str, Any] = Field(default_factory=dict)
    local_status: dict[str, Any] = Field(default_factory=dict)
    plan: dict[str, Any] = Field(default_factory=dict)


class ProcedureTemplate(ConfigMeta):
    id: str
    label_ru: str
    operation_name_ru: str
    blocking_items: list[str] = Field(default_factory=list)
    optional_labs: list[str] = Field(default_factory=list)
    instrumental: list[str] = Field(default_factory=list)
    main_diagnosis: MainDiagnosis = Field(default_factory=MainDiagnosis)
    defaults: ProcedureDefaults = Field(default_factory=ProcedureDefaults)
    caprini_defaults: list[str] = Field(default_factory=list)
    surgery_texts: SurgeryTexts = Field(default_factory=SurgeryTexts)


class CapriniAuto(_Strict):
    type: str
    min: int | None = None
    max: int | None = None
    value: float | None = None


class CapriniFactor(_Strict):
    key: str
    points: int
    label_ru: str
    auto: CapriniAuto | None = None


class CapriniCategory(_Strict):
    key: str
    label_ru: str
    min: int
    max: int | None


class CapriniConfig(ConfigMeta):
    model: str
    factors: list[CapriniFactor]
    risk_categories: list[CapriniCategory]


class ColumbiaQuestion(_Strict):
    n: int
    text_ru: str | None = None


class UrgentRuleConfig(_Strict):
    all_yes: list[int] = Field(default_factory=list)
    any_yes: list[int] = Field(default_factory=list)
    rule_text_ru: str | None = None


class ColumbiaConfig(ConfigMeta):
    questions: list[ColumbiaQuestion]
    always_ask: list[int]
    follow_up: list[int]
    follow_up_trigger: list[int]
    urgent_consult_rule: UrgentRuleConfig


class NutritionQuestion(_Strict):
    key: str
    label_ru: str
    auto: bool = False


class NutritionConfig(ConfigMeta):
    bmi_threshold: float
    questions: list[NutritionQuestion]
    total_rule: str


class DietsConfig(ConfigMeta):
    diets: list[str]
    default: str | None = None


class SystemDefault(_Strict):
    label_ru: str
    normal_ru: str | None = None


class PsychoDefault(_Strict):
    label_ru: str
    default_ru: str


class Segment(_Strict):
    key: str
    name_ru: str
    gen_ru: str


class DefaultsConfig(ConfigMeta):
    systems: dict[str, SystemDefault]
    psycho: dict[str, PsychoDefault]
    segments: list[Segment]
    picklists: dict[str, list[str]]


_SOURCE = re.compile(
    r"^(form|generated|board|schedule|staff|skip|case|procedure|copy:[a-z0-9_]+\.[a-z0-9_]+)$"
)


class EmrFieldConfig(_Strict):
    key: str
    section: str
    label: str
    emr_type: EmrType
    critical: bool = False
    source: str = "form"
    generator: str | None = None
    path: str | None = None
    fallback_path: str | None = None
    override_path: str | None = None
    format: str | None = None
    emr_prefill: bool = False
    keep_if_empty: bool = False
    default_ru: str | None = None
    staff: str | None = None
    hint: str | None = None
    required: bool = False
    only_if: str | None = None

    @field_validator("source")
    @classmethod
    def _source_ok(cls, value: str) -> str:
        if not _SOURCE.match(value):
            raise ValueError(f"unsupported source {value!r}")
        return value

    def to_spec(self) -> FieldSpec:
        return FieldSpec(**self.model_dump())


class EmrTemplateConfig(ConfigMeta):
    id: str
    title_ru: str
    status: str = "ready"  # ready | awaiting_template
    fields: list[EmrFieldConfig] = Field(default_factory=list)
    gating_items: list[str] = Field(default_factory=list)

    def to_spec(self) -> TemplateSpec:
        return TemplateSpec(
            id=self.id,
            title_ru=self.title_ru,
            version=self.version,
            status=self.status,
            fields=tuple(f.to_spec() for f in self.fields),
            gating_items=tuple(self.gating_items),
        )
