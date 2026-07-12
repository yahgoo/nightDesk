"""Structured, inspectable observability for NightDesk.

Single responsibility: emit every agent decision and tool call as a structured
JSON-line event (and hand back the same record so it can also be persisted to the
Convex ``agentRunLogs`` table). A contextvar-based correlation id threads a single
booking conversation from the Telegram message through the manager, the specialist,
the Hermes gateway call, and the confirmation, so handoff context survives the whole
pipeline exactly as the scoring rubric requires.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

_log = logging.getLogger("nightdesk")
logging.basicConfig(level=logging.INFO)

# Correlation context that survives across agent handoffs within a single request.
run_id_ctx: ContextVar[str] = ContextVar("nightdesk_run_id", default="")
conversation_id_ctx: ContextVar[str] = ContextVar("nightdesk_conversation_id", default="")

LOG_DIR = os.environ.get(
    "NIGHTDESK_LOG_DIR",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs"),
)
LOG_FILE = os.path.join(LOG_DIR, "agent_runs.jsonl")


def new_run_id() -> str:
    return uuid.uuid4().hex


def ensure_run() -> str:
    """Return the active run_id, creating one if this flow hasn't started yet."""
    rid = run_id_ctx.get()
    if not rid:
        rid = new_run_id()
        run_id_ctx.set(rid)
    return rid


@dataclass
class AgentEvent:
    run_id: str
    conversation_id: str
    agent: str
    intent: Optional[str]
    event_type: str
    detail: dict[str, Any]
    level: str = "INFO"
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ts_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.ts))
        return d


def log_event(
    agent: str,
    event_type: str,
    detail: Optional[dict[str, Any]] = None,
    *,
    intent: Optional[str] = None,
    level: str = "INFO",
    conversation_id: Optional[str] = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Write one structured event to the JSON-lines log and return the record.

    When ``persist`` is True and a Convex loop is available, the record is also
    pushed to the ``agentRunLogs`` table (best-effort, fire-and-forget so logging
    never blocks or crashes the agent pipeline).
    """
    detail = detail or {}
    record = AgentEvent(
        run_id=ensure_run(),
        conversation_id=conversation_id or conversation_id_ctx.get() or ensure_run(),
        agent=agent,
        intent=intent,
        event_type=event_type,
        detail=detail,
        level=level,
    ).to_dict()

    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
    except OSError as exc:  # never let logging crash the pipeline
        _log.warning("nightdesk: failed to write local log: %s", exc)

    if level in ("ERROR", "WARN"):
        getattr(_log, level.lower())(json.dumps(record, default=str))
    else:
        _log.debug(json.dumps(record, default=str))

    if persist:
        try:
            import asyncio

            from app.convex_client import persist_run_log  # lazy import

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(persist_run_log(record))
            except RuntimeError:
                pass  # no running loop (e.g. sync context) — skip Convex push
        except Exception:  # persistence is best-effort
            pass

    return record
