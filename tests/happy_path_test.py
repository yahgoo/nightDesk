"""End-to-end happy-path test for NightDesk.

Drives a late-night, real-service, real-time-slot booking through the full chain
(Telegram message -> Manager Agent -> Booking Specialist -> check_slots/create_booking
-> Convex) using stubbed gateway + Convex clients so we can assert the REAL (non-staged)
write path and that the whole handoff is captured under a single run_id in the logs.

Run with:  python tests/happy_path_test.py
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force the offline/deterministic path (no LLM keys) for a reproducible test.
os.environ.pop("OPENROUTER_API_KEY", None)
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("HERMES_GATEWAY_URL", None)

from app import booking_specialist, hermes_client, manager_agent, convex_client
from app.logging_utils import LOG_FILE, log_event


captured = {"gateway": None, "convex": None}


async def fake_create_booking(payload):
    captured["gateway"] = payload
    log_event("hermes_client", "tool_call",
              {"path": "/create_booking", "payload": payload})
    log_event("hermes_client", "tool_result",
              {"path": "/create_booking", "ok": True})
    return {"ok": True, "booking_id": "BK_TEST_1", "staged": False}


async def fake_check_slots(business_id, date):
    log_event("hermes_client", "tool_call",
              {"path": "/check_slots", "payload": {"business_id": business_id, "date": date}})
    log_event("hermes_client", "tool_result",
              {"path": "/check_slots", "ok": True})
    return {"ok": True, "slots": ["21:00", "21:30"], "staged": False}


async def fake_convex_create(booking):
    captured["convex"] = booking
    return "convex_id_1"


def main():
    # Stub the external boundaries to simulate a CONFIGURED, working gateway + Convex.
    # booking_specialist binds these names at import time, so patch them there.
    booking_specialist.create_booking = fake_create_booking
    booking_specialist.check_slots = fake_check_slots
    booking_specialist.convex_create_booking = fake_convex_create

    # Start each run with a clean log so assertions are about THIS run only.
    open(LOG_FILE, "w").close()

    async def run():
        m = manager_agent.ManagerAgent()
        return await m.handle(
            "tg-night-1",
            "Hi, I need an urgent TCM acupuncture session tomorrow at 9pm",
        )

    reply = asyncio.run(run())

    assert "Booked" in reply, f"expected confirmation, got: {reply!r}"
    assert captured["gateway"] is not None, "gateway create_booking not called"
    assert captured["convex"] is not None, "Convex booking not persisted"
    assert captured["convex"]["status"] == "confirmed", "status should be confirmed (non-staged)"
    assert captured["convex"]["service"] == "TCM consultation", captured["convex"]
    assert captured["convex"]["slot_time"].endswith("T21:00"), captured["convex"]

    with open(LOG_FILE) as fh:
        lines = [json.loads(l) for l in fh if l.strip()]
    types = {x["event_type"] for x in lines}
    for required in ("intent_classified", "intake_start", "slots_checked",
                     "tool_call", "tool_result"):
        assert required in types, f"missing log event: {required}"

    # The manager -> specialist -> hermes handoff must share ONE run_id.
    shared = {x["run_id"] for x in lines
              if x["event_type"] in ("intent_classified", "intake_start", "tool_call")}
    assert len(shared) == 1, f"handoff run_id not threaded: {shared}"

    print("HAPPY_PATH_OK")
    print("reply     :", reply)
    print("convex    :", captured["convex"])
    print("run_id    :", next(iter(shared)))
    print("log_events:", len(lines))


if __name__ == "__main__":
    main()
