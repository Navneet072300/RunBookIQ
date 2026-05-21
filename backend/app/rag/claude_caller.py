"""
LLM caller — uses Google Gemini via the OpenAI-compatible API.

Gemini base URL: https://generativelanguage.googleapis.com/v1beta/openai/
Free tier: ~1M tokens/day with gemini-2.0-flash (get key at aistudio.google.com)
"""
import json
import re
from typing import Any, AsyncGenerator, Optional

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.core.logging import get_logger
from app.rag.prompt_builder import SYSTEM_PROMPT

settings = get_settings()
log = get_logger(__name__)

_client: Optional[AsyncOpenAI] = None


def get_llm_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.gemini_api_key,
            base_url=settings.gemini_base_url,
        )
    return _client


def _extract_json(text: str) -> dict[str, Any]:
    """Extract JSON object from LLM response (strips markdown fences)."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    log.error("llm_json_parse_failed", response_preview=text[:200])
    return {
        "probable_cause": "Unable to parse LLM response",
        "severity": "unknown",
        "runbook_steps": [],
        "escalation_path": "Escalate to on-call SRE",
        "auto_remediation_suggestion": "none",
        "auto_remediation_details": "",
    }


async def call_claude(
    messages: list[dict[str, Any]],
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """
    Non-streaming LLM call via Gemini OpenAI-compat API.
    Returns parsed JSON playbook dict.
    """
    client = get_llm_client()
    max_tok = max_tokens or settings.llm_max_tokens

    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    response = await client.chat.completions.create(
        model=settings.llm_model,
        max_tokens=max_tok,
        messages=full_messages,
    )

    raw_text = response.choices[0].message.content or ""
    log.debug(
        "llm_response_received",
        model=response.model,
        input_tokens=response.usage.prompt_tokens if response.usage else 0,
        output_tokens=response.usage.completion_tokens if response.usage else 0,
    )

    parsed = _extract_json(raw_text)
    parsed["_raw"] = raw_text
    parsed["_model"] = response.model
    return parsed


async def stream_claude(
    messages: list[dict[str, Any]],
    max_tokens: int | None = None,
) -> AsyncGenerator[str, None]:
    """
    Streaming LLM call via Gemini OpenAI-compat API.
    Yields raw text tokens as they arrive.
    """
    client = get_llm_client()
    max_tok = max_tokens or settings.llm_max_tokens

    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    stream = await client.chat.completions.create(
        model=settings.llm_model,
        max_tokens=max_tok,
        messages=full_messages,
        stream=True,
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
