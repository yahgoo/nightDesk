"""Convex persistence layer for NightDesk.

Single responsibility: own every write to the three Convex tables the product
depends on — ``bookings``, ``revenueEvents``, and ``agentRunLogs`` — through a thin
async REST wrapper around the Convex deployment. All other modules call these
helpers instead of touching the network themselves, so the persistence contract
stays in one auditable place.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

CONVEX_URL = os.environ.get("CONVEX_URL", "").rstrip("/")
CONVEX_TOKEN = os.environ.get("CONVEX_AUTH_TOKEN", "")  # optional, for protected funcs
DEFAULT_TIMEOUT = float(os.environ.get("CONVEX_TIMEOUT", "10"))


def _endpoint() -> str:
    # CONVEX_URL is typically https://<deployment>.convex.cloud
    return f"{CONVEX_URL}/api/run"


async def _call(function_path: str, args: list[Any]) -> Any:
    """Call a Convex function via the REST API and return its ``value``."""
    if not CONVEX_URL:
        # No Convex configured yet — surface this loudly but don't crash.
        return {"ok": False, "staged": True, "reason": "CONVEX_URL not configured"}
    payload = {"path": function_path, "args": args, "format": "json"}
    headers = {"Content-Type": "application/json"}
    if CONVEX_TOKEN:
        headers["Authorization"] = f"Bearer {CONVEX_TOKEN}"
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        resp = await client.post(_endpoint(), json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "success":
            return data.get("value")
        return {"ok": False, "error": data}


async def create_booking(booking: dict[str, Any]) -> Any:
    return await _call("bookings:create", [booking])


async def update_booking(booking_id: str, patch: dict[str, Any]) -> Any:
    return await _call("bookings:update", [booking_id, patch])


async def record_revenue_event(event: dict[str, Any]) -> Any:
    return await _call("revenueEvents:create", [event])


async def persist_run_log(record: dict[str, Any]) -> Any:
    return await _call("agentRunLogs:create", [record])
