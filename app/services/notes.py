"""Progress-note generators behind one interface.

The default is deterministic Russian text from Jinja2 templates. An optional LLM generator
(AI_PROVIDER=anthropic) receives de-identified structured data only (`llm_safe`), is told to use
only the given facts, and its output is validated; on any failure the template text is used.
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.domain.postop import llm_safe
from app.settings import Settings

logger = logging.getLogger("notes")

MAX_FIELD_CHARS = 1500
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
SYSTEM_PROMPT = (
    "Ты помогаешь врачу-ортопеду оформить дневниковую запись. Напиши клинический текст на русском "
    "языке, используя только предоставленные факты. Не добавляй новых находок и не давай "
    "рекомендаций. Ответь JSON-объектом ровно с двумя строковыми полями: general_condition "
    "(жалобы, боль, сознание, двигательный режим, терапия) и local_status (рана, повязка, "
    "дренаж, отёк, дистальный нейроваскулярный статус)."
)


@dataclass(frozen=True)
class NoteOutput:
    general_condition: str
    local_status: str

    def to_dict(self) -> dict[str, str]:
        return {"general_condition": self.general_condition, "local_status": self.local_status}


class NoteGenerationError(Exception):
    pass


class NoteGenerator(Protocol):
    name: str

    def generate(self, structured_input: dict[str, Any]) -> NoteOutput: ...


def day_phrase(day: int) -> str:
    return "День операции." if day == 0 else f"{day}-е сутки после операции."


class TemplateNoteGenerator:
    name = "template"

    def generate(self, structured_input: dict[str, Any]) -> NoteOutput:
        from app.services.documents import jinja_env

        env = jinja_env()
        general = env.get_template("postop_general.j2").render(data=structured_input)
        local = env.get_template("postop_local.j2").render(data=structured_input)
        return NoteOutput(" ".join(general.split()), " ".join(local.split()))


class LLMNoteGenerator:
    name = "llm"

    def __init__(self, api_key: str, model: str, timeout: float, http: httpx.Client | None = None):
        self._api_key = api_key
        self._model = model
        self._http = http or httpx.Client(timeout=timeout)

    def generate(self, structured_input: dict[str, Any]) -> NoteOutput:
        payload = llm_safe(
            structured_input
        )  # no names, dates of birth, record numbers or free text
        body = {
            "model": self._model,
            "max_tokens": 1024,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        }
        try:
            response = self._http.post(
                ANTHROPIC_URL,
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=body,
            )
            response.raise_for_status()
            text = response.json()["content"][0]["text"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise NoteGenerationError(type(exc).__name__) from None
        return validate_output(text, int(structured_input["post_op_day"]))


def validate_output(raw: str, day: int) -> NoteOutput:
    """Exactly two non-empty string fields within length limits; the day phrase comes first."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(cleaned)
    except ValueError:
        raise NoteGenerationError("not json") from None
    if not isinstance(data, dict) or set(data) != {"general_condition", "local_status"}:
        raise NoteGenerationError("unexpected fields")
    general, local = data["general_condition"], data["local_status"]
    for value in (general, local):
        if not isinstance(value, str) or not value.strip() or len(value) > MAX_FIELD_CHARS:
            raise NoteGenerationError("bad field")
    general = " ".join(general.split())
    phrase = day_phrase(day)
    if not general.startswith(phrase):
        general = f"{phrase} {general}"
    return NoteOutput(general, " ".join(local.split()))


def generate_note(
    settings: Settings,
    structured_input: dict[str, Any],
    *,
    http: httpx.Client | None = None,
) -> tuple[str, NoteOutput]:
    """Returns (generator name, output). Falls back to the template generator on any failure."""
    template = TemplateNoteGenerator()
    if settings.ai_provider == "anthropic" and settings.anthropic_api_key and settings.ai_model:
        generator = LLMNoteGenerator(
            settings.anthropic_api_key, settings.ai_model, settings.ai_timeout_s, http
        )
        try:
            return generator.name, generator.generate(structured_input)
        except NoteGenerationError as exc:
            logger.warning("LLM note failed (%s); using the template generator", exc)
    return template.name, template.generate(structured_input)
