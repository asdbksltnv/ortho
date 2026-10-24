import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

from app.domain.emr import TemplateSpec
from app.domain.intake import path_exists
from app.schemas.config import (
    AlertThresholdsConfig,
    AntibioticConfig,
    CapriniConfig,
    ChecklistConfig,
    ChecklistItemDefinition,
    ColumbiaConfig,
    ConfigMeta,
    DefaultsConfig,
    DietsConfig,
    EmrTemplateConfig,
    LabsConfig,
    LocationQuestionsConfig,
    NutritionConfig,
    OrderSetsConfig,
    ProcedureTemplate,
)
from app.settings import get_settings

logger = logging.getLogger("config")


@dataclass(frozen=True)
class ConfigFileStatus:
    name: str
    version: int
    requires_clinical_validation: bool


@dataclass(frozen=True)
class AppConfig:
    checklist: ChecklistConfig
    labs: LabsConfig
    procedures: dict[str, ProcedureTemplate]
    caprini: CapriniConfig
    columbia: ColumbiaConfig
    nutrition: NutritionConfig
    diets: DietsConfig
    defaults: DefaultsConfig
    locations: LocationQuestionsConfig
    alerts: AlertThresholdsConfig
    antibiotic: AntibioticConfig
    order_sets: OrderSetsConfig
    emr_templates: dict[str, TemplateSpec]
    files: list[ConfigFileStatus]

    @property
    def checklist_by_key(self) -> dict[str, ChecklistItemDefinition]:
        return {i.key: i for i in self.checklist.items}

    @property
    def pending_validation(self) -> list[ConfigFileStatus]:
        return [f for f in self.files if f.requires_clinical_validation]


def _read[T: BaseModel](path: Path, model: type[T]) -> T:
    with path.open(encoding="utf-8") as fh:
        return model.model_validate(yaml.safe_load(fh))


def _validate_locations(locations: LocationQuestionsConfig, segments: set[str]) -> None:
    unknown = set(locations.locations) - segments
    if unknown:
        raise ValueError(f"location_questions.yaml: unknown segments {sorted(unknown)}")
    for segment in locations.locations:
        keys = [q.key for q in locations.questions_for(segment)]
        duplicates = {k for k in keys if keys.count(k) > 1}
        if duplicates:
            raise ValueError(
                f"location_questions.yaml: {segment}: duplicate keys {sorted(duplicates)}"
            )


