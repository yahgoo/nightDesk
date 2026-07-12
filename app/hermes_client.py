"""HTTP client to the remote Hermes "nightdesk" gateway.

Single responsibility: translate the product's four booking operations —
check_slots, create_booking, cancel_booking, reschedule_booking — into calls
against the remote Hermes gateway, which drives the real SME portal via Playwright.
Every call is logged through ``logging_utils``; if the gateway is unreachable or
unconfigured the client returns a clearly-labelled ``staged`` payload rather than
silently faking success, so the buildathon scoring boundary stays honest.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from app.logging_utils import log_event

HERMES_GATEWAY_URL = os.environ.get("HERMES_GATEWAY_URL", "").rstrip("/")
DEFAULT_TIMEOUT = float(os.environ.get("HERMES_TIMEOUT", "30"))


def _configured() -> bool:
    return bool(HERMES_GATEWAY_URL)


async def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not _configured():
        log_event(
            "hermes_client", "gateway_unconfigured",
            {"path": path, "payload": payload}, level="WARN",
        )
        return {
            "ok": False,
            "staged": True,
            "note": (
                "Hermes gateway URL not configured — returning staged response. "
                "Real portal writes require HERMES_GATEWAY_URL to point at the "
                "remote nightdesk Hermes profile gateway."
            ),
        }
    url = f"{HERMES_GATEWAY_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            log_event("hermes_client", "tool_call", {"path": path, "payload": payload})
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            log_event("hermes_client", "tool_result",
                      {"path": path, "ok": data.get("ok", True)})
            return data
    except Exception as exc:
        log_event("hermes_client", "tool_error",
                  {"path": path, "error": str(exc)}, level="ERROR")
        return {
            "ok": False, "staged": True,
            "note": f"Hermes gateway call failed ({exc}); returning staged response.",
        }


async def check_slots(business_id: str, date: str) -> dict[str, Any]:
    return await _post("/check_slots", {"business_id": business_id, "date": date})


async def create_booking(booking: dict[str, Any]) -> dict[str, Any]:
    return await _post("/create_booking", booking)


async def cancel_booking(booking_id: str) -> dict[str, Any]:
    return await _post("/cancel_booking", {"booking_id": booking_id})


async def reschedule_booking(booking_id: str, new_slot: str) -> dict[str, Any]:
    return await _post("/reschedule_booking",
                       {"booking_id": booking_id, "new_slot": new_slot})
