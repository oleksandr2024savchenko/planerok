"""Gemini agent: free-form text / voice → structured tasks."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from datetime import datetime, time, timedelta
from functools import lru_cache
from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import TIMEZONE, get_settings
from app.models import Priority
from app.schemas import TaskCreate, _to_vienna

logger = logging.getLogger(__name__)

WEEKDAYS_UK = (
    "понеділок",
    "вівторок",
    "середа",
    "четвер",
    "п'ятниця",
    "субота",
    "неділя",
)

CATEGORY_SLUGS: dict[str, str] = {
    "work": "робота",
    "study": "навчання",
    "training": "тренування",
    "personal": "особисте",
}

_END_OF_DAY = time(23, 59)


class TaskExtractionError(RuntimeError):
    pass


class ParsedTask(BaseModel):
    """Single task extracted from free-form speech or text."""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(
        min_length=1,
        max_length=255,
        description="Clear task title without filler like 'нагадай мені' or 'треба зробити'.",
    )
    description: str | None = Field(default=None, description="Extra details, if any.")
    category: Literal["work", "study", "training", "personal"] = Field(
        description="work=job, study=learning, training=sport, personal=everything else.",
    )
    priority: Literal["low", "medium", "high"] = "medium"
    deadline: datetime | None = Field(default=None, description="Event/due time as ISO 8601.")
    remind_at: datetime | None = Field(default=None, description="Reminder time as ISO 8601.")

    @field_validator("category", mode="before")
    @classmethod
    def _normalize_category(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        key = value.strip().lower()
        if key in CATEGORY_SLUGS:
            return key
        reverse = {slug: name for name, slug in CATEGORY_SLUGS.items()}
        return reverse.get(key, value)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("title is empty")
        return title[:255]

    @field_validator("deadline", "remind_at", mode="before")
    @classmethod
    def _blank_datetime(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("deadline", "remind_at")
    @classmethod
    def _localize(cls, value: datetime | None) -> datetime | None:
        return _to_vienna(value)


class TaskExtractionResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tasks: list[ParsedTask] = Field(default_factory=list)


class _GeminiTask(BaseModel):
    """Wire schema for Gemini. Avoids date-time format and length constraints the API rejects."""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(description="Short task title without filler words.")
    description: str | None = Field(default=None, description="Extra details, if any.")
    category: Literal["work", "study", "training", "personal"] = Field(
        description="work, study, training, or personal.",
    )
    priority: Literal["low", "medium", "high"] = "medium"
    deadline: str | None = Field(default=None, description="ISO 8601 timestamp with offset, or null.")
    remind_at: str | None = Field(default=None, description="ISO 8601 timestamp with offset, or null.")


class _GeminiExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tasks: list[_GeminiTask] = Field(default_factory=list)


def build_system_prompt(now: datetime | None = None) -> str:
    now = (now or datetime.now(TIMEZONE)).astimezone(TIMEZONE)
    weekday = WEEKDAYS_UK[now.weekday()]
    return (
        "Ти агент персонального планера. Витягни всі завдання з повідомлення користувача.\n"
        f"Поточний час (Europe/Vienna): {now.isoformat(timespec='minutes')} "
        f"— {weekday}, {now.strftime('%d.%m.%Y %H:%M')}.\n"
        "Правила:\n"
        "- title: коротка назва без «нагадай мені», «треба зробити», «не забудь».\n"
        "- category: work / study / training / personal за змістом.\n"
        "- priority: high якщо сьогодні або «терміново», інакше medium; low для нечітких бажань.\n"
        "- deadline і remind_at — ISO 8601 з часовим поясом Vienna.\n"
        "- Відносні дати («завтра», «через 2 години», «у п'ятницю о 18:00») рахуй від поточного часу вище.\n"
        "- Якщо названо час події, але не час нагадування: remind_at = за 15 хвилин до deadline.\n"
        "- Якщо названо лише час нагадування — запиши його в remind_at і deadline.\n"
        "- Кілька справ в одному повідомленні → кілька елементів у tasks.\n"
        "- Якщо завдань немає, поверни порожній список tasks.\n"
        '- Відповідь — лише JSON {"tasks":[{"title","description","category","priority","deadline","remind_at"}]}.'
    )


def finalize_task(task: ParsedTask, now: datetime | None = None) -> ParsedTask:
    """Guarantee Vienna timezones and the 15-minute reminder default."""
    now = (now or datetime.now(TIMEZONE)).astimezone(TIMEZONE)
    deadline = _to_vienna(task.deadline)
    remind_at = _to_vienna(task.remind_at)
    if deadline is not None and remind_at is None:
        if deadline.time() not in (_END_OF_DAY, time(0, 0)):
            remind_at = deadline - timedelta(minutes=15)
    return task.model_copy(update={"deadline": deadline, "remind_at": remind_at})


def to_task_create(task: ParsedTask) -> TaskCreate:
    return TaskCreate(
        title=task.title,
        description=task.description,
        category=CATEGORY_SLUGS[task.category],
        priority=Priority(task.priority),
        deadline=task.deadline,
        remind_at=task.remind_at,
    )


@lru_cache
def _client() -> genai.Client:
    key = get_settings().gemini_api_key
    if not key:
        raise TaskExtractionError("AI-агент не налаштовано. Додай GEMINI_API_KEY.")
    return genai.Client(api_key=key)


def _coerce_result(payload: object) -> TaskExtractionResult:
    if isinstance(payload, TaskExtractionResult):
        return payload
    if isinstance(payload, _GeminiExtraction):
        return TaskExtractionResult(
            tasks=[ParsedTask.model_validate(item.model_dump()) for item in payload.tasks]
        )
    if isinstance(payload, _GeminiTask):
        return TaskExtractionResult(tasks=[ParsedTask.model_validate(payload.model_dump())])
    if isinstance(payload, ParsedTask):
        return TaskExtractionResult(tasks=[payload])
    if isinstance(payload, list):
        return TaskExtractionResult(tasks=[ParsedTask.model_validate(item) for item in payload])
    if isinstance(payload, dict):
        if "tasks" in payload:
            return TaskExtractionResult.model_validate(payload)
        return TaskExtractionResult(tasks=[ParsedTask.model_validate(payload)])
    raise TaskExtractionError("Неочікувана відповідь моделі")


def _parse_response(response: object) -> TaskExtractionResult:
    parsed = getattr(response, "parsed", None)
    if parsed is not None:
        return _coerce_result(parsed)
    raw = (getattr(response, "text", None) or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    if not raw:
        raise TaskExtractionError("Порожня відповідь моделі")
    return TaskExtractionResult.model_validate_json(raw)


def _safe_error(exc: BaseException) -> str:
    text = str(exc)
    text = re.sub(r"(key=)[^&\s]+", r"\1***", text)
    text = re.sub(r"AIza[0-9A-Za-z_\-]{10,}", "***", text)
    return text[:500]


def _failure_message(exc: BaseException) -> str:
    code = getattr(exc, "code", None)
    status = str(getattr(exc, "status", "") or "")
    if code in (401, 403) or status in {"UNAUTHENTICATED", "PERMISSION_DENIED"}:
        return "Ключ Gemini відхилено. Перевір GEMINI_API_KEY."
    if code == 429 or status == "RESOURCE_EXHAUSTED":
        return "Ліміт Gemini вичерпано. Спробуй трохи пізніше."
    if code == 404 or status == "NOT_FOUND":
        return "Модель Gemini недоступна. Перевір GEMINI_MODEL."
    return "Не вдалося розпізнати повідомлення"


def _is_rejected_request(exc: BaseException) -> bool:
    return getattr(exc, "code", None) == 400


def transcode_ogg_to_wav(audio: bytes) -> bytes | None:
    """Telegram voice is OGG/Opus. Re-encode to WAV when ffmpeg is installed."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None or not audio:
        return None
    try:
        completed = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "ogg",
                "-i",
                "pipe:0",
                "-f",
                "wav",
                "-ac",
                "1",
                "-ar",
                "16000",
                "pipe:1",
            ],
            input=audio,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("ffmpeg transcode failed: %s", exc)
        return None
    if completed.returncode != 0 or not completed.stdout:
        logger.warning(
            "ffmpeg transcode failed: %s",
            completed.stderr.decode(errors="replace")[:300],
        )
        return None
    return completed.stdout


