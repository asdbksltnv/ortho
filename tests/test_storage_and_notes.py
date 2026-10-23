import uuid
from pathlib import Path
from typing import Any

import pytest

from app.services import storage
from app.services.notes import (
    MAX_FIELD_CHARS,
    NoteGenerationError,
    TemplateNoteGenerator,
    day_phrase,
    generate_note,
    validate_output,
)
from app.settings import Settings, get_settings


def test_local_storage_roundtrip_and_traversal_guard(tmp_path: Path) -> None:
    store = storage.LocalStorage(tmp_path)
    store.put("wound/a/b.png", b"data", "image/png")
    assert store.get("wound/a/b.png") == (b"data", "image/png")
    assert store.get("wound/a/missing.png") is None
    with pytest.raises(ValueError):
        store.put("../escape.png", b"x", "image/png")
    with pytest.raises(ValueError):
        store.get("../../etc/passwd")


def test_disabled_storage_refuses_everything() -> None:
    disabled = storage.DisabledStorage()
    with pytest.raises(storage.StorageDisabled):
        disabled.put("k", b"x", "image/png")
    with pytest.raises(storage.StorageDisabled):
        disabled.get("k")


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], tuple[bytes, str]] = {}

    def put_object(self, Bucket: str, Key: str, Body: bytes, ContentType: str) -> None:  # noqa: N803
        self.objects[(Bucket, Key)] = (Body, ContentType)

    def get_object(self, Bucket: str, Key: str) -> dict[str, Any]:  # noqa: N803
        if (Bucket, Key) not in self.objects:
            raise KeyError(Key)
        body, content_type = self.objects[(Bucket, Key)]

        class Stream:
            def read(self) -> bytes:
                return body

        return {"Body": Stream(), "ContentType": content_type}


def test_s3_storage_uses_the_bucket_and_content_type() -> None:
    fake = FakeS3()
    store = storage.S3Storage("clinic-photos", client=fake)
    store.put("wound/x.jpg", b"jpg", "image/jpeg")
    assert fake.objects[("clinic-photos", "wound/x.jpg")] == (b"jpg", "image/jpeg")
    assert store.get("wound/x.jpg") == (b"jpg", "image/jpeg")
    assert store.get("wound/none.jpg") is None


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"DEMO_MODE": "true", "STORAGE_BACKEND": "s3"}, storage.DisabledStorage),
        ({"DEMO_MODE": "false", "STORAGE_BACKEND": "disabled"}, storage.DisabledStorage),
        ({"DEMO_MODE": "false", "STORAGE_BACKEND": "local"}, storage.LocalStorage),
    ],
)
def test_backend_follows_settings_and_demo_mode_wins(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str], expected: type
) -> None:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    assert isinstance(storage.get_storage(), expected)


def test_photo_keys_are_opaque_and_typed() -> None:
    key = storage.new_photo_key(uuid.UUID(int=1), "image/png")
    assert key.startswith("wound/00000000-0000-0000-0000-000000000001/") and key.endswith(".png")


# ---- note generators ----

INPUT = {
    "post_op_day": 3,
    "complaints": "",
    "pain_vas": None,
    "consciousness": None,
    "vitals": {},
    "wound": {
        "dressing": None,
        "discharge": None,
        "redness": False,
        "swelling": False,
        "sutures": None,
        "dressing_changed": False,
    },
    "drain": {"present": False, "output_ml": None, "removed": False},
    "neurovascular": {"pulsation": None, "sensation": None, "motor": None},
    "calf_tenderness": False,
    "mobilization": {"level": None, "weight_bearing": None, "physiotherapy": False},
    "therapy": {"antibiotic_day": None, "vte_prophylaxis": False, "analgesia": ""},
}


def test_template_generator_is_deterministic_and_starts_with_the_day() -> None:
    first = TemplateNoteGenerator().generate(INPUT)
    assert first == TemplateNoteGenerator().generate(INPUT)
    assert first.general_condition == "3-е сутки после операции."
    assert (
        first.local_status
        == "Гиперемия: нет. Отёк: нет. Дренаж отсутствует. Болезненность в икроножных мышцах: нет."
    )


def test_template_generator_states_only_recorded_facts() -> None:
    out = TemplateNoteGenerator().generate(
        {
            **INPUT,
            "post_op_day": 1,
            "complaints": "Боль.",
            "pain_vas": 0,
            "drain": {"present": True, "output_ml": None, "removed": True},
        }
    )
    assert out.general_condition == "1-е сутки после операции. Жалобы: Боль. Боль по ВАШ 0 из 10."
    assert "Дренаж удалён." in out.local_status and "Дренаж отсутствует" not in out.local_status


def test_day_phrase() -> None:
    assert day_phrase(0) == "День операции." and day_phrase(5) == "5-е сутки после операции."


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "text",
        "[]",
        '{"general_condition": "a"}',
        '{"general_condition": "a", "local_status": "b", "x": 1}',
        '{"general_condition": " ", "local_status": "b"}',
        '{"general_condition": 1, "local_status": "b"}',
        '{"general_condition": "' + "a" * (MAX_FIELD_CHARS + 1) + '", "local_status": "b"}',
    ],
)
def test_validate_output_rejects_bad_shapes(raw: str) -> None:
    with pytest.raises(NoteGenerationError):
        validate_output(raw, 2)


def test_validate_output_accepts_fenced_json_and_adds_the_day() -> None:
    fenced = '```json\n{"general_condition": "Жалоб нет.", "local_status": "Повязка  сухая."}\n```'
    out = validate_output(fenced, 2)
    assert (
        out.general_condition == "2-е сутки после операции. Жалоб нет."
        and out.local_status == "Повязка сухая."
    )
    already = validate_output(
        '{"general_condition": "2-е сутки после операции. Ок.", "local_status": "b"}', 2
    )
    assert already.general_condition == "2-е сутки после операции. Ок."


def test_generate_note_uses_the_template_by_default() -> None:
    name, out = generate_note(Settings(), INPUT)
    assert name == "template" and out.general_condition.startswith("3-е сутки")
