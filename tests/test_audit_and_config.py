import uuid
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.domain.enums import Role
from app.services.config_loader import load_config
from tests.conftest import Api, case_payload

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def test_mutations_are_audited_without_clinical_free_text(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.NURSE)
    api.patch(
        f"/cases/{case_id}/checklist/labs_core",
        json={"status": "problem", "note": "СЕКРЕТНАЯ ЗАМЕТКА Иванов"},
    )
    api.as_role(Role.HEAD_OF_DEPARTMENT)
    rows = api.get("/audit?entity=checklist_item").json()["items"]
    assert rows and rows[0]["action"] == "update"
    assert rows[0]["diff"]["status"] == ["not_started", "problem"]
    assert rows[0]["diff"]["note_changed"] is True
    full = api.get("/audit?limit=200").text
    assert "СЕКРЕТНАЯ" not in full and "Иванов" not in full


def test_login_success_and_failure_are_audited(api: Api) -> None:
    api.login("doctor", "bad")
    api.as_role(Role.HEAD_OF_DEPARTMENT)
    rows = api.get("/audit?action=login").json()["items"]
    assert [r["diff"]["success"] for r in rows] == [True, False]


def test_audit_pagination_by_cursor(api: Api) -> None:
    for _ in range(5):
        api.login("doctor", "bad")
    api.as_role(Role.ADMIN)
    seen: list[str] = []
    cursor = None
    while True:
        page = api.get(
            "/audit", params={"limit": 2, **({"cursor": cursor} if cursor else {})}
        ).json()
        seen += [r["id"] for r in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert len(seen) == len(set(seen)) >= 6


def test_bad_cursor_is_rejected(api: Api) -> None:
    api.as_role(Role.ADMIN)
    assert api.get("/audit?cursor=garbage").status_code == 422


def test_audit_log_has_no_update_or_delete_routes(api: Api) -> None:
    api.as_role(Role.ADMIN)
    for method in ("PATCH", "PUT", "DELETE", "POST"):
        assert api.request(method, "/audit", json={}).status_code in (404, 405)


def test_admin_sees_config_warning_list(api: Api) -> None:
    api.as_role(Role.ADMIN)
    files = api.get("/admin/config-status").json()
    assert {f["name"] for f in files} >= {"checklist_items.yaml", "labs.yaml", "tka.yaml"}
    assert all(f["requires_clinical_validation"] for f in files)


def test_definitions_expose_labels_and_procedures(api: Api) -> None:
    api.as_role(Role.NURSE)
    body = api.get("/config/definitions").json()
    assert body["checklist"][0]["label_ru"] == "Осмотр и документы (5)"
    assert {p["id"] for p in body["procedures"]} == {
        "tka",
        "tha",
        "arthroscopy",
        "plate_osteosynthesis",
        "im_nailing",
    }


def test_phase3_config_is_empty_where_the_department_has_not_decided() -> None:
    config = load_config(CONFIG_DIR)
    t = config.alerts.thresholds
    assert (t.temperature_max, t.drain_output_ml_max, t.pain_vas_max, t.purulent_discharge) == (
        None,
        None,
        None,
        None,
    )
    assert config.antibiotic.drugs == []  # never filled in here
    assert {s.name_ru for s in config.order_sets.sets} == {
        "Контрольная рентгенография",
        "Повторный ОАК",
    }
    t6 = config.emr_templates["t6_progress_note"]
    assert (
        t6.scope == "postop_entry"
        and len(t6.fields) == 25
        and sum(f.critical for f in t6.fields) == 6
    )
    assert {f.key for f in t6.fields if f.source == "note"} == {"general_condition", "local_status"}


def test_bad_note_path_and_order_type_fail_startup(config_copy: Path) -> None:
    path = config_copy / "emr_templates" / "t6_progress_note.yaml"
    text = path.read_text().replace('"path": "general_condition"', '"path": "nonsense"')
    path.write_text(text)
    with pytest.raises(ValueError, match="note fields"):
        load_config(config_copy)
    path.write_text(text.replace('"path": "nonsense"', '"path": "general_condition"'))
    sets = config_copy / "order_sets.yaml"
    sets.write_text(sets.read_text().replace("type: imaging", "type: surgery"))
    with pytest.raises(ValueError, match="unknown order types"):
        load_config(config_copy)


def test_real_config_loads_and_all_flags_are_unvalidated() -> None:
    config = load_config(CONFIG_DIR)
    assert len(config.checklist.items) == 11
    assert config.procedures["tka"].blocking_items == ["blood_reserve", "implant"]
    assert config.procedures["tha"].blocking_items == ["blood_reserve", "implant"]
    assert len(config.pending_validation) == len(config.files)
    assert all(lab.validity_days is None for lab in config.labs.labs)


@pytest.fixture
def config_copy(tmp_path: Path) -> Path:
    import shutil

    target = tmp_path / "config"
    shutil.copytree(CONFIG_DIR, target)
    return target


def test_unknown_blocking_item_fails_startup(config_copy: Path) -> None:
    path = config_copy / "procedure_templates" / "tka.yaml"
    data = yaml.safe_load(path.read_text())
    data["blocking_items"] = ["does_not_exist"]
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match="unknown blocking_items"):
        load_config(config_copy)


