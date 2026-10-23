import json
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.domain.enums import Role
from app.services import storage
from app.services.config_loader import get_config
from app.settings import get_settings
from tests.conftest import Api, FakeTelegram, link_telegram
from tests.helpers import move_to_postop

TODAY = date(2026, 3, 10)
T6 = "t6_progress_note"
REAL_CLIENT = httpx.Client  # captured before any test patches httpx.Client
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    for target in (
        "app.services.cases",
        "app.services.board",
        "app.services.documents",
        "app.services.intake",
        "app.services.postop",
        "app.api.postop",
    ):
        monkeypatch.setattr(f"{target}.local_today", lambda: TODAY)


def entry_data(**over: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "complaints": "Беспокоит умеренная боль в области раны",
        "pain_vas": 3,
        "consciousness": "ясное",
        "vitals": {"bp": "120/80", "pulse": 76, "rr": 16, "spo2": 98, "temp": 36.7},
        "wound": {
            "dressing": "сухая",
            "discharge": "нет",
            "redness": False,
            "swelling": True,
            "sutures": "без особенностей",
            "dressing_changed": True,
        },
        "drain": {"present": True, "output_ml": 120, "removed": False},
        "neurovascular": {"pulsation": "сохранена", "sensation": "сохранена", "motor": "сохранены"},
        "calf_tenderness": False,
        "mobilization": {
            "level": "стоит у кровати",
            "weight_bearing": "с дополнительной опорой",
            "physiotherapy": True,
        },
        "therapy": {"antibiotic_day": 2, "vte_prophylaxis": True, "analgesia": "по назначению"},
    }
    data.update(over)
    return data


@pytest.fixture
def postop_case(api: Api, case_id: uuid.UUID, db: Any) -> uuid.UUID:
    move_to_postop(db, case_id, TODAY - timedelta(days=2))
    return case_id


def create(case: uuid.UUID, role: Role = Role.DOCTOR, **over: Any) -> Any:
    return Api().as_role(role).post(f"/cases/{case}/postop", json={"data": entry_data(**over)})


