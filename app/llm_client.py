"""Shared LLM access for the NightDesk agents.

Single responsibility: provide one async ``call_model`` entry point that targets the
remote Hermes "nightdesk" model (tencent/hy3:free via OpenRouter) and automatically
falls back to OpenAI when ``OPENAI_API_KEY`` is set and the primary call fails or is
rate-limited. Both the Manager and the Booking Specialist import this so the model
contract lives in exactly one place instead of being duplicated across agents.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
PRIMARY_MODEL = os.environ.get("NIGHTDESK_MODEL", "tencent/hy3:free")
FALLBACK_MODEL = os.environ.get("NIGHTDESK_FALLBACK_MODEL", "gpt-4o-mini")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "30"))


async def call_model(
    system: str,
    user: str,
    *,
    json_mode: bool = False,
    temperature: float = 0.2,
) -> str:
    """Return the model's text response, trying OpenRouter (hy3) then OpenAI."""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    # 1) primary: OpenRouter / hy3:free
    if OPENROUTER_API_KEY:
        try:
            body: dict[str, Any] = {
                "model": PRIMARY_MODEL,
                "messages": messages,
                "temperature": temperature,
            }
            if json_mode:
                body["response_format"] = {"type": "json_object"}
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                resp = await client.post(
                    OPENROUTER_URL, json=body,
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "HTTP-Referer": "https://nightdesk.app",
                        "X-Title": "NightDesk",
                    },
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except Exception:
            pass  # fall through to OpenAI
    # 2) fallback: OpenAI
    if OPENAI_API_KEY:
        body = {
            "model": FALLBACK_MODEL,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.post(
                OPENAI_URL, json=body,
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
    # No keys configured: return a clearly labelled stub so the pipeline still runs.
    return '{"staged": true, "note": "No LLM API key configured; returning stub response."}'