def test_unknown_field_in_config_is_rejected(config_copy: Path) -> None:
    path = config_copy / "checklist_items.yaml"
    data = yaml.safe_load(path.read_text())
    data["items"][0]["blokcing"] = "always"
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError):
        load_config(config_copy)


def test_duplicate_checklist_keys_fail(config_copy: Path) -> None:
    path = config_copy / "checklist_items.yaml"
    data = yaml.safe_load(path.read_text())
    data["items"].append(dict(data["items"][0]))
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match="duplicate"):
        load_config(config_copy)


def test_no_invented_clinical_values_in_config() -> None:
    """Appendix B defaults: everything not given in the build prompt stays null/empty."""
    config = load_config(CONFIG_DIR)
    for template in config.procedures.values():
        assert template.main_diagnosis.icd10 is None and template.main_diagnosis.text_ru is None
        assert all(v is None for v in template.surgery_texts.model_dump().values())


def test_migrations_match_models(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from alembic import command
    from alembic.config import Config

    from app.settings import get_settings

    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'm.db'}")
    get_settings.cache_clear()
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    command.upgrade(cfg, "head")
    command.check(cfg)  # raises if models and migrations differ
    get_settings.cache_clear()


def test_seed_creates_users_ward_and_twelve_cases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import func, select

    from app import db as db_module
    from app.models.case import Case
    from app.seed import seed_if_empty
    from app.settings import get_settings

    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 's.db'}")
    get_settings.cache_clear()
    db_module.get_engine.cache_clear()
    db_module.get_session_factory.cache_clear()
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(cfg, "head")
    creds = seed_if_empty()
    assert creds is not None and set(creds) == {
        "doctor1",
        "doctor2",
        "nurse1",
        "anaesth1",
        "head1",
        "headnurse1",
        "admin1",
    }
    assert all(len(p) >= 12 for p in creds.values())
    assert seed_if_empty() is None  # idempotent
    with db_module.get_session_factory()() as s:
        assert s.scalar(select(func.count()).select_from(Case)) == 12
        statuses = {c.status for c in s.scalars(select(Case))}
    assert {
        "admitted",
        "in_preparation",
        "approved_for_surgery",
        "called_to_or",
        "post_op",
    } <= statuses
    db_module.get_engine.cache_clear()
    db_module.get_session_factory.cache_clear()
    get_settings.cache_clear()


_ = (Any, case_payload)


def test_create_admin_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import select

    from app import db as db_module
    from app.create_admin import create_admin
    from app.models.user import User
    from app.settings import get_settings

    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'a.db'}")
    get_settings.cache_clear()
    db_module.get_engine.cache_clear()
    db_module.get_session_factory.cache_clear()
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(cfg, "head")
    with pytest.raises(ValueError):
        create_admin("boss", "Главный", "short")
    assert create_admin("boss", "Главный", "Long!Passw0rd1") is True
    assert create_admin("boss", "Главный", "Long!Passw0rd1") is False
    with db_module.get_session_factory()() as s:
        user = s.scalars(select(User).where(User.login == "boss")).one()
        assert user.role == "admin" and "Long!Passw0rd1" not in user.password_hash
    db_module.get_engine.cache_clear()
    db_module.get_session_factory.cache_clear()
    get_settings.cache_clear()
