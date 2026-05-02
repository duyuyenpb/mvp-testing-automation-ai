"""
Configurable LLM client. The single source of truth for all model calls in QAForge.

Users choose the provider in `.env`:
    QAFORGE_LLM_PROVIDER=anthropic | openai | codex | gemini | openai-compatible
    QAFORGE_MODEL=<provider model>

The public API returns a provider-neutral AskResult so planner/generator/healer
do not need provider-specific branching.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

DEFAULT_PROVIDER = os.environ.get("QAFORGE_LLM_PROVIDER", "codex").strip().lower()
DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-6",
    "openai": "gpt-5.2",
    "codex": "gpt-5.2-codex",
    "gemini": "gemini-2.5-pro",
    "openai-compatible": "gpt-4.1",
}
SUPPORTED_PROVIDERS = set(DEFAULT_MODELS)
DEFAULT_MAX_TOKENS = 4096


@dataclass(frozen=True)
class AskResult:
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    provider: str = DEFAULT_PROVIDER


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    api_key: str
    base_url: Optional[str] = None


_anthropic_client = None


def ask_llm(
    *,
    user: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    assistant_prefill: Optional[str] = None,
) -> AskResult:
    """
    Send a single prompt to the configured LLM provider and return text.

    `assistant_prefill` is preserved for structured-output prompts. Providers
    with native assistant-message support receive it as an assistant turn.
    Providers without that shape receive an instruction and the returned text
    is still prefixed before parsing by callers.
    """
    config = resolve_config(model=model)
    if config.provider == "anthropic":
        return _ask_anthropic(config, user, system, max_tokens, assistant_prefill)
    if config.provider in ("openai", "codex"):
        return _ask_openai_chat(config, user, system, max_tokens, assistant_prefill)
    if config.provider == "openai-compatible":
        return _ask_openai_chat(config, user, system, max_tokens, assistant_prefill)
    if config.provider == "gemini":
        return _ask_gemini(config, user, system, max_tokens, assistant_prefill)
    _exit_config_error(
        f"unsupported QAFORGE_LLM_PROVIDER={config.provider!r}",
        "Use one of: anthropic, openai, codex, gemini, openai-compatible.",
    )


def ask_claude(
    *,
    user: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    assistant_prefill: Optional[str] = None,
) -> AskResult:
    """Backward-compatible alias for older callers; uses the configured provider."""
    return ask_llm(
        user=user,
        system=system,
        model=model,
        max_tokens=max_tokens,
        assistant_prefill=assistant_prefill,
    )


def resolve_config(*, model: Optional[str] = None) -> LLMConfig:
    provider = os.environ.get("QAFORGE_LLM_PROVIDER", DEFAULT_PROVIDER).strip().lower()
    if provider == "openai_compatible":
        provider = "openai-compatible"
    if provider not in SUPPORTED_PROVIDERS:
        _exit_config_error(
            f"unsupported QAFORGE_LLM_PROVIDER={provider!r}",
            "Use one of: anthropic, openai, codex, gemini, openai-compatible.",
        )

    chosen_model = model or os.environ.get("QAFORGE_MODEL") or DEFAULT_MODELS.get(provider, "")
    if not chosen_model:
        _exit_config_error(
            f"no default model is configured for provider {provider!r}",
            "Set QAFORGE_MODEL in .env.",
        )

    api_key_var = _api_key_var(provider)
    api_key = os.environ.get(api_key_var, "").strip()
    if not api_key:
        _exit_config_error(
            f"{api_key_var} is missing.",
            _provider_setup_hint(provider, api_key_var),
        )

    base_url = os.environ.get("OPENAI_BASE_URL") if provider == "openai-compatible" else None
    if provider == "openai-compatible" and not base_url:
        _exit_config_error(
            "OPENAI_BASE_URL is missing.",
            "Set OPENAI_BASE_URL to your OpenAI-compatible endpoint, for example http://localhost:11434/v1.",
        )

    return LLMConfig(provider=provider, model=chosen_model, api_key=api_key, base_url=base_url)


def _api_key_var(provider: str) -> str:
    if provider == "anthropic":
        return "ANTHROPIC_API_KEY"
    if provider in ("openai", "codex", "openai-compatible"):
        return "OPENAI_API_KEY"
    if provider == "gemini":
        return "GEMINI_API_KEY"
    return "QAFORGE_API_KEY"


def _provider_setup_hint(provider: str, api_key_var: str) -> str:
    docs = {
        "anthropic": "https://console.anthropic.com/settings/keys",
        "openai": "https://platform.openai.com/api-keys",
        "codex": "https://platform.openai.com/api-keys",
        "gemini": "https://aistudio.google.com/app/apikey",
        "openai-compatible": "your provider's API key page",
    }
    return (
        "  1. cp .env.example .env\n"
        f"  2. Set QAFORGE_LLM_PROVIDER={provider}\n"
        f"  3. Add {api_key_var}=... from {docs.get(provider, 'your provider')}\n"
        "  4. Re-run the command."
    )


def _exit_config_error(message: str, hint: str) -> None:
    print(f"[qaforge] {message}\n{hint}", file=sys.stderr)
    sys.exit(1)


def _ask_anthropic(
    config: LLMConfig,
    user: str,
    system: Optional[str],
    max_tokens: int,
    assistant_prefill: Optional[str],
) -> AskResult:
    global _anthropic_client
    try:
        from anthropic import Anthropic
    except ImportError:
        _exit_config_error(
            "The `anthropic` package is not installed.",
            "Run: pip install -e '.[test]'  (or: pip install anthropic)",
        )

    if _anthropic_client is None:
        _anthropic_client = Anthropic(api_key=config.api_key)

    messages: list[dict] = [{"role": "user", "content": user}]
    if assistant_prefill is not None:
        messages.append({"role": "assistant", "content": assistant_prefill})

    kwargs: dict = {
        "model": config.model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system

    message = _anthropic_client.messages.create(**kwargs)
    body = "\n".join(
        block.text for block in message.content if getattr(block, "type", None) == "text"
    )
    text = _with_prefill(body, assistant_prefill)
    return AskResult(
        text=text,
        input_tokens=message.usage.input_tokens,
        output_tokens=message.usage.output_tokens,
        model=config.model,
        provider=config.provider,
    )


def _ask_openai_chat(
    config: LLMConfig,
    user: str,
    system: Optional[str],
    max_tokens: int,
    assistant_prefill: Optional[str],
) -> AskResult:
    base_url = (config.base_url or "https://api.openai.com/v1").rstrip("/")
    messages: list[dict[str, str]] = []
    if system:
        role = "system" if config.provider == "openai-compatible" else "developer"
        messages.append({"role": role, "content": system})
    messages.append({"role": "user", "content": user})
    if assistant_prefill is not None:
        messages.append({"role": "assistant", "content": assistant_prefill})

    payload = {
        "model": config.model,
        "messages": messages,
    }
    token_key = "max_tokens" if config.provider == "openai-compatible" else "max_completion_tokens"
    payload[token_key] = max_tokens
    data = _post_json(
        f"{base_url}/chat/completions",
        payload,
        headers={"Authorization": f"Bearer {config.api_key}"},
    )
    choice = (data.get("choices") or [{}])[0]
    body = ((choice.get("message") or {}).get("content") or "").strip()
    usage = data.get("usage") or {}
    return AskResult(
        text=_with_prefill(body, assistant_prefill),
        input_tokens=int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0),
        output_tokens=int(usage.get("completion_tokens") or usage.get("output_tokens") or 0),
        model=config.model,
        provider=config.provider,
    )


def _ask_gemini(
    config: LLMConfig,
    user: str,
    system: Optional[str],
    max_tokens: int,
    assistant_prefill: Optional[str],
) -> AskResult:
    prompt = user
    if assistant_prefill:
        prompt = (
            f"{user}\n\n"
            f"Begin your response by continuing after this exact prefix:\n{assistant_prefill}"
        )

    payload: dict = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens},
    }
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}

    model_path = config.model.replace("/", "%2F")
    data = _post_json(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model_path}:generateContent?key={config.api_key}",
        payload,
    )
    candidates = data.get("candidates") or []
    parts = (((candidates[0] if candidates else {}).get("content") or {}).get("parts") or [])
    body = "\n".join(str(part.get("text", "")) for part in parts).strip()
    usage = data.get("usageMetadata") or {}
    return AskResult(
        text=_with_prefill(body, assistant_prefill),
        input_tokens=int(usage.get("promptTokenCount") or 0),
        output_tokens=int(usage.get("candidatesTokenCount") or 0),
        model=config.model,
        provider=config.provider,
    )


def _post_json(url: str, payload: dict, *, headers: Optional[dict[str, str]] = None) -> dict:
    request_headers = {
        "Content-Type": "application/json",
        **(headers or {}),
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"[qaforge] LLM provider request failed ({exc.code}): {detail}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"[qaforge] LLM provider request failed: {exc}", file=sys.stderr)
        sys.exit(1)


def _with_prefill(body: str, assistant_prefill: Optional[str]) -> str:
    body = body.strip()
    if assistant_prefill is None:
        return body
    if body.startswith(assistant_prefill):
        return body
    return (assistant_prefill + body).strip()
