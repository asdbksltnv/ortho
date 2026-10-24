"""Schema of the bedside intake form (stored as JSONB, versioned).

Every field is optional so partial drafts can be autosaved. Picklist values are stored as the
Russian labels shown in the UI; they are not validated against the config so that editing a
picklist never invalidates saved forms. Numeric fields are typo guards only, not clinical limits.
"""

from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

SCHEMA_VERSION = 1

Text = Annotated[str, StringConstraints(max_length=2000, strip_whitespace=True)]
Short = Annotated[str, StringConstraints(max_length=200, strip_whitespace=True)]
BP = Annotated[str, StringConstraints(pattern=r"^\d{2,3}/\d{2,3}$")]
DetailKey = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{1,64}$")]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class History(_Model):
    onset_date: date | None = None
    mechanism: Text = ""
    duration: Short = ""
    prior_treatment: Text = ""
    course: Short | None = None
    hospitalization_count: Annotated[int, Field(ge=1, le=99)] | None = None


class Complaints(_Model):
    segment: Short | None = None  # key from defaults_ru.yaml segments
    pain_vas: Annotated[int, Field(ge=0, le=10)] | None = None
    limitation: bool = False
    deformity: bool = False
    swelling: bool = False
    weight_bearing: Short | None = None
    other: Text = ""
    # Answers to the location-specific questions (location_questions.yaml), keyed by question.
    details: dict[DetailKey, Short | list[Short]] = Field(default_factory=dict, max_length=40)


class Allergy(_Model):
    has: bool | None = None
    description: Text = ""


class PastItem(_Model):
    text: Short
    year: Annotated[int, Field(ge=1900, le=2100)] | None = None


class Past(_Model):
    denies: bool = False  # «Перенесённые операции и заболевания отрицает»
    items: list[PastItem] = Field(default_factory=list, max_length=50)
    epidemiological: list[Short] = Field(default_factory=list, max_length=20)
    epidemiological_other: Text = ""


class Medication(_Model):
    name: Short
    dose: Short = ""
    frequency: Short = ""
    is_anticoagulant: bool = False


class Social(_Model):
    alcohol: Short | None = None
    alcohol_amount: Short = ""
    tobacco: Short | None = None
    drugs: Short | None = None
    economic: Short | None = None
    physical_activity: Short | None = None


class Psycho(_Model):
    behavior: Short | None = None
    appearance: Short | None = None
    mood: Short | None = None
    emotions: Short | None = None
    understanding: Short | None = None
    criticism: Short | None = None


class Vitals(_Model):
    bp: BP | None = None
    pulse: Annotated[float, Field(ge=20, le=250)] | None = None
    hr: Annotated[float, Field(ge=20, le=250)] | None = None
    rr: Annotated[float, Field(ge=4, le=80)] | None = None
    spo2: Annotated[float, Field(ge=50, le=100)] | None = None
    temp: Annotated[float, Field(ge=30, le=45)] | None = None
    weight: Annotated[float, Field(ge=2, le=400)] | None = None
    height: Annotated[float, Field(ge=30, le=260)] | None = None


class General(_Model):
    severity: Short | None = None
    consciousness: Short | None = None
    position: Short | None = None


class SystemFinding(_Model):
    normal: bool | None = None  # True = the normal-finding sentence is accepted unchanged
    text: Text = ""  # used when normal is False


class Systems(_Model):
    skin: SystemFinding = Field(default_factory=SystemFinding)
    cvs: SystemFinding = Field(default_factory=SystemFinding)
    resp: SystemFinding = Field(default_factory=SystemFinding)
    msk: SystemFinding = Field(default_factory=SystemFinding)
    gu: SystemFinding = Field(default_factory=SystemFinding)
    gi: SystemFinding = Field(default_factory=SystemFinding)
    neuro: SystemFinding = Field(default_factory=SystemFinding)


class RomEntry(_Model):
    movement: Short
    degrees: Annotated[int, Field(ge=-90, le=360)]


class StabilityTest(_Model):
    test: Short
    result: Short


class Neurovascular(_Model):
    pulsation: Short | None = None
    sensation: Short | None = None
    motor: Short | None = None


class LocalStatus(_Model):
    segment: Short | None = None
    inspection: list[Short] = Field(default_factory=list, max_length=20)
    inspection_text: Text = ""
    palpation: Text = ""
    rom: list[RomEntry] = Field(default_factory=list, max_length=30)
    stability: list[StabilityTest] = Field(default_factory=list, max_length=30)
    neurovascular: Neurovascular = Field(default_factory=Neurovascular)
    other: Text = ""


