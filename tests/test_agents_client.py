"""Tests for the litellm-backed client (no network, no extra required)."""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

from repomind.agents.client import LiteLLMClient, MissingLLMError
from repomind.errors import RepoMindError


def _fake_litellm(content: str) -> tuple[types.ModuleType, dict[str, object]]:
    """Build a fake litellm module that records the completion kwargs."""
    recorded: dict[str, object] = {}
    module = types.ModuleType("litellm")

    def completion(**kwargs: object) -> object:
        recorded.update(kwargs)
        message = SimpleNamespace(content=content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    module.completion = completion  # type: ignore[attr-defined]
    return module, recorded


def test_completion_retries_and_returns_content(monkeypatch: pytest.MonkeyPatch) -> None:
    module, recorded = _fake_litellm('{"summary": "ok"}')
    monkeypatch.setitem(sys.modules, "litellm", module)

    client = LiteLLMClient(model="fake/model", timeout=5)

    assert client.complete(system="system", user="user") == '{"summary": "ok"}'
    assert recorded["model"] == "fake/model"
    assert recorded["timeout"] == 5
    assert recorded["num_retries"] == 2


def test_missing_extra_raises_helpful_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "litellm", None)

    client = LiteLLMClient(model="ollama/qwen2.5-coder:7b")

    with pytest.raises(MissingLLMError, match=r"repomind-analyzer\[llm\]"):
        client.complete(system="system", user="user")


def test_empty_response_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    module, _recorded = _fake_litellm("   ")
    monkeypatch.setitem(sys.modules, "litellm", module)

    client = LiteLLMClient(model="fake/model")

    with pytest.raises(RepoMindError, match="empty response"):
        client.complete(system="system", user="user")


def test_model_property_is_exposed() -> None:
    client = LiteLLMClient(model="gemini/gemini-3.8-flash")
    assert client.model == "gemini/gemini-3.8-flash"
