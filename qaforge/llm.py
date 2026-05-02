"""
Claude API client. The single source of truth for all LLM calls in QAForge.

Usage as a library:
    from qaforge.llm import ask_claude
    result = ask_claude(system="...", user="Hello")
    print(result.text)

Usage from the CLI (smoke test):
    qaforge ask "say hi in one sentence"
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = os.environ.get("QAFORGE_MODEL", "claude-sonnet-4-6")
DEFAULT_MAX_TOKENS = 4096


@dataclass(frozen=True)
class AskResult:
    text: str
    input_tokens: int
    output_tokens: int
    model: str


_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "[qaforge] ANTHROPIC_API_KEY is missing.\n"
            "  1. cp .env.example .env\n"
            "  2. Open .env and paste your key from "
            "https://console.anthropic.com/settings/keys\n"
            "  3. Re-run the command.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        from anthropic import Anthropic
    except ImportError:
        print(
            "[qaforge] The `anthropic` package is not installed.\n"
            "  Run: pip install -e '.[test]'  (or: pip install anthropic)",
            file=sys.stderr,
        )
        sys.exit(1)

    _client = Anthropic(api_key=api_key)
    return _client


def ask_claude(
    *,
    user: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    assistant_prefill: Optional[str] = None,
) -> AskResult:
    """
    Send a single user message to Claude and return the text response.

    If `assistant_prefill` is given, it is sent as the first chunk of the
    assistant turn. Claude continues from there. The returned text includes
    the prefill prepended, so callers see the full assistant message.

    Useful for forcing structured output: e.g. assistant_prefill='{"files":'
    almost guarantees Claude returns a JSON object.
    """
    chosen_model = model or DEFAULT_MODEL
    messages: list[dict] = [{"role": "user", "content": user}]
    if assistant_prefill is not None:
        messages.append({"role": "assistant", "content": assistant_prefill})

    kwargs: dict = {
        "model": chosen_model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system

    message = _get_client().messages.create(**kwargs)

    body = "\n".join(
        block.text for block in message.content if getattr(block, "type", None) == "text"
    )
    if assistant_prefill is not None:
        text = (assistant_prefill + body).strip()
    else:
        text = body.strip()

    return AskResult(
        text=text,
        input_tokens=message.usage.input_tokens,
        output_tokens=message.usage.output_tokens,
        model=chosen_model,
    )