class Columbia(_Model):
    q1: bool | None = None
    q2: bool | None = None
    q3: bool | None = None
    q4: bool | None = None
    q5: bool | None = None
    q6: bool | None = None
    q7: bool | None = None


class Nutrition(_Model):
    weight_loss: bool | None = None
    reduced_intake: bool | None = None
    stress_factor: bool | None = None


class CapriniInput(_Model):
    factors: list[Short] = Field(default_factory=list, max_length=60)


class IcdEntry(_Model):
    code: Short = ""
    text: Text = ""


class Diagnosis(_Model):
    main: IcdEntry = Field(default_factory=IcdEntry)
    competing: IcdEntry = Field(default_factory=IcdEntry)
    complication: IcdEntry = Field(default_factory=IcdEntry)
    background: IcdEntry = Field(default_factory=IcdEntry)
    comorbid: list[IcdEntry] = Field(default_factory=list, max_length=20)


class PlanMedication(_Model):
    name: Short
    note: Short = ""
    kind: Short = ""  # антибиотикопрофилактика | профилактика ВТЭ | обезболивание | другое


class Plan(_Model):
    checked: list[Short] = Field(default_factory=list, max_length=20)
    diet: Short = ""
    special_diet: Text = ""
    labs: list[Short] = Field(default_factory=list, max_length=60)
    instrumental: list[Short] = Field(default_factory=list, max_length=60)
    consults: list[Short] = Field(default_factory=list, max_length=30)
    medications: list[PlanMedication] = Field(default_factory=list, max_length=60)
    recommendations: Text = ""


class Preop(_Model):
    """Extra inputs for the pre-operative epicrisis (T3)."""

    economic_assessment: Short | None = None
    social_needs: Short | None = None
    psychological_needs: Short | None = None
    discharge_needs: list[Short] = Field(default_factory=list, max_length=20)
    vitals: Vitals = Field(default_factory=Vitals)  # fresh measurement, required for T3
    general_condition: Text = ""  # replaces the T1 text when the condition changed
    local_status: Text = ""  # replaces the T1 text when the status changed
    imaging: Text = ""
    failed_conservative: Text = ""


class IntakeData(_Model):
    history: History = Field(default_factory=History)
    complaints: Complaints = Field(default_factory=Complaints)
    allergy: Allergy = Field(default_factory=Allergy)
    past: Past = Field(default_factory=Past)
    medications: list[Medication] = Field(default_factory=list, max_length=60)
    medications_none: bool = False  # «Постоянно лекарственные препараты не принимает»
    social: Social = Field(default_factory=Social)
    psycho: Psycho = Field(default_factory=Psycho)
    vitals: Vitals = Field(default_factory=Vitals)
    general: General = Field(default_factory=General)
    systems: Systems = Field(default_factory=Systems)
    local_status: LocalStatus = Field(default_factory=LocalStatus)
    columbia: Columbia = Field(default_factory=Columbia)
    nutrition: Nutrition = Field(default_factory=Nutrition)
    caprini: CapriniInput = Field(default_factory=CapriniInput)
    diagnosis: Diagnosis = Field(default_factory=Diagnosis)
    plan: Plan = Field(default_factory=Plan)
    preop: Preop = Field(default_factory=Preop)

    @property
    def takes_anticoagulant(self) -> bool:
        return any(m.is_anticoagulant for m in self.medications)


def valid_path_roots() -> set[str]:
    return set(IntakeData.model_fields)


from app.domain.postop import PostOpData  # noqa: E402

VIRTUAL_ROOTS: dict[str, type[BaseModel]] = {"latest_vitals": Vitals, "postop": PostOpData}


def path_exists(path: str) -> bool:
    """Whether a dotted path points at a field of the intake schema (or a virtual root)."""
    root, *rest = path.split(".")
    model: type[BaseModel] | None = VIRTUAL_ROOTS.get(root) or (
        IntakeData if root == "__root__" else None
    )
    if model is None:
        if root not in IntakeData.model_fields:
            return False
        annotation = IntakeData.model_fields[root].annotation
        if not rest:
            return True
        model = (
            annotation
            if isinstance(annotation, type) and issubclass(annotation, BaseModel)
            else None
        )
    for index, part in enumerate(rest):
        if model is None or part not in model.model_fields:
            return False
        annotation = model.model_fields[part].annotation
        model = (
            annotation
            if isinstance(annotation, type) and issubclass(annotation, BaseModel)
            else None
        )
        if model is None and index < len(rest) - 1:
            return False
    return True
