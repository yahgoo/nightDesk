"""Local demo of the NightDesk happy path.

Runs a sample late-night booking through the agent chain and prints the structured
log trail so you can see the manager->specialist->gateway->Convex handoff. Uses the
deterministic (offline) fallbacks when no LLM keys are set, and the staged Hermes
gateway when HERMES_GATEWAY_URL is unset — so it always runs and is clearly labelled.

Run with:  python scripts/run_demo.py
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import manager_agent
from app.logging_utils import LOG_FILE


async def main():
    m = manager_agent.ManagerAgent()
    open(LOG_FILE, "w").close()  # start the demo with a clean log trail
    samples = [
        "Hi, I need an urgent TCM acupuncture session tomorrow at 9pm",
        "Can I reschedule my dental checkup to Friday 3pm?",
        "Cancel my tuition slot please",
    ]
    for text in samples:
        print("\n=== USER:", text)
        reply = await m.handle("demo-user", text)
        print("BOT  :", reply)

    print("\n=== Agent run log (this session) ===")
    try:
        with open(LOG_FILE) as fh:
            for line in fh:
                if not line.strip():
                    continue
                rec = json.loads(line)
                print(f"  [{rec['agent']:<17}] {rec['event_type']:<16} "
                      f"intent={rec.get('intent')} run={rec['run_id'][:8]}")
    except FileNotFoundError:
        print("  (no log file yet)")


if __name__ == "__main__":
    asyncio.run(main())
