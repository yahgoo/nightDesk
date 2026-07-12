"""Manager Agent for NightDesk.

Single responsibility: classify each inbound Telegram message into one of the four
intents the product handles — new_booking, cancel, reschedule, or faq — and hand the
message off to the Booking Specialist (or answer the FAQ) while logging the decision
and preserving the correlation id so the specialist and downstream tools inherit the
same conversation context. It is the only entry point the Telegram bot talks to.
"""
from __future__ import annotations

import json
from typing import Optional

from app.booking_specialist import BookingSpecialist
from app.llm_client import call_model
from app.logging_utils import conversation_id_ctx, ensure_run, log_event

SYSTEM_PROMPT = (
    "You are the NightDesk Manager Agent for heartland Singapore SMEs "
    "(TCM clinics, dentists, tuition centres). Classify the user's message into "
    "exactly one intent: new_booking, cancel, reschedule, or faq. "
    "Respond with strict JSON: {\"intent\": <one of the four>, "
    "\"confidence\": <0-1>, \"language\": <en|zh|other>, "
    "\"needs_clarification\": <bool>, \"summary\": <short>}. "
    "If the message is ambiguous, set needs_clarification true and intent faq."
)


class ManagerAgent:
    """Intent classifier that delegates booking work to the Booking Specialist."""

    def __init__(self) -> None:
        self.specialist = BookingSpecialist()

    async def classify(self, text: str) -> dict:
        raw = await call_model(SYSTEM_PROMPT, text, json_mode=True)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {
                "intent": "faq",
                "confidence": 0.0,
                "needs_clarification": True,
                "summary": "could not parse model output",
                "language": "en",
            }

    async def handle(
        self,
        telegram_user_id: str,
        text: str,
        conversation_id: Optional[str] = None,
    ) -> str:
        if conversation_id:
            conversation_id_ctx.set(conversation_id)
        ensure_run()
        classification = await self.classify(text)
        intent = classification.get("intent", "faq")
        log_event(
            "manager_agent", "intent_classified",
            {"text": text, "classification": classification,
             "telegram_user_id": telegram_user_id},
            intent=intent,
        )

        if intent in ("new_booking", "cancel", "reschedule"):
            reply = await self.specialist.handle(
                intent, text, telegram_user_id=telegram_user_id)
        else:
            reply = await self._answer_faq(text)
        return reply

    async def _answer_faq(self, text: str) -> str:
        log_event("manager_agent", "faq_answered", {"text": text}, intent="faq")
        return (
            "Thanks for messaging NightDesk! I can help you book, cancel, or "
            "reschedule an appointment with a TCM clinic, dentist, or tuition "
            "centre. What would you like to do?"
        )
