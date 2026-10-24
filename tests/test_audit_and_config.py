import uuid
from pathlib import Path
from typing import Any

import pytest
import yaml
from sqlalchemy import select

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


def test_location_questions_must_match_segments(config_copy: Path) -> None:
    path = config_copy / "location_questions.yaml"
    original = path.read_text()
    path.write_text(original.replace("\n  knee:\n", "\n  kneee:\n", 1))
    with pytest.raises(ValueError, match="unknown segments"):
        load_config(config_copy)
    path.write_text(original.replace("key: locking", "key: pain_character", 1))
    with pytest.raises(ValueError, match="duplicate keys"):
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


def test_demo_password_applies_to_demo_users_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import select

    from app import db as db_module
    from app.auth import verify_password
    from app.models.user import User
    from app.seed import apply_demo_password, seed_if_empty
    from app.settings import get_settings

    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'p.db'}")
    get_settings.cache_clear()
    db_module.get_engine.cache_clear()
    db_module.get_session_factory.cache_clear()
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(cfg, "head")
    seed_if_empty()
    with db_module.get_session_factory()() as s:
        from app.auth import hash_password

        s.add(
            User(
                login="real.user",
                full_name="Не демо",
                role="nurse",
                password_hash=hash_password("Original!Pass123"),
            )
        )
        s.commit()
    with pytest.raises(ValueError):
        apply_demo_password("short")
    assert apply_demo_password("Shared!DemoPass1") == 7
    with db_module.get_session_factory()() as s:
        rows = {u.login: u for u in s.scalars(select(User))}
        assert verify_password("Shared!DemoPass1", rows["head1"].password_hash)
        assert verify_password("Shared!DemoPass1", rows["admin1"].password_hash)
        assert verify_password("Original!Pass123", rows["real.user"].password_hash)  # untouched
    db_module.get_engine.cache_clear()
    db_module.get_session_factory.cache_clear()
    get_settings.cache_clear()


def _prod_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **env: str) -> Any:
    from alembic import command
    from alembic.config import Config

    from app import db as db_module
    from app.settings import get_settings

    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'prod.db'}")
    monkeypatch.setenv("DEMO_MODE", "false")
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    db_module.get_engine.cache_clear()
    db_module.get_session_factory.cache_clear()
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(cfg, "head")
    return db_module


def test_production_predeploy_creates_the_first_admin_and_retires_demo_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from app.auth import verify_password
    from app.models.case import Case
    from app.models.user import User
    from app.predeploy import main as predeploy
    from app.seed import seed_if_empty
    from app.settings import get_settings

    db_module = _prod_db(tmp_path, monkeypatch)
    seed_if_empty()  # an earlier demo deployment left synthetic users and cases behind
    monkeypatch.setenv("ADMIN_PASSWORD", "Real!Admin-Pass1")
    monkeypatch.setenv("ADMIN_LOGIN", "chief.admin")
    get_settings.cache_clear()
    predeploy()
    out = capsys.readouterr().out
    assert "Real!Admin-Pass1" not in out and "administrator 'chief.admin' created" in out
    assert "retired 7 demo user(s) and 12 demo case(s)" in out
    with db_module.get_session_factory()() as s:
        users = {u.login: u for u in s.scalars(select(User))}
        assert users["chief.admin"].role == "admin" and users["chief.admin"].is_active
        assert verify_password("Real!Admin-Pass1", users["chief.admin"].password_hash)
        assert not any(users[k].is_active for k in ("doctor1", "head1", "nurse1", "admin1"))
        assert {c.status for c in s.scalars(select(Case))} == {"discharged"}
    predeploy()  # idempotent
    assert "an administrator already exists" in capsys.readouterr().out
    db_module.get_engine.cache_clear()
    db_module.get_session_factory.cache_clear()
    get_settings.cache_clear()


def test_demo_users_stay_active_until_a_real_admin_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from app.models.user import User
    from app.predeploy import main as predeploy
    from app.seed import seed_if_empty
    from app.settings import get_settings

    db_module = _prod_db(tmp_path, monkeypatch)
    seed_if_empty()
    predeploy()  # no ADMIN_PASSWORD: warn, and do not lock everyone out
    assert "NO ADMINISTRATOR EXISTS" in capsys.readouterr().out
    with db_module.get_session_factory()() as s:
        assert all(u.is_active for u in s.scalars(select(User)))
    monkeypatch.setenv("ADMIN_PASSWORD", "short")
    get_settings.cache_clear()
    predeploy()
    assert "at least 10 characters" in capsys.readouterr().out
    db_module.get_engine.cache_clear()
    db_module.get_session_factory.cache_clear()
    get_settings.cache_clear()


def test_first_admin_never_overwrites_an_existing_account(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.auth import hash_password, verify_password
    from app.bootstrap import ensure_first_admin
    from app.models.user import User
    from app.settings import get_settings

    db_module = _prod_db(tmp_path, monkeypatch, ADMIN_PASSWORD="Another!Pass123")  # noqa: S106
    with db_module.get_session_factory()() as s:
        s.add(
            User(
                login="admin",
                full_name="Nurse",
                role="nurse",
                password_hash=hash_password("Nurse!Pass12345"),
            )
        )
        s.commit()
        assert "taken by a non-admin" in ensure_first_admin(s, get_settings())
        s.add(
            User(
                login="boss",
                full_name="Boss",
                role="admin",
                password_hash=hash_password("Boss!Pass123456"),
            )
        )
        s.commit()
        assert "already exists" in ensure_first_admin(s, get_settings())
        boss = s.scalars(select(User).where(User.login == "boss")).one()
        assert verify_password("Boss!Pass123456", boss.password_hash)
    db_module.get_engine.cache_clear()
    db_module.get_session_factory.cache_clear()
    get_settings.cache_clear()
