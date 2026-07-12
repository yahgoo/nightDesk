# NightDesk — Agent Context

## What this is
NightDesk is an after-hours booking nurturer for heartland Singapore SMEs
(TCM clinics, dentists, tuition centers) whose customers message late at
night on Telegram. Built for the Hermes Buildathon, Track 03: AI as Agency.

## Track scoring — build to this, not around it
- Root parameter: working product shipping real output on a real surface (20x).
  Staged/mocked portal caps us at L3. Real portal writes = L4/L5.
- Agent org structure (5x): must have a MANAGER agent that delegates to
  SPECIALIST agents. No monolithic single-agent design.
- Observability (7x): every agent action and tool call must be logged in
  a structured, inspectable way (JSON lines or a Convex table), not print().
- Agent handoffs/memory (2x): booking context must survive from Telegram
  message -> manager -> specialist -> Hermes call -> confirmation.
- Power-ups (+25 each, real use only): Convex, ElevenLabs, LinkUp,
  Cloudflare. Dodo Payments is a stretch goal, cut first if behind schedule.

## Non-negotiable architecture
Telegram (aiogram/python-telegram-bot)
  -> Manager Agent (intent classification: new booking / cancel / reschedule / FAQ)
  -> Booking Specialist Agent (extracts service, time, urgency; calls tools)
  -> Hermes HTTP client (check_slots, create_booking, cancel_booking, reschedule_booking)
  -> SME portal (Playwright automation via existing Hermes gateway)
  -> Convex (bookings, revenueEvents, agentRunLogs tables)
  -> ElevenLabs TTS -> Telegram voice-note confirmation
  -> LinkUp tool call (fallback lookup when request is outside known service menu)
  -> Cloudflare Pages/Workers hosts the metrics/status view

## Tech stack (locked, do not deviate without asking)
- Python 3.12
- Bot: aiogram (async)
- Backend/API: FastAPI
- Agent orchestration: manager + specialist pattern, model access via
  the remote Hermes "nightdesk" profile -> OpenRouter tencent/hy3:free
  (coding + low-stakes), fallback to OpenAI (env: OPENAI_API_KEY) for
  the critical booking-intent extraction step if hy3 tool-calling is
  unreliable or rate-limited.
- Persistence: Convex (NOT SQLite) — tables: bookings, revenueEvents, agentRunLogs
- Voice: ElevenLabs TTS for booking confirmations
- Search fallback tool: LinkUp for out-of-menu queries
- Hosting for dashboard/status page: Cloudflare Pages or Workers
- Payments (stretch only): Dodo Payments checkout for a S$10 deposit

## Env vars (names only, never hardcode secrets)
OPENROUTER_API_KEY, OPENAI_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USERS,
CONVEX_DEPLOYMENT, CONVEX_URL, ELEVENLABS_API_KEY, LINKUP_API_KEY,
CLOUDFLARE_API_TOKEN, DODO_API_KEY (stretch)

## Relationship to the remote Hermes VPS profile
This local repo is the application being built. A separate Hermes
profile named "nightdesk" exists on a remote Tencent VPS
(~/.hermes/profiles/nightdesk/) — it is the agent runtime, configured
to use tencent/hy3:free via OpenRouter, with its own isolated Telegram
bot token and allowed user. It is fully decoupled from the VPS's other
live profile, "signaltable", which must never be touched, restarted,
or reconfigured from this project.

## Working rules for this session
- Build the manager/specialist split FIRST. This is scored explicitly
  and cannot be retrofitted convincingly later.
- Log every agent decision and tool call as structured JSON (or a
  Convex row) from the start — do not add logging as an afterthought.
- Keep the happy path (new booking, 11pm, real service, real time slot)
  rock solid before touching edge cases (cancel/reschedule/FAQ).
- If the real SME portal isn't reachable during the build, mock it
  clearly and label it as staged — do not hide this; flag borderline
  scoring cases honestly.
- Ship to a live URL. No local-only demo.
- Do not touch anything outside this project folder. You have no reason
  to modify the remote VPS, the signaltable profile, or global Hermes
  config from here.
