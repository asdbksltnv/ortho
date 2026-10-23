import uuid
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.domain.enums import Role
from tests.conftest import Api, case_payload
from tests.intake_fixture import tka_intake

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
T1, T2, T3 = "t1_primary_exam", "t2_diagnosis_justification", "t3_preop_epicrisis"
TODAY = date(2026, 3, 10)


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    for target in (
        "app.services.cases",
        "app.services.board",
        "app.services.documents",
        "app.services.intake",
    ):
        monkeypatch.setattr(f"{target}.local_today", lambda: TODAY)


def put_intake(api: Api, case: uuid.UUID, data: dict[str, Any], **kw: Any) -> Any:
    body = {"data": data, "request_id": str(uuid.uuid4()), **kw}
    return api.request("PUT", f"/cases/{case}/intake", json=body)


def doc(api: Api, case: uuid.UUID, tid: str) -> dict[str, Any]:
    return api.get(f"/cases/{case}/documents/{tid}").json()


def fields_by_key(d: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {f["key"]: f for f in d["fields"]}


def template_keys(tid: str) -> list[str]:
    path = next(CONFIG_DIR.glob(f"emr_templates/{tid}.yaml"))
    return [f["key"] for f in yaml.safe_load(path.read_text())["fields"]]


# -------------------------------------------------------------- intake


def test_new_case_intake_is_prefilled_from_procedure_template(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.DOCTOR)
    body = api.get(f"/cases/{case_id}/intake").json()
    assert body["is_new"] is True and body["can_edit"] is True
    data = body["data"]
    assert data["complaints"]["segment"] == "knee"
    assert data["local_status"]["segment"] == "knee"
    assert data["plan"]["consults"] == ["Анестезиолог"]
    assert data["plan"]["labs"][0] == "HBsAg (HBV)" and len(data["plan"]["labs"]) == 6
    assert data["caprini"]["factors"] == ["elective_major_arthroplasty"]
    assert body["derived"]["caprini"]["total"] == 7  # age 65 (2) + arthroplasty (5); BMI unknown


def test_intake_save_roundtrip_and_derived_values(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.DOCTOR)
    resp = put_intake(api, case_id, tka_intake(), completed=True)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_new"] is False and body["completed_at"] is not None
    d = body["derived"]
    assert d["age"] == 65 and d["bmi"] == 31.5  # preop vitals: 91 kg / 170 cm
    assert d["caprini"]["total"] == 8 and d["caprini"]["category_key"] == "high"
    assert set(d["caprini"]["automatic"]) == {"age_61_74", "bmi_over_25"}
    assert d["nutrition"] == {"bmi_low": False, "total": 0, "complete": True}
    assert d["columbia"]["visible"] == [1, 2, 7] and d["columbia"]["urgent_alert"] is False


def test_columbia_alert_in_derived_values(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.DOCTOR)
    data = tka_intake()
    data["columbia"] = {
        "q1": True,
        "q2": False,
        "q3": False,
        "q4": True,
        "q5": True,
        "q6": False,
        "q7": False,
    }
    d = put_intake(api, case_id, data).json()["derived"]["columbia"]
    assert d["urgent_alert"] is True and d["visible"] == [1, 2, 3, 4, 5, 6, 7]


def test_intake_idempotent_by_request_id(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.DOCTOR)
    rid = str(uuid.uuid4())
    first = api.request(
        "PUT", f"/cases/{case_id}/intake", json={"data": tka_intake(), "request_id": rid}
    )
    changed = tka_intake()
    changed["complaints"]["pain_vas"] = 1
    replay = api.request(
        "PUT", f"/cases/{case_id}/intake", json={"data": changed, "request_id": rid}
    )
    assert first.status_code == replay.status_code == 200
    assert replay.json()["data"]["complaints"]["pain_vas"] == 6  # replay did not apply again


def test_intake_conflict_when_another_user_saved(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.DOCTOR)
    base = put_intake(api, case_id, tka_intake()).json()["updated_at"]
    head = Api().as_role(Role.HEAD_OF_DEPARTMENT)
    edited = tka_intake()
    edited["complaints"]["pain_vas"] = 2
    assert put_intake(head, case_id, edited).status_code == 200
    stale = put_intake(api, case_id, tka_intake(), base_updated_at=base)
    assert stale.status_code == 409 and stale.json()["code"] == "conflict"
    assert "current_updated_at" in stale.json()["details"]


def test_same_user_can_overwrite_own_newer_save(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.DOCTOR)
    first = put_intake(api, case_id, tka_intake()).json()["updated_at"]
    put_intake(api, case_id, tka_intake())
    assert put_intake(api, case_id, tka_intake(), base_updated_at=first).status_code == 200


def test_intake_validation_rejects_bad_values_without_echo(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.DOCTOR)
    bad = tka_intake()
    bad["vitals"]["bp"] = "СЕКРЕТ"
    bad["complaints"]["pain_vas"] = 11
    resp = put_intake(api, case_id, bad)
    assert resp.status_code == 422 and "СЕКРЕТ" not in resp.text
    unknown = tka_intake()
    unknown["surprise"] = 1
    assert put_intake(api, case_id, unknown).status_code == 422


def test_intake_permissions(api: Api, case_id: uuid.UUID) -> None:
    for role in (Role.NURSE, Role.ANAESTHESIOLOGIST, Role.HEAD_NURSE):
        api.as_role(role)
        assert put_intake(api, case_id, tka_intake()).status_code == 403
        assert api.get(f"/cases/{case_id}/intake").status_code == 200
    api.login("doctor2")
    assert put_intake(api, case_id, tka_intake()).status_code == 403
    api.as_role(Role.ADMIN)
    assert api.get(f"/cases/{case_id}/intake").status_code == 403


def test_medication_anticoagulant_flag_drives_the_board_item(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.DOCTOR)
    data = tka_intake()
    data["medications"][0]["is_anticoagulant"] = True
    put_intake(api, case_id, data)
    case = api.get(f"/cases/{case_id}").json()
    assert case["takes_anticoagulant"] is True and "anticoag" in case["readiness"]["blocking"]
    data["medications"][0]["is_anticoagulant"] = False
    put_intake(api, case_id, data)
    assert api.get(f"/cases/{case_id}").json()["takes_anticoagulant"] is False


def test_intake_config_endpoint(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.NURSE)
    cfg = api.get("/config/intake").json()
    assert cfg["picklists"]["course"] == [
        "острое",
        "прогрессирующее",
        "стабильное",
        "рецидивирующее",
    ]
    assert cfg["picklists"]["physical_activity"][0] == "самостоятельно"
    assert cfg["systems"]["neuro"]["normal_ru"] == "Без очаговой неврологической симптоматики"
    assert cfg["systems"]["skin"]["normal_ru"] is None  # not provided by the department
    assert cfg["psycho"]["behavior"]["default_ru"] == "Адекватное"
    assert cfg["diets"] == [] and cfg["default_diet"] is None
    assert cfg["nutrition"]["bmi_threshold"] == 20.5
    assert len(cfg["caprini"]["factors"]) == 37
    assert cfg["columbia"]["always_ask"] == [1, 2, 7]


# -------------------------------------------------------------- T1


def test_template_list_shows_awaiting_templates(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.DOCTOR)
    listing = {d["template_id"]: d for d in api.get(f"/cases/{case_id}/documents").json()}
    assert listing["t4_patient_verification"]["status"] == "awaiting_template"
    assert listing["t5_caprini_sheet"]["status"] == "awaiting_template"
    assert listing[T1]["status"] == "not_generated"
    assert (
        api.post(f"/cases/{case_id}/documents/t4_patient_verification/generate").status_code == 422
    )


def test_critical_fields_block_generation(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.DOCTOR)
    resp = api.post(f"/cases/{case_id}/documents/{T1}/generate")
    assert resp.status_code == 422 and resp.json()["code"] == "generation_blocked"
    missing = {p["key"] for p in resp.json()["details"]["problems"] if p["code"] == "missing"}
    assert missing >= {
        "hospitalization_count",
        "allergy_has",
        "past_history",
        "medications",
        "bp",
        "pulse",
        "hr",
        "rr",
        "spo2",
        "temp",
        "diet",
        "nutrition_total",
    }
    put_intake(api, case_id, tka_intake())
    assert api.post(f"/cases/{case_id}/documents/{T1}/generate").status_code == 200


def test_t1_follows_emr_order_with_correct_types(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.DOCTOR)
    put_intake(api, case_id, tka_intake())
    d = api.post(f"/cases/{case_id}/documents/{T1}/generate").json()
    assert [f["key"] for f in d["fields"]] == template_keys(T1)
    assert len(d["fields"]) == 65 and sum(f["critical"] for f in d["fields"]) == 16
    f = fields_by_key(d)
    assert f["pulse"]["emr_type"] == "number" and f["pulse"]["value"] == "78"
    assert f["temp"]["value"] == "36,6"  # decimal separator from config
    assert f["hr"]["value"] == "78"  # prefilled from pulse
    assert f["bmi"]["display"] == "calculate" and f["bmi"]["value"] is None
    assert f["bp"]["value"] == "130/80"
    assert (
        f["allergy_has"]["value"] == "Нет"
        and f["allergy_description"]["value"] == "Аллергические реакции отрицает."
    )
    assert f["neuro"]["value"] == "Без очаговой неврологической симптоматики"
    assert f["columbia_q3"]["display"] == "skip" and f["columbia_q1"]["value"] == "Нет"
    assert f["nutrition_bmi_low"]["value"] == "Нет" and f["nutrition_total"]["value"] == "0"
    assert f["dx_main"]["icd"] == [{"code": "TEST.1", "text": "Тестовый основной диагноз"}]
    assert (
        f["treating_doctor"]["value"] == "Тест doctor" and f["resident"]["value"] == "Тест doctor"
    )
    assert f["labs"]["items"][0] == "HBsAg (HBV)"
    assert f["medication_orders"]["items"] == ["Препарат Б — тест", "Препарат В"]
    assert f["plan_checked"]["display"] == "manual"  # option list is TODO
    assert (
        f["goal"]["value"]
        == "Обследование и оперативное лечение: Тотальное эндопротезирование коленного сустава слева"
    )
    assert (
        "Жалобы на боль в области коленного сустава слева (ВАШ 6 из 10), ограничение движений, деформацию."
        in f["complaints"]["value"]
    )


def test_columbia_followups_show_only_after_trigger(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.DOCTOR)
    data = tka_intake()
    data["columbia"]["q2"] = True
    data["columbia"].update({"q3": False, "q4": False, "q5": False, "q6": False})
    put_intake(api, case_id, data)
    f = fields_by_key(api.post(f"/cases/{case_id}/documents/{T1}/generate").json())
    expected = {1: "Нет", 2: "Да", 3: "Нет", 4: "Нет", 5: "Нет", 6: "Нет", 7: "Нет"}
    assert {i: f[f"columbia_q{i}"]["value"] for i in range(1, 8)} == expected


def test_documents_visible_to_readers_but_generated_only_by_the_treating_doctor(
    api: Api, case_id: uuid.UUID
) -> None:
    api.as_role(Role.DOCTOR)
    put_intake(api, case_id, tka_intake())
    api.post(f"/cases/{case_id}/documents/{T1}/generate")
    for role in (Role.NURSE, Role.ANAESTHESIOLOGIST, Role.HEAD_NURSE):
        api.as_role(role)
        assert api.get(f"/cases/{case_id}/documents/{T1}").status_code == 200
        assert api.post(f"/cases/{case_id}/documents/{T1}/generate").status_code == 403
        assert (
            api.post(
                f"/cases/{case_id}/documents/{T1}/fields/bp/copied", json={"copied": True}
            ).status_code
            == 403
        )
    api.login("doctor2")
    assert api.post(f"/cases/{case_id}/documents/{T1}/generate").status_code == 403
    api.as_role(Role.ADMIN)
    assert api.get(f"/cases/{case_id}/documents").status_code == 403


# -------------------------------------------------------------- copy flags, outdated


def test_copy_flags_and_audit_without_content(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.DOCTOR)
    put_intake(api, case_id, tka_intake())
    api.post(f"/cases/{case_id}/documents/{T1}/generate")
    r = api.post(f"/cases/{case_id}/documents/{T1}/fields/bp/copied", json={"copied": True})
    assert fields_by_key(r.json())["bp"]["copied"] is True
    assert (
        api.post(
            f"/cases/{case_id}/documents/{T1}/fields/nope/copied", json={"copied": True}
        ).status_code
        == 404
    )
    api.post(f"/cases/{case_id}/documents/{T1}/copy-all")
    api.as_role(Role.HEAD_OF_DEPARTMENT)
    rows = api.get("/audit?action=copy").json()["items"]
    assert {r["diff"]["key"] for r in rows} == {"bp", "*"}
    assert "130/80" not in str(rows)


def test_outdated_detection_highlights_changed_fields_and_regeneration_keeps_ticks(
    api: Api, case_id: uuid.UUID
) -> None:
    api.as_role(Role.DOCTOR)
    put_intake(api, case_id, tka_intake())
    api.post(f"/cases/{case_id}/documents/{T1}/generate")
    for key in ("bp", "pulse"):
        api.post(f"/cases/{case_id}/documents/{T1}/fields/{key}/copied", json={"copied": True})
    assert doc(api, case_id, T1)["is_outdated"] is False

    changed = tka_intake()
    changed["vitals"]["pulse"] = 90
    put_intake(api, case_id, changed)
    state = doc(api, case_id, T1)
    assert state["status"] == "outdated" and state["is_outdated"] is True
    assert set(state["changed_keys"]) == {"pulse", "hr"}  # hr is prefilled from pulse
    listing = {d["template_id"]: d for d in api.get(f"/cases/{case_id}/documents").json()}
    assert listing[T1]["is_outdated"] is True

    regenerated = api.post(f"/cases/{case_id}/documents/{T1}/generate").json()
    f = fields_by_key(regenerated)
    assert f["pulse"]["value"] == "90" and f["pulse"]["copied"] is False  # changed: tick reset
    assert f["bp"]["copied"] is True  # unchanged: tick kept
    assert regenerated["is_outdated"] is False and regenerated["changed_keys"] == []


def test_unrelated_intake_edit_does_not_outdate_a_document(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.DOCTOR)
    put_intake(api, case_id, tka_intake())
    api.post(f"/cases/{case_id}/documents/{T1}/generate")
    other = tka_intake()
    other["preop"]["imaging"] = "изменено"  # only used by T3
    put_intake(api, case_id, other)
    assert doc(api, case_id, T1)["is_outdated"] is False


def test_copy_all_text_is_labelled_and_ordered(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.DOCTOR)
    put_intake(api, case_id, tka_intake())
    text = api.post(f"/cases/{case_id}/documents/{T1}/copy-all").json()["all_text"]
    assert text == "" or "Основные жалобы:" in text  # not generated yet -> nothing to copy
    api.post(f"/cases/{case_id}/documents/{T1}/generate")
    text = api.post(f"/cases/{case_id}/documents/{T1}/copy-all").json()["all_text"]
    lines = text.splitlines()
    assert lines[0].startswith("Основные жалобы: Жалобы на боль")
    assert "Температура тела, °C: 36,6" in lines
    assert lines.index("Артериальное давление, мм рт.ст.: 130/80") < lines.index("Пульс: 78")


# -------------------------------------------------------------- T2


def test_t2_requires_conclusion_and_main_diagnosis(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.DOCTOR)
    data = tka_intake()
    data["diagnosis"]["main"] = {"code": "", "text": ""}
    put_intake(api, case_id, data)
    resp = api.post(f"/cases/{case_id}/documents/{T2}/generate")
    missing = {p["key"] for p in resp.json()["details"]["problems"]}
    assert missing == {"conclusion", "dx_main"}
    put_intake(api, case_id, tka_intake())
    d = api.post(f"/cases/{case_id}/documents/{T2}/generate").json()
    assert [f["key"] for f in d["fields"]] == template_keys(T2) and len(d["fields"]) == 45
    assert not any(f["critical"] for f in d["fields"])


def test_t2_conclusion_follows_the_fixed_order(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.DOCTOR)
    put_intake(api, case_id, tka_intake())
    f = fields_by_key(api.post(f"/cases/{case_id}/documents/{T2}/generate").json())
    text = f["conclusion"]["value"]
    order = ["жалоб на", "анамнеза", "данных объективного осмотра", "выставлен диагноз"]
    positions = [text.index(part) for part in order]
    assert positions == sorted(positions)
    assert text.endswith("выставлен диагноз: Тестовый основной диагноз (TEST.1).")
    # only the recorded imaging result is cited; labs are not done on the board yet
    assert "результатов исследований (рентгенография: сужение суставной щели)" in text
    assert (
        "HBsAg" not in text and "Рентгенография коленного сустава" not in text
    )  # planned, not done


def test_t2_conclusion_cites_only_done_studies_and_recorded_facts(
    api: Api, case_id: uuid.UUID
) -> None:
    Api().as_role(Role.NURSE).patch(
        f"/cases/{case_id}/checklist/labs_core", json={"status": "done"}
    )
    api.as_role(Role.DOCTOR)
    sparse = tka_intake()
    sparse["history"] = {}
    sparse["local_status"] = {}
    sparse["complaints"] = {"pain_vas": 4}
    put_intake(api, case_id, sparse)
    f = fields_by_key(api.post(f"/cases/{case_id}/documents/{T2}/generate").json())
    text = f["conclusion"]["value"]
    assert text.startswith(
        "На основании жалоб на боль (ВАШ 4 из 10), результатов исследований (HBsAg (HBV), anti-HCV"
    )
    assert "Рентгенография коленного сустава" not in text
    assert "анамнеза" not in text and "объективного осмотра" not in text
    assert f["studies"]["items"][:2] == ["HBsAg (HBV)", "anti-HCV"]


def test_t2_copies_t1_and_uses_latest_vitals(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.DOCTOR)
    put_intake(api, case_id, tka_intake())
    t1 = fields_by_key(api.post(f"/cases/{case_id}/documents/{T1}/generate").json())
    t2 = fields_by_key(api.post(f"/cases/{case_id}/documents/{T2}/generate").json())
    for key in (
        "complaints",
        "history_brief",
        "course",
        "allergy_has",
        "past_history",
        "medications",
        "local_status",
        "skin",
    ):
        assert t2[key]["value"] == t1[key]["value"], key
    assert t2["bp"]["value"] == "125/80"  # fresh pre-op measurement wins
    assert t2["weight"]["value"] == "91"
    assert t2["medication_status"]["value"] == "Сверено"
    assert t2["physical_activity"]["value"] == "с опорой"
    assert t2["endo_course"]["display"] == "skip"


# -------------------------------------------------------------- T3


def _ready_for_t3(api: Api, case_id: uuid.UUID) -> None:
    head = Api().as_role(Role.HEAD_OF_DEPARTMENT)
    for key in ("labs_core", "consults", "anaesthesia"):
        assert (
            head.patch(f"/cases/{case_id}/checklist/{key}", json={"status": "done"}).status_code
            == 200
        )
    Api().as_role(Role.ANAESTHESIOLOGIST).request(
        "PUT",
        f"/cases/{case_id}/anaesthesia",
        json={"type": "Спинальная анестезия", "remarks": "тест"},
    )
    head.patch(
        f"/cases/{case_id}",
        json={"planned_surgery_date": "2026-03-12", "planned_surgery_time": "09:30:00"},
    )


def test_t3_requires_labs_consults_and_anaesthesia_done(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.DOCTOR)
    put_intake(api, case_id, tka_intake())
    resp = api.post(f"/cases/{case_id}/documents/{T3}/generate")
    gating = {p["key"] for p in resp.json()["details"]["problems"] if p["code"] == "gating"}
    assert gating == {"labs_core", "consults", "anaesthesia"}
    listing = {d["template_id"]: d for d in api.get(f"/cases/{case_id}/documents").json()}
    assert listing[T3]["can_generate"] is False
    # not_applicable counts as satisfied (e.g. no consultation needed)
    head = Api().as_role(Role.HEAD_OF_DEPARTMENT)
    head.patch(f"/cases/{case_id}/checklist/consults", json={"status": "not_applicable"})
    head.patch(f"/cases/{case_id}/checklist/labs_core", json={"status": "done"})
    head.patch(f"/cases/{case_id}/checklist/anaesthesia", json={"status": "pending"})
    api.as_role(Role.DOCTOR)
    resp = api.post(f"/cases/{case_id}/documents/{T3}/generate")
    assert {p["key"] for p in resp.json()["details"]["problems"] if p["code"] == "gating"} == {
        "anaesthesia"
    }


def test_t3_requires_fresh_vitals(api: Api, case_id: uuid.UUID) -> None:
    _ready_for_t3(api, case_id)
    api.as_role(Role.DOCTOR)
    data = tka_intake()
    data["preop"]["vitals"] = {}
    put_intake(api, case_id, data)
    resp = api.post(f"/cases/{case_id}/documents/{T3}/generate")
    missing = {p["key"] for p in resp.json()["details"]["problems"] if p["code"] == "missing"}
    assert missing == {"bp", "pulse", "hr", "rr", "spo2", "temp", "weight", "height"}


def test_t3_renders_in_order_with_prefill_handling(api: Api, case_id: uuid.UUID) -> None:
    _ready_for_t3(api, case_id)
    api.as_role(Role.DOCTOR)
    data = tka_intake()
    data["systems"]["msk"] = {"normal": False, "text": "Деформация правого коленного сустава"}
    for key in ("skin", "cvs", "resp", "gu", "gi"):
        data["systems"][key] = {"normal": True, "text": ""}
    put_intake(api, case_id, data)
    d = api.post(f"/cases/{case_id}/documents/{T3}/generate").json()
    assert [f["key"] for f in d["fields"]] == template_keys(T3)
    assert len(d["fields"]) == 58 and sum(f["critical"] for f in d["fields"]) == 2
    f = fields_by_key(d)
    # kept normal finding -> «Оставить текст EMR»
    for key in ("skin", "cvs", "resp", "gu", "gi", "neuro"):
        assert f[key]["display"] == "keep_emr" and f[key]["hint"] == "Оставить текст EMR", key
    # changed finding -> new value plus the select-all hint
    assert (
        f["msk"]["display"] == "value"
        and f["msk"]["value"] == "Деформация правого коленного сустава"
    )
    assert f["msk"]["hint"] == "Выделите всё в поле EMR перед вставкой"
    # epidemiology: nothing recorded -> keep the EMR's own text
    assert f["epidemiology"]["display"] == "keep_emr"
    assert f["or_time"]["value"] == "12.03.2026 09:30"
    assert f["anaesthesia_type"]["value"] == "Спинальная анестезия"
    assert f["operation_name"]["value"] == "Тотальное эндопротезирование коленного сустава слева"
    assert f["bp"]["value"] == "125/80" and f["temp"]["value"] == "36,5"
    assert f["risks"]["value"] is None and f["tactics"]["value"] is None  # TODO(clinical) config
    assert f["discharge_needs"]["value"] == "костыли, перевязки"
    assert "Риск ВТЭ по шкале Caprini: 8 (Высокий)" in f["risk_factors"]["value"]
    assert f["prevention"]["value"].startswith("Антибиотикопрофилактика: Препарат Б.")
    assert "Профилактика ВТЭ (Caprini 8, Высокий): Препарат В." in f["prevention"]["value"]
    assert f["indication"]["value"].startswith("Диагноз: Тестовый основной диагноз (TEST.1).")
    assert f["psych_assessment"]["display"] == "manual"


def test_t3_updates_general_condition_and_local_status(api: Api, case_id: uuid.UUID) -> None:
    _ready_for_t3(api, case_id)
    api.as_role(Role.DOCTOR)
    data = tka_intake()
    data["preop"]["general_condition"] = "Состояние удовлетворительное, без динамики."
    put_intake(api, case_id, data)
    f = fields_by_key(api.post(f"/cases/{case_id}/documents/{T3}/generate").json())
    assert f["general_condition"]["value"] == "Состояние удовлетворительное, без динамики."
    assert f["local_status"]["value"].startswith("Коленный сустав слева.")  # copied from T1


def test_anaesthesia_endpoint_permissions(api: Api, case_id: uuid.UUID) -> None:
    for role, expected in [
        (Role.ANAESTHESIOLOGIST, 200),
        (Role.HEAD_OF_DEPARTMENT, 200),
        (Role.DOCTOR, 403),
        (Role.NURSE, 403),
        (Role.HEAD_NURSE, 403),
        (Role.ADMIN, 403),
    ]:
        api.as_role(role)
        resp = api.request("PUT", f"/cases/{case_id}/anaesthesia", json={"type": "Тест"})
        assert resp.status_code == expected, role
    api.as_role(Role.NURSE)
    assert api.get(f"/cases/{case_id}").json()["anaesthesia_type"] == "Тест"


def test_head_name_is_filled_when_a_head_exists(api: Api, case_id: uuid.UUID) -> None:
    api.as_role(Role.DOCTOR)
    put_intake(api, case_id, tka_intake())
    f = fields_by_key(api.post(f"/cases/{case_id}/documents/{T2}/generate").json())
    assert f["head"]["value"] == "Тест head"


def test_case_payload_helper_is_reachable() -> None:
    assert case_payload()["procedure_key"] == "tka"
