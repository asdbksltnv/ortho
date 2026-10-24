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


class LocationQuestion(_Strict):
    key: str = Field(pattern=r"^[a-z0-9_]{1,64}$")
    label_ru: str
    multi: bool = False
    options: list[str] = Field(min_length=1)


class LocationMovement(_Strict):
    name_ru: str
    rom_normal: int | None = None  # reference value in degrees, shown as a hint only


class LocationSpec(_Strict):
    questions: list[LocationQuestion] = Field(default_factory=list)
    movements: list[LocationMovement] = Field(default_factory=list)
    tests: list[str] = Field(default_factory=list)


class LocationQuestionsConfig(ConfigMeta):
    common: list[LocationQuestion]
    shared: list[LocationQuestion] = Field(default_factory=list)  # YAML anchors only
    locations: dict[str, LocationSpec]

    def questions_for(self, segment: str | None) -> list[LocationQuestion]:
        """Common questions first, then the ones for the segment (none without a segment)."""
        if not segment:
            return []
        spec = self.locations.get(segment)
        return [*self.common, *(spec.questions if spec else [])]


_SOURCE = re.compile(
    r"^(form|generated|board|schedule|staff|skip|case|procedure|note|copy:[a-z0-9_]+\.[a-z0-9_]+)$"
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
    scope: str = "case"  # case | postop_entry
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
            scope=self.scope,
        )


class AlertThresholdsInner(_Strict):
    temperature_max: float | None = None
    drain_output_ml_max: int | None = None
    pain_vas_max: int | None = None
    purulent_discharge: bool | None = None


class AlertThresholdsConfig(ConfigMeta):
    thresholds: AlertThresholdsInner


class AntibioticConfig(ConfigMeta):
    """Empty until the department supplies its protocol; the `antibiotic` item stays manual."""

    drugs: list[dict[str, Any]] = Field(default_factory=list)


class OrderTemplate(_Strict):
    type: str
    item: str


class OrderSet(_Strict):
    key: str
    name_ru: str
    orders: list[OrderTemplate]


class OrderSetsConfig(ConfigMeta):
    sets: list[OrderSet]
