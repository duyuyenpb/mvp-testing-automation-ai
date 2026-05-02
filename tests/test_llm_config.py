from __future__ import annotations

import pytest

from qaforge.llm import resolve_config


def test_resolve_defaults_to_codex(monkeypatch) -> None:
    monkeypatch.delenv("QAFORGE_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("QAFORGE_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    config = resolve_config()

    assert config.provider == "codex"
    assert config.model == "gpt-5.2-codex"


def test_resolve_codex_provider_uses_openai_key(monkeypatch) -> None:
    monkeypatch.setenv("QAFORGE_LLM_PROVIDER", "codex")
    monkeypatch.setenv("QAFORGE_MODEL", "gpt-5.2-codex")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    config = resolve_config()

    assert config.provider == "codex"
    assert config.model == "gpt-5.2-codex"
    assert config.api_key == "test-openai-key"


def test_resolve_openai_compatible_requires_base_url(monkeypatch) -> None:
    monkeypatch.setenv("QAFORGE_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("QAFORGE_MODEL", "local-model")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    with pytest.raises(SystemExit) as exc:
        resolve_config()

    assert exc.value.code == 1


def test_resolve_gemini_provider_uses_gemini_key(monkeypatch) -> None:
    monkeypatch.setenv("QAFORGE_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("QAFORGE_MODEL", "gemini-2.5-pro")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    config = resolve_config()

    assert config.provider == "gemini"
    assert config.model == "gemini-2.5-pro"
    assert config.api_key == "test-gemini-key"


def test_resolve_missing_provider_key_exits(monkeypatch) -> None:
    monkeypatch.setenv("QAFORGE_LLM_PROVIDER", "openai")
    monkeypatch.setenv("QAFORGE_MODEL", "gpt-5.2")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(SystemExit) as exc:
        resolve_config()

    assert exc.value.code == 1


def test_resolve_rejects_unknown_provider(monkeypatch) -> None:
    monkeypatch.setenv("QAFORGE_LLM_PROVIDER", "mystery")
    monkeypatch.setenv("QAFORGE_MODEL", "whatever")

    with pytest.raises(SystemExit) as exc:
        resolve_config()

    assert exc.value.code == 1