def load_config(config_dir: Path) -> AppConfig:
    files: list[ConfigFileStatus] = []

    def track(path: Path, meta: ConfigMeta) -> None:
        files.append(ConfigFileStatus(path.name, meta.version, meta.requires_clinical_validation))

    checklist = _read(config_dir / "checklist_items.yaml", ChecklistConfig)
    track(config_dir / "checklist_items.yaml", checklist)
    labs = _read(config_dir / "labs.yaml", LabsConfig)
    track(config_dir / "labs.yaml", labs)

    keys = {i.key for i in checklist.items}
    if len(keys) != len(checklist.items):
        raise ValueError("duplicate checklist item keys")

    procedures: dict[str, ProcedureTemplate] = {}
    for path in sorted((config_dir / "procedure_templates").glob("*.yaml")):
        template = _read(path, ProcedureTemplate)
        unknown = set(template.blocking_items) - keys
        if unknown:
            raise ValueError(f"{path.name}: unknown blocking_items {sorted(unknown)}")
        procedures[template.id] = template
        track(path, template)

    caprini = _read(config_dir / "caprini.yaml", CapriniConfig)
    columbia = _read(config_dir / "columbia.yaml", ColumbiaConfig)
    nutrition = _read(config_dir / "nutrition.yaml", NutritionConfig)
    diets = _read(config_dir / "diets.yaml", DietsConfig)
    defaults = _read(config_dir / "defaults_ru.yaml", DefaultsConfig)
    locations = _read(config_dir / "location_questions.yaml", LocationQuestionsConfig)
    _validate_locations(locations, {s.key for s in defaults.segments})
    alerts = _read(config_dir / "alert_thresholds.yaml", AlertThresholdsConfig)
    antibiotic = _read(config_dir / "antibiotic_protocol.yaml", AntibioticConfig)
    order_sets = _read(config_dir / "order_sets.yaml", OrderSetsConfig)
    for order_set in order_sets.sets:
        bad = {o.type for o in order_set.orders} - ORDER_TYPES
        if bad:
            raise ValueError(f"order set {order_set.key}: unknown order types {sorted(bad)}")
    for name, meta in (
        ("alert_thresholds.yaml", alerts),
        ("antibiotic_protocol.yaml", antibiotic),
        ("order_sets.yaml", order_sets),
        ("caprini.yaml", caprini),
        ("columbia.yaml", columbia),
        ("nutrition.yaml", nutrition),
        ("diets.yaml", diets),
        ("defaults_ru.yaml", defaults),
        ("location_questions.yaml", locations),
    ):
        track(config_dir / name, meta)

    caprini_keys = {f.key for f in caprini.factors}
    for template in procedures.values():
        unknown_factors = set(template.caprini_defaults) - caprini_keys
        if unknown_factors:
            raise ValueError(f"{template.id}: unknown caprini_defaults {sorted(unknown_factors)}")

    emr_templates: dict[str, TemplateSpec] = {}
    for path in sorted((config_dir / "emr_templates").glob("*.yaml")):
        emr = _read(path, EmrTemplateConfig)
        track(path, emr)
        emr_templates[emr.id] = emr.to_spec()
    _validate_emr(emr_templates, keys, templates_dir=TEMPLATES_DIR)

    return AppConfig(
        checklist=checklist,
        labs=labs,
        procedures=procedures,
        caprini=caprini,
        columbia=columbia,
        nutrition=nutrition,
        diets=diets,
        defaults=defaults,
        locations=locations,
        alerts=alerts,
        antibiotic=antibiotic,
        order_sets=order_sets,
        emr_templates=emr_templates,
        files=files,
    )


TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates_ru"
ORDER_TYPES = {"lab", "imaging", "consult", "other"}


def _validate_emr(
    templates: dict[str, TemplateSpec], checklist_keys: set[str], templates_dir: Path
) -> None:
    for spec in templates.values():
        seen: set[str] = set()
        for field in spec.fields:
            where = f"{spec.id}.{field.key}"
            if field.key in seen:
                raise ValueError(f"{where}: duplicate key")
            seen.add(field.key)
            if field.source == "generated":
                if not field.generator or not (templates_dir / f"{field.generator}.j2").is_file():
                    raise ValueError(f"{where}: missing generator template {field.generator!r}")
            elif field.source.startswith("copy:"):
                ref_template, ref_key = field.source.removeprefix("copy:").split(".", 1)
                target = templates.get(ref_template)
                if target is None or ref_key not in {f.key for f in target.fields}:
                    raise ValueError(f"{where}: bad copy reference {field.source!r}")
            elif (
                field.source == "form"
                and field.path
                and field.format != "fact"
                and not path_exists(field.path)
            ):
                raise ValueError(f"{where}: unknown intake path {field.path!r}")
            if field.source == "note" and field.path not in {"general_condition", "local_status"}:
                raise ValueError(f"{where}: note fields use path general_condition or local_status")
            if field.source == "staff" and field.staff not in {"treating_doctor", "head", "author"}:
                raise ValueError(f"{where}: unknown staff role {field.staff!r}")
        unknown = set(spec.gating_items) - checklist_keys
        if unknown:
            raise ValueError(f"{spec.id}: unknown gating_items {sorted(unknown)}")


@lru_cache
def get_config() -> AppConfig:
    config = load_config(Path(get_settings().config_dir))
    if config.pending_validation:
        logger.warning(
            "%d config files still require clinical validation", len(config.pending_validation)
        )
    return config
