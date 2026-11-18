"""Gemini hiccups (overload, timeouts) are retried instead of failing the voice note."""

import asyncio
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.config import TIMEZONE, get_settings
from app.services import ai_agent


class _Busy(Exception):
    code = 503
    status = "UNAVAILABLE"


class _BadKey(Exception):
    code = 403
    status = "PERMISSION_DENIED"


@pytest.fixture
def calls(monkeypatch):
    log: list[str] = []
    monkeypatch.setattr(ai_agent, "RETRY_DELAYS", (0, 0))
    return log


def _run(monkeypatch, outcomes, calls):
    async def fake_once(parts, now, schema, model):
        calls.append(model)
        result = outcomes.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(ai_agent, "_generate_once", fake_once)
    return asyncio.run(ai_agent._generate(["hi"], datetime.now(TIMEZONE), None))


def test_busy_gemini_is_retried(monkeypatch, calls) -> None:
    ok = SimpleNamespace(text="{}")
    assert _run(monkeypatch, [_Busy(), TimeoutError(), ok], calls) is ok
    assert len(calls) == 3


def test_real_errors_are_not_retried(monkeypatch, calls) -> None:
    with pytest.raises(_BadKey):
        _run(monkeypatch, [_BadKey()], calls)
    assert len(calls) == 1


def test_fallback_model_after_retries(monkeypatch, calls) -> None:
    monkeypatch.setattr(get_settings(), "gemini_fallback_model", "backup-model")
    ok = SimpleNamespace(text="{}")
    assert _run(monkeypatch, [_Busy(), _Busy(), _Busy(), ok], calls) is ok
    assert calls[-1] == "backup-model"


def test_messages_tell_busy_from_broken() -> None:
    assert "не відповідає" in ai_agent._failure_message(_Busy())
    assert "GEMINI_API_KEY" in ai_agent._failure_message(_BadKey())
    assert "(Gemini: ValueError)" in ai_agent._failure_message(ValueError("x"))
