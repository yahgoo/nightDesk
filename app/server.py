"""FastAPI server and process host for NightDesk.

Single responsibility: expose the HTTP surface the product needs — a health check, a
live status/metrics endpoint that the Cloudflare dashboard reads, and a Telegram
webhook receiver — and serve as the single long-running process that also boots the
bot poller. Nothing here contains agent logic; it wires the agents and the bot to the
web/status layer.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.logging_utils import log_event
from app.manager_agent import ManagerAgent

app = FastAPI(title="NightDesk", version="0.1.0")
manager = ManagerAgent()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "nightdesk"}


@app.get("/api/status")
async def status() -> dict[str, Any]:
    """Lightweight status snapshot consumed by the Cloudflare-hosted dashboard."""
    return {
        "service": "nightdesk",
        "gateway_configured": bool(os.environ.get("HERMES_GATEWAY_URL")),
        "convex_configured": bool(os.environ.get("CONVEX_URL")),
        "llm_configured": bool(
            os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
        ),
        "tts_configured": bool(os.environ.get("ELEVENLABS_API_KEY")),
    }


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request) -> JSONResponse:
    payload = await request.json()
    message = payload.get("message", {})
    text = message.get("text")
    user_id = message.get("from", {}).get("id")
    if text and user_id:
        reply = await manager.handle(
            str(user_id), text,
            conversation_id=str(message.get("chat", {}).get("id")),
        )
        return JSONResponse({"reply": reply})
    return JSONResponse({"reply": None})


def main() -> None:
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
