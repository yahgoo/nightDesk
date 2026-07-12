"""Booking Specialist Agent for NightDesk.

Single responsibility: given a classified intent, extract the structured booking
details the SME portal needs (service, date/time, urgency, customer), execute the
matching Hermes gateway tool (create / cancel / reschedule), persist the outcome to
Convex, and produce an ElevenLabs voice-note confirmation — using LinkUp as a
fallback lookup only when the request falls outside the known service menu.
"""
from __future__ import annotations

import json
import os
from typing import Any

import httpx

from app.convex_client import create_booking as convex_create_booking
from app.hermes_client import cancel_booking, create_booking, reschedule_booking
from app.llm_client import call_model
from app.logging_utils import log_event

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
LINKUP_API_KEY = os.environ.get("LINKUP_API_KEY", "")

EXTRACTION_PROMPT = (
    "You are the NightDesk Booking Specialist. Extract booking details from the "
    "user message into strict JSON: {\"service\": <string|null>, "
    "\"date\": <YYYY-MM-DD|null>, \"time\": <HH:MM|null>, "
    "\"urgency\": <low|normal|high>, \"customer_name\": <string|null>, "
    "\"out_of_menu\": <bool>, \"missing\": [<fields needed>]}. "
    "Set out_of_menu true if the requested service is not a typical TCM/dental/"
    "tuition service."
)


class BookingSpecialist:
    """Turns a classified intent into a persisted, confirmed booking action."""

    async def handle(self, intent: str, text: str, *, telegram_user_id: str) -> str:
        log_event(
            "booking_specialist", "intake_start",
            {"intent": intent, "text": text, "telegram_user_id": telegram_user_id},
            intent=intent,
        )
        if intent == "new_booking":
            return await self._new_booking(text, telegram_user_id)
        if intent == "cancel":
            return await self._cancel(text, telegram_user_id)
        if intent == "reschedule":
            return await self._reschedule(text, telegram_user_id)
        return "Sorry, I couldn't process that request."

    async def _extract(self, text: str) -> dict[str, Any]:
        raw = await call_model(EXTRACTION_PROMPT, text, json_mode=True)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {
                "service": None, "date": None, "time": None,
                "urgency": "normal", "customer_name": None,
                "out_of_menu": False, "missing": ["service", "date", "time"],
            }

    async def _new_booking(self, text: str, telegram_user_id: str) -> str:
        details = await self._extract(text)
        if details.get("out_of_menu"):
            await self._linkup_fallback(text, details)

        result = await create_booking({
            "service": details.get("service"),
            "date": details.get("date"),
            "time": details.get("time"),
            "urgency": details.get("urgency", "normal"),
            "telegram_user_id": telegram_user_id,
            "customer_name": details.get("customer_name"),
        })
        await convex_create_booking({
            "service": details.get("service"),
            "slot_time": f"{details.get('date')}T{details.get('time')}",
            "urgency": details.get("urgency", "normal"),
            "telegram_user_id": telegram_user_id,
            "status": "confirmed" if not result.get("staged") else "staged",
            "source": "telegram",
        })
        await self._voice_confirm(details, result)

        if result.get("staged"):
            return (
                "(STAGED) Booking recorded against the mock portal. I've noted "
                f"your {details.get('service')} appointment on {details.get('date')} "
                f"at {details.get('time')}. Real portal write pending gateway config."
            )
        return (
            f"Booked! Your {details.get('service')} appointment is confirmed for "
            f"{details.get('date')} at {details.get('time')}. "
            "I've sent a voice note to confirm."
        )

    async def _cancel(self, text: str, telegram_user_id: str) -> str:
        details = await self._extract(text)
        result = await cancel_booking(details.get("booking_id") or text)
        return ("Cancellation request sent." if not result.get("staged")
                else "(STAGED) Cancellation recorded against the mock portal.")

    async def _reschedule(self, text: str, telegram_user_id: str) -> str:
        details = await self._extract(text)
        result = await reschedule_booking(
            details.get("booking_id") or text,
            f"{details.get('date')}T{details.get('time')}",
        )
        return ("Reschedule request sent." if not result.get("staged")
                else "(STAGED) Reschedule recorded against the mock portal.")

    async def _voice_confirm(self, details: dict[str, Any], result: dict[str, Any]) -> None:
        if not ELEVENLABS_API_KEY:
            log_event("booking_specialist", "tts_skipped",
                      {"reason": "ELEVENLABS_API_KEY not configured"}, intent="new_booking")
            return
        tts_text = (
            f"Hi, this is NightDesk. Your {details.get('service')} appointment "
            f"on {details.get('date')} at {details.get('time')} is confirmed. "
            "See you soon!"
        )
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
                    json={"text": tts_text, "model_id": "eleven_monolingual_v1"},
                    headers={"xi-api-key": ELEVENLABS_API_KEY,
                             "Content-Type": "application/json"},
                )
                resp.raise_for_status()
                log_event("booking_specialist", "tts_generated",
                          {"bytes": len(resp.content)}, intent="new_booking")
        except Exception as exc:
            log_event("booking_specialist", "tts_error", {"error": str(exc)},
                      intent="new_booking", level="ERROR")

    async def _linkup_fallback(self, text: str, details: dict[str, Any]) -> None:
        if not LINKUP_API_KEY:
            log_event("booking_specialist", "linkup_skipped",
                      {"reason": "LINKUP_API_KEY not configured"}, intent="new_booking")
            return
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.linkup.so/v1/search",
                    json={"query": text, "depth": "standard"},
                    headers={"Authorization": f"Bearer {LINKUP_API_KEY}"},
                )
                resp.raise_for_status()
                log_event("booking_specialist", "linkup_lookup",
                          {"result": resp.json()}, intent="new_booking")
        except Exception as exc:
            log_event("booking_specialist", "linkup_error", {"error": str(exc)},
                      intent="new_booking", level="ERROR")