def audio_payloads(audio: bytes) -> list[tuple[bytes, str]]:
    payloads: list[tuple[bytes, str]] = [(audio, "audio/ogg")]
    wav = transcode_ogg_to_wav(audio)
    if wav:
        payloads.append((wav, "audio/wav"))
    return payloads


def _content_parts(
    *,
    text: str | None,
    audio: tuple[bytes, str] | None,
) -> list[types.Part | str]:
    parts: list[types.Part | str] = []
    if audio is not None:
        data, mime_type = audio
        parts.append(types.Part.from_bytes(data=data, mime_type=mime_type))
        parts.append("Розпізнай голосове повідомлення і витягни всі завдання.")
    if text:
        parts.append(text)
    return parts


async def _generate(
    parts: list[types.Part | str],
    now: datetime,
    schema: type[BaseModel] | None,
) -> object:
    config_kwargs: dict[str, object] = {
        "system_instruction": build_system_prompt(now),
        "temperature": 0.1,
        "response_mime_type": "application/json",
    }
    if schema is not None:
        config_kwargs["response_schema"] = schema
    return await _client().aio.models.generate_content(
        model=get_settings().gemini_model,
        contents=parts,
        config=types.GenerateContentConfig(**config_kwargs),
    )


async def parse_input_to_tasks(
    text: str | None = None,
    audio_bytes: bytes | None = None,
) -> TaskExtractionResult:
    cleaned = text.strip() if text else None
    if not cleaned and not audio_bytes:
        raise TaskExtractionError("Немає тексту або аудіо для розпізнавання")

    now = datetime.now(TIMEZONE)
    attempts: list[tuple[tuple[bytes, str] | None, type[BaseModel] | None]] = []
    if audio_bytes:
        for payload in audio_payloads(audio_bytes):
            attempts.append((payload, _GeminiExtraction))
            attempts.append((payload, None))
    else:
        attempts.append((None, _GeminiExtraction))
        attempts.append((None, None))

    response: object | None = None
    last_error: BaseException | None = None
    for audio, schema in attempts:
        mime = audio[1] if audio else "text"
        try:
            response = await _generate(_content_parts(text=cleaned, audio=audio), now, schema)
            break
        except TaskExtractionError:
            raise
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Gemini attempt mime=%s schema=%s failed: %s",
                mime,
                schema is not None,
                _safe_error(exc),
            )
            if not _is_rejected_request(exc):
                break
    else:
        response = None

    if response is None:
        assert last_error is not None
        logger.error(
            "Gemini extraction failed: %s",
            _safe_error(last_error),
            exc_info=last_error,
        )
        raise TaskExtractionError(_failure_message(last_error)) from last_error

    try:
        result = _parse_response(response)
    except Exception as exc:
        logger.exception("Failed to parse Gemini JSON: %s", getattr(response, "text", None))
        raise TaskExtractionError("Модель повернула некоректні дані") from exc

    tasks = [finalize_task(task, now=now) for task in result.tasks if task.title.strip()]
    return TaskExtractionResult(tasks=tasks)