def fields(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {f["key"]: f for f in doc["fields"]}


# -------------------------------------------------------------- recording


def test_entries_start_only_after_the_patient_is_back_from_the_or(
    api: Api, case_id: uuid.UUID
) -> None:
    resp = create(case_id)
    assert resp.status_code == 409 and resp.json()["code"] == "not_postop"
    listing = Api().as_role(Role.DOCTOR).get(f"/cases/{case_id}/postop").json()
    assert listing["can_record"] is False and listing["entries"] == []


def test_create_entry_computes_the_day_and_drafts_a_note(api: Api, postop_case: uuid.UUID) -> None:
    resp = create(postop_case)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["post_op_day"] == 2 and body["entry_date"] == "2026-03-10"
    note = body["note"]
    assert note["generator"] == "template" and note["approved"] is False
    assert note["general_condition"].startswith("2-е сутки после операции.")
    assert "Боль по ВАШ 3 из 10." in note["general_condition"]
    assert "Антибиотикотерапия: 2-е сутки." in note["general_condition"]
    assert "Беспокоит умеренная боль" in note["general_condition"]
    local = note["local_status"]
    assert "Повязка сухая." in local and "Отёк: есть." in local and "Гиперемия: нет." in local
    assert "Дренаж: отделяемое 120 мл." in local
    assert "пульсация сохранена, чувствительность сохранена, движения сохранены" in local
    assert "Болезненность в икроножных мышцах: нет." in local


def test_day_of_surgery_wording(api: Api, case_id: uuid.UUID, db: Any) -> None:
    move_to_postop(db, case_id, TODAY)
    note = create(case_id).json()["note"]
    assert note["general_condition"].startswith("День операции.")


def test_one_entry_per_day(api: Api, postop_case: uuid.UUID) -> None:
    first = create(postop_case).json()
    again = create(postop_case)
    assert again.status_code == 409 and again.json()["code"] == "entry_exists"
    assert again.json()["details"]["entry_id"] == first["id"]


def test_listing_has_trends_and_the_todays_entry(api: Api, postop_case: uuid.UUID) -> None:
    create(postop_case)
    listing = Api().as_role(Role.NURSE).get(f"/cases/{postop_case}/postop").json()
    assert listing["can_edit"] is False and listing["today_entry_id"] == listing["entries"][0]["id"]
    assert listing["trends"] == [
        {
            "day": 2,
            "date": "2026-03-10",
            "temp": 36.7,
            "drain_ml": 120,
            "pain": 3,
            "discharge": "нет",
            "redness": False,
            "swelling": True,
        }
    ]


def test_who_can_record_and_edit(api: Api, postop_case: uuid.UUID) -> None:
    for role in (Role.NURSE, Role.HEAD_NURSE, Role.ANAESTHESIOLOGIST, Role.ADMIN):
        assert create(postop_case, role).status_code == 403, role
    other = Api()
    other.login("doctor2")
    assert (
        other.post(f"/cases/{postop_case}/postop", json={"data": entry_data()}).status_code == 403
    )
    assert create(postop_case, Role.HEAD_OF_DEPARTMENT).status_code == 201


def test_validation_rejects_bad_values_without_echo(api: Api, postop_case: uuid.UUID) -> None:
    resp = create(postop_case, pain_vas=11, vitals={"bp": "СЕКРЕТ"})
    assert resp.status_code == 422 and "СЕКРЕТ" not in resp.text


def test_editing_an_entry_redrafts_the_note_and_drops_the_approval(
    api: Api, postop_case: uuid.UUID
) -> None:
    entry = create(postop_case).json()
    base = f"/cases/{postop_case}/postop/{entry['id']}"
    doctor = Api().as_role(Role.DOCTOR)
    note = entry["note"]
    approved = doctor.post(
        f"{base}/note/approve",
        json={"general_condition": note["general_condition"], "local_status": note["local_status"]},
    ).json()
    assert (
        approved["note"]["approved"] is True
        and approved["note"]["approved_by_name"] == "Тест doctor"
    )
    edited = doctor.put(base, json={"data": entry_data(pain_vas=7)}).json()
    assert (
        edited["note"]["approved"] is False
        and "Боль по ВАШ 7 из 10." in edited["note"]["general_condition"]
    )
    assert edited["id"] == entry["id"] and edited["post_op_day"] == 2


# -------------------------------------------------------------- approval and T6


def generate_t6(case: uuid.UUID, entry: str) -> Any:
    return Api().as_role(Role.DOCTOR).post(f"/cases/{case}/postop/{entry}/document/generate")


def test_t6_has_the_template_shape(api: Api, postop_case: uuid.UUID) -> None:
    entry = create(postop_case).json()["id"]
    doc = generate_t6(postop_case, entry).json()
    assert len(doc["fields"]) == 25 and sum(f["critical"] for f in doc["fields"]) == 6
    f = fields(doc)
    assert (
        f["bp"]["value"] == "120/80"
        and f["temp"]["value"] == "36,7"
        and f["pulse"]["value"] == "76"
    )
    assert (
        f["exam_time"]["value"]
        and f["exam_time"]["value"][2] == "."
        and ":" in f["exam_time"]["value"]
    )
    assert f["cvp"]["value"] is None and "Пусто" in f["cvp"]["hint"]  # empty unless measured
    assert f["bmi"]["display"] == "calculate"
    assert "hr" not in f and not any(
        "drain" in k or "wound" in k for k in f
    )  # no heart rate, wound or drain fields
    assert f["receiving_doctor"]["display"] == "skip" and f["resident"]["value"] == "Тест doctor"


def test_t6_critical_vitals_block_generation(api: Api, postop_case: uuid.UUID) -> None:
    entry = create(postop_case, vitals={"bp": "120/80"}).json()["id"]
    resp = generate_t6(postop_case, entry)
    assert resp.status_code == 422
    missing = {p["key"] for p in resp.json()["details"]["problems"]}
    assert missing == {"pulse", "rr", "spo2", "temp"}


def test_an_unapproved_draft_cannot_be_copied(api: Api, postop_case: uuid.UUID) -> None:
    entry = create(postop_case).json()["id"]
    doc = generate_t6(postop_case, entry).json()
    f = fields(doc)
    assert f["general_condition"]["locked"] is True and f["local_status"]["locked"] is True
    assert f["bp"]["locked"] is False
    base = f"/cases/{postop_case}/postop/{entry}/document"
    doctor = Api().as_role(Role.DOCTOR)
    for key in ("general_condition", "local_status"):
        refused = doctor.post(f"{base}/fields/{key}/copied", json={"copied": True})
        assert refused.status_code == 409 and refused.json()["code"] == "note_not_approved"
    assert doctor.post(f"{base}/fields/bp/copied", json={"copied": True}).status_code == 200
    text = doctor.post(f"{base}/copy-all").json()["all_text"]
    assert "Артериальное давление: 120/80" in text
    assert "Описание:" not in text and "2-е сутки" not in text  # the drafts stay off the clipboard


def test_approval_unlocks_copying_and_refreshes_the_stored_document(
    api: Api, postop_case: uuid.UUID
) -> None:
    entry = create(postop_case).json()
    eid = entry["id"]
    generate_t6(postop_case, eid)
    doctor = Api().as_role(Role.DOCTOR)
    edited_general = entry["note"]["general_condition"] + " Состояние стабильное."
    resp = doctor.post(
        f"/cases/{postop_case}/postop/{eid}/note/approve",
        json={"general_condition": edited_general, "local_status": entry["note"]["local_status"]},
    )
    assert resp.status_code == 200 and resp.json()["note"]["approved"] is True
    doc = doctor.get(f"/cases/{postop_case}/postop/{eid}/document").json()
    f = fields(doc)
    assert (
        f["general_condition"]["locked"] is False
        and f["general_condition"]["value"] == edited_general
    )
    assert doc["is_outdated"] is False  # regenerated on approval
    marked = doctor.post(
        f"/cases/{postop_case}/postop/{eid}/document/fields/general_condition/copied",
        json={"copied": True},
    )
    assert (
        marked.status_code == 200 and fields(marked.json())["general_condition"]["copied"] is True
    )
    text = doctor.post(f"/cases/{postop_case}/postop/{eid}/document/copy-all").json()["all_text"]
    assert f"Описание: {edited_general}" in text


def test_approval_before_the_document_exists_does_not_create_one(
    api: Api, postop_case: uuid.UUID
) -> None:
    entry = create(postop_case).json()
    doctor = Api().as_role(Role.DOCTOR)
    doctor.post(
        f"/cases/{postop_case}/postop/{entry['id']}/note/approve",
        json={"general_condition": "Текст.", "local_status": "Текст."},
    )
    assert (
        doctor.get(f"/cases/{postop_case}/postop/{entry['id']}/document").json()["status"]
        == "not_generated"
    )


@pytest.mark.parametrize("role", [Role.NURSE, Role.HEAD_NURSE, Role.ANAESTHESIOLOGIST, Role.ADMIN])
def test_only_the_treating_doctor_or_head_approves(
    api: Api, postop_case: uuid.UUID, role: Role
) -> None:
    entry = create(postop_case).json()["id"]
    body = {"general_condition": "Текст.", "local_status": "Текст."}
    assert (
        Api()
        .as_role(role)
        .post(f"/cases/{postop_case}/postop/{entry}/note/approve", json=body)
        .status_code
        == 403
    )
    other = Api()
    other.login("doctor2")
    assert (
        other.post(f"/cases/{postop_case}/postop/{entry}/note/approve", json=body).status_code
        == 403
    )
    assert (
        Api()
        .as_role(Role.HEAD_OF_DEPARTMENT)
        .post(f"/cases/{postop_case}/postop/{entry}/note/approve", json=body)
        .status_code
        == 200
    )


def test_approval_needs_both_texts(api: Api, postop_case: uuid.UUID) -> None:
    entry = create(postop_case).json()["id"]
    resp = (
        Api()
        .as_role(Role.DOCTOR)
        .post(
            f"/cases/{postop_case}/postop/{entry}/note/approve",
            json={"general_condition": "", "local_status": "x"},
        )
    )
    assert resp.status_code == 422


def test_regenerating_the_draft_clears_the_approval(api: Api, postop_case: uuid.UUID) -> None:
    entry = create(postop_case).json()["id"]
    doctor = Api().as_role(Role.DOCTOR)
    base = f"/cases/{postop_case}/postop/{entry}"
    doctor.post(
        f"{base}/note/approve", json={"general_condition": "Текст.", "local_status": "Текст."}
    )
    redo = doctor.post(f"{base}/note/regenerate").json()
    assert redo["note"]["approved"] is False and redo["note"]["general_condition"].startswith(
        "2-е сутки"
    )


def test_approval_is_audited_without_the_note_text(api: Api, postop_case: uuid.UUID) -> None:
    entry = create(postop_case).json()["id"]
    Api().as_role(Role.DOCTOR).post(
        f"/cases/{postop_case}/postop/{entry}/note/approve",
        json={"general_condition": "СЕКРЕТНЫЙ ТЕКСТ", "local_status": "x"},
    )
    rows = Api().as_role(Role.HEAD_OF_DEPARTMENT).get("/audit?entity=ai_note_draft").json()["items"]
    assert rows[0]["diff"] == {
        "approved": True,
        "generator": "template",
    } and "СЕКРЕТНЫЙ" not in str(rows)


# -------------------------------------------------------------- alerts


def test_alerts_are_off_until_the_department_sets_thresholds(
    api: Api, postop_case: uuid.UUID
) -> None:
    hot = create(
        postop_case, vitals={"bp": "120/80", "pulse": 76, "rr": 16, "spo2": 98, "temp": 41}
    ).json()
    assert hot["alerts"] == []
    assert Api().as_role(Role.DOCTOR).get("/notifications").json() == []


def test_a_crossed_threshold_notifies_the_treating_doctor(
    api: Api,
    postop_case: uuid.UUID,
    db: Any,
    monkeypatch: pytest.MonkeyPatch,
    telegram_fake: FakeTelegram,
) -> None:
    thresholds = get_config().alerts.thresholds
    monkeypatch.setattr(thresholds, "temperature_max", 37.5)
    monkeypatch.setattr(thresholds, "purulent_discharge", True)
    link_telegram(db, "doctor", "222")
    entry = create(
        postop_case,
        vitals={"bp": "120/80", "pulse": 76, "rr": 16, "spo2": 98, "temp": 38.2},
        wound={"discharge": "гнойное"},
    ).json()
    assert set(entry["alerts"]) == {"temperature", "purulent_discharge"}
    feed = Api().as_role(Role.DOCTOR).get("/notifications").json()
    assert feed[0]["event"] == "postop_alert"
    sent = [text for chat, text in telegram_fake.sent if chat == "222"]
    assert sent == [
        "Пал. 1, к. 1 (И. А. Д.): послеоперационный сигнал — температура выше порога, гнойное отделяемое из раны"
    ]
    assert "38" not in sent[0] and "Иванов" not in sent[0]
    # the same finding on the next edit does not alert twice
    Api().as_role(Role.DOCTOR).put(
        f"/cases/{postop_case}/postop/{entry['id']}",
        json={
            "data": entry_data(
                vitals={"bp": "120/80", "pulse": 76, "rr": 16, "spo2": 98, "temp": 38.5},
                wound={"discharge": "гнойное"},
            )
        },
    )
    assert len([t for c, t in telegram_fake.sent if c == "222"]) == 1


# -------------------------------------------------------------- photo storage


def test_photos_are_disabled_in_demo_mode(
    api: Api, postop_case: uuid.UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    get_settings.cache_clear()
    entry = create(postop_case).json()["id"]
    doctor = Api().as_role(Role.DOCTOR)
    assert doctor.get(f"/cases/{postop_case}/postop").json()["photo_enabled"] is False
    resp = doctor.request(
        "PUT",
        f"/cases/{postop_case}/postop/{entry}/photo",
        content=PNG,
        headers={"Content-Type": "image/png"},
    )
    assert resp.status_code == 409 and resp.json()["code"] == "storage_disabled"


def test_photo_upload_download_and_checks(api: Api, postop_case: uuid.UUID, tmp_path: Path) -> None:
    storage.set_storage_for_tests(storage.LocalStorage(tmp_path))
    try:
        entry = create(postop_case).json()["id"]
        base = f"/cases/{postop_case}/postop/{entry}/photo"
        doctor = Api().as_role(Role.DOCTOR)
        assert doctor.get(f"/cases/{postop_case}/postop").json()["photo_enabled"] is True
        ok = doctor.request("PUT", base, content=PNG, headers={"Content-Type": "image/png"})
        assert ok.status_code == 200 and ok.json()["has_photo"] is True
        got = Api().as_role(Role.NURSE).get(base)
        assert (
            got.status_code == 200
            and got.content == PNG
            and got.headers["content-type"] == "image/png"
        )
        assert got.headers["cache-control"] == "private, no-store"
        spoof = doctor.request(
            "PUT", base, content=b"<html>", headers={"Content-Type": "image/png"}
        )
        assert spoof.status_code == 415
        wrong = doctor.request("PUT", base, content=PNG, headers={"Content-Type": "image/jpeg"})
        assert wrong.status_code == 415
        big = doctor.request(
            "PUT",
            base,
            content=PNG + b"0" * storage.MAX_BYTES,
            headers={"Content-Type": "image/png"},
        )
        assert big.status_code == 413
        nurse = Api().as_role(Role.NURSE)
        assert (
            nurse.request(
                "PUT", base, content=PNG, headers={"Content-Type": "image/png"}
            ).status_code
            == 403
        )
        assert Api().as_role(Role.ADMIN).get(base).status_code == 403
        assert len(list(tmp_path.rglob("*.png"))) == 1
    finally:
        storage.set_storage_for_tests(None)


def test_the_client_cannot_set_the_photo_key(api: Api, postop_case: uuid.UUID) -> None:
    entry = create(postop_case, photo_key="wound/evil.png").json()
    assert entry["data"]["photo_key"] is None and entry["has_photo"] is False


# -------------------------------------------------------------- LLM generator


@pytest.fixture
def llm(monkeypatch: pytest.MonkeyPatch) -> list[httpx.Request]:
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("AI_MODEL", "test-model")
    get_settings.cache_clear()
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        reply = {
            "general_condition": "Состояние удовлетворительное, боль умеренная.",
            "local_status": "Повязка сухая, отделяемого нет.",
        }
        return httpx.Response(
            200, json={"content": [{"type": "text", "text": json.dumps(reply, ensure_ascii=False)}]}
        )

    monkeypatch.setattr(
        "app.services.notes.httpx.Client",
        lambda timeout=None: REAL_CLIENT(transport=httpx.MockTransport(handler)),
    )
    llm.handler = handler  # type: ignore[attr-defined]
    return requests


def test_llm_request_contains_no_identifiers_or_free_text(
    api: Api, postop_case: uuid.UUID, llm: list[httpx.Request]
) -> None:
    resp = create(
        postop_case,
        complaints="Иванов Алишер просит воды, история T-0001",
        therapy={"antibiotic_day": 2, "analgesia": "секретный препарат"},
    )
    assert resp.status_code == 201
    note = resp.json()["note"]
    assert note["generator"] == "llm"
    assert (
        note["general_condition"]
        == "2-е сутки после операции. Состояние удовлетворительное, боль умеренная."
    )
    assert len(llm) == 1
    request = llm[0]
    assert request.headers["x-api-key"] == "test-key" and request.url.host == "api.anthropic.com"
    body = request.content.decode()
    sent = json.loads(body)
    assert sent["model"] == "test-model" and "только предоставленные факты" in sent["system"]
    for forbidden in (
        "Иванов",
        "Алишер",
        "T-0001",
        "1960",
        "просит воды",
        "секретный",
        "Тест doctor",
    ):
        assert forbidden not in body, forbidden
    payload = json.loads(sent["messages"][0]["content"])
    assert payload["post_op_day"] == 2 and payload["therapy"]["analgesia_given"] is True
    assert "complaints" not in payload


@pytest.mark.parametrize(
    "reply",
    [
        "это не JSON",
        json.dumps({"general_condition": "x"}),
        json.dumps({"general_condition": "x", "local_status": "y", "extra": "z"}),
        json.dumps({"general_condition": "", "local_status": "y"}),
        json.dumps({"general_condition": "a" * 1600, "local_status": "y"}),
        json.dumps({"general_condition": 5, "local_status": "y"}),
    ],
)
def test_invalid_llm_output_falls_back_to_the_template(
    api: Api,
    postop_case: uuid.UUID,
    llm: list[httpx.Request],
    monkeypatch: pytest.MonkeyPatch,
    reply: str,
) -> None:
    monkeypatch.setattr(
        "app.services.notes.httpx.Client",
        lambda timeout=None: REAL_CLIENT(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, json={"content": [{"text": reply}]})
            )
        ),
    )
    note = create(postop_case).json()["note"]
    assert note["generator"] == "template" and note["general_condition"].startswith(
        "2-е сутки после операции."
    )


def test_llm_http_failure_falls_back_to_the_template(
    api: Api, postop_case: uuid.UUID, llm: list[httpx.Request], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.services.notes.httpx.Client",
        lambda timeout=None: REAL_CLIENT(
            transport=httpx.MockTransport(lambda r: httpx.Response(500))
        ),
    )
    assert create(postop_case).json()["note"]["generator"] == "template"


def test_llm_without_a_key_or_model_uses_the_template(
    api: Api, postop_case: uuid.UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    get_settings.cache_clear()
    assert create(postop_case).json()["note"]["generator"] == "template"


def test_llm_note_is_still_a_locked_draft(
    api: Api, postop_case: uuid.UUID, llm: list[httpx.Request]
) -> None:
    entry = create(postop_case).json()["id"]
    doc = generate_t6(postop_case, entry).json()
    assert fields(doc)["general_condition"]["locked"] is True
