"""Daily post-operative monitoring: the bedside form schema, post-op day and threshold alerts."""

from dataclasses import dataclass
from datetime import date
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Text = Annotated[str, StringConstraints(max_length=2000, strip_whitespace=True)]
Short = Annotated[str, StringConstraints(max_length=200, strip_whitespace=True)]
BP = Annotated[str, StringConstraints(pattern=r"^\d{2,3}/\d{2,3}$")]

PURULENT = "гнойное"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PostOpVitals(_Model):
    bp: BP | None = None
    pulse: Annotated[float, Field(ge=20, le=250)] | None = None
    rr: Annotated[float, Field(ge=4, le=80)] | None = None
    spo2: Annotated[float, Field(ge=50, le=100)] | None = None
    temp: Annotated[float, Field(ge=30, le=45)] | None = None
    cvp: Annotated[float, Field(ge=-20, le=60)] | None = None  # optional


class Wound(_Model):
    dressing: Short | None = None  # сухая | промокла
    discharge: Short | None = None  # нет | серозное | геморрагическое | гнойное
    redness: bool = False
    swelling: bool = False
    sutures: Short | None = None
    dressing_changed: bool = False


class Drain(_Model):
    present: bool = False
    output_ml: Annotated[int, Field(ge=0, le=5000)] | None = None
    removed: bool = False


class Neurovascular(_Model):
    pulsation: Short | None = None
    sensation: Short | None = None
    motor: Short | None = None


class Mobilization(_Model):
    level: Short | None = None
    weight_bearing: Short | None = None
    physiotherapy: bool = False


class Therapy(_Model):
    antibiotic_day: Annotated[int, Field(ge=1, le=60)] | None = None
    vte_prophylaxis: bool = False
    analgesia: Short = ""


class PostOpData(_Model):
    complaints: Text = ""  # free text: used by the template generator, never sent to an LLM
    pain_vas: Annotated[int, Field(ge=0, le=10)] | None = None
    consciousness: Short | None = None
    vitals: PostOpVitals = Field(default_factory=PostOpVitals)
    wound: Wound = Field(default_factory=Wound)
    drain: Drain = Field(default_factory=Drain)
    neurovascular: Neurovascular = Field(default_factory=Neurovascular)
    calf_tenderness: bool = False
    mobilization: Mobilization = Field(default_factory=Mobilization)
    therapy: Therapy = Field(default_factory=Therapy)
    recommendations: Text = ""
    photo_key: str | None = None  # set by the photo upload endpoint, never by the client form


def post_op_day(operated_on: date, on: date) -> int:
    """Day of surgery is day 0; the next calendar day is «1-е сутки»."""
    return max(0, (on - operated_on).days)


@dataclass(frozen=True)
class Thresholds:
    """From config/alert_thresholds.yaml. None disables the rule (the department decides)."""

    temperature_max: float | None = None
    drain_output_ml_max: int | None = None
    pain_vas_max: int | None = None
    purulent_discharge: bool | None = None


@dataclass(frozen=True)
class Alert:
    code: str
    message_ru: str


def evaluate_alerts(data: PostOpData, thresholds: Thresholds) -> list[Alert]:
    alerts: list[Alert] = []
    t = thresholds
    temp = data.vitals.temp
    if t.temperature_max is not None and temp is not None and temp > t.temperature_max:
        alerts.append(Alert("temperature", "температура выше порога"))
    out = data.drain.output_ml
    if t.drain_output_ml_max is not None and out is not None and out > t.drain_output_ml_max:
        alerts.append(Alert("drain_output", "отделяемое по дренажу выше порога"))
    pain = data.pain_vas
    if t.pain_vas_max is not None and pain is not None and pain > t.pain_vas_max:
        alerts.append(Alert("pain", "боль выше порога"))
    if t.purulent_discharge and data.wound.discharge == PURULENT:
        alerts.append(Alert("purulent_discharge", "гнойное отделяемое из раны"))
    return alerts


# Keys that may be sent to an LLM: structured values only, never free text.
STRUCTURED_KEYS = (
    "pain_vas",
    "consciousness",
    "vitals",
    "wound",
    "drain",
    "neurovascular",
    "calf_tenderness",
    "mobilization",
    "therapy",
)


def note_input(data: PostOpData, day: int) -> dict[str, Any]:
    """Structured input for a NoteGenerator. Carries no name, birth date or record number.

    It still includes the doctor's free-text complaints and analgesia, which only the local
    template generator may use; `llm_safe` removes them before anything leaves the server.
    """
    dumped = data.model_dump(mode="json")
    return {
        "post_op_day": day,
        "complaints": dumped["complaints"],
        **{key: dumped[key] for key in STRUCTURED_KEYS},
    }


def llm_safe(payload: dict[str, Any]) -> dict[str, Any]:
    """The only shape ever sent to an LLM: structured values, no free text."""
    safe = {k: v for k, v in payload.items() if k != "complaints"}
    therapy = dict(safe.get("therapy", {}))
    therapy["analgesia_given"] = bool(therapy.pop("analgesia", ""))
    safe["therapy"] = therapy
    return safe
