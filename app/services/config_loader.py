import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

from app.schemas.config import (
    ChecklistConfig,
    ChecklistItemDefinition,
    ConfigMeta,
    LabsConfig,
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

    return AppConfig(checklist=checklist, labs=labs, procedures=procedures, files=files)


@lru_cache
def get_config() -> AppConfig:
    config = load_config(Path(get_settings().config_dir))
    if config.pending_validation:
        logger.warning(
            "%d config files still require clinical validation", len(config.pending_validation)
        )
    return config
