# NightDesk

After-hours booking nurturer for heartland Singapore SMEs (TCM clinics, dentists,
tuition centres) whose customers message late at night on Telegram. Built for the
Hermes Buildathon, Track 03: AI as Agency.

## Architecture

```
Telegram (aiogram)
  -> Manager Agent      (intent classification: new booking / cancel / reschedule / FAQ)
    -> Booking Specialist (extract service+time+urgency, call tools, TTS confirm)
      -> Hermes HTTP client (check_slots / create_booking / cancel_booking / reschedule_booking)
        -> SME portal (Playwright automation via the remote nightdesk Hermes gateway)
      -> Convex   (bookings, revenueEvents, agentRunLogs)
      -> ElevenLabs TTS -> Telegram voice-note confirmation
      -> LinkUp   (fallback lookup for out-of-menu requests)
  -> Cloudflare Pages/Workers hosts the metrics/status view
```

## Agent org structure (scored)

- **Manager Agent** (`app/manager_agent.py`) — classifies intent, delegates.
- **Booking Specialist** (`app/booking_specialist.py`) — extracts details, runs tools,
  persists to Convex, triggers voice confirmation.
- Every decision and tool call is logged as structured JSON via `app/logging_utils.py`
  (local `logs/agent_runs.jsonl`) **and** pushed to the Convex `agentRunLogs` table, so
  booking context survives the full handoff chain.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in real keys
```

## Running

- Bot (polling):  `python -m app.telegram_bot`
- Web server:     `python -m app.server`   (serves `/health`, `/api/status`, `/webhook/telegram`)
- Convex schema:  `npx convex dev`  (deploys `convex/schema.js` + function modules)

## Environment variables

See `.env.example` — `OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `TELEGRAM_BOT_TOKEN`,
`TELEGRAM_ALLOWED_USERS`, `CONVEX_DEPLOYMENT`, `CONVEX_URL`, `ELEVENLABS_API_KEY`,
`LINKUP_API_KEY`, `CLOUDFLARE_API_TOKEN`, `DODO_API_KEY` (stretch), plus
`HERMES_GATEWAY_URL` for the remote portal gateway.

## Integrations (buildathon power-ups)

All four power-up surfaces are wired and exercised by `scripts/verify_integrations.py`
(real calls when credentials are present, honest `staged` status otherwise):

- **Convex** — `app/convex_client.py` writes `bookings`, `revenueEvents`, `agentRunLogs`.
  Schema + mutations live in `convex/`. Deploy with `npx convex dev` (needs
  `CONVEX_URL` / `CONVEX_DEPLOYMENT`).
- **ElevenLabs** — `BookingSpecialist._voice_confirm` generates a voice-note
  confirmation when `ELEVENLABS_API_KEY` is set.
- **LinkUp** — `BookingSpecialist._linkup_fallback` does an out-of-menu lookup when
  `LINKUP_API_KEY` is set.
- **Cloudflare** — the status/metrics dashboard lives in `cloudflare/` (static
  `public/index.html` + `functions/api/status.js` proxy). Deploy with
  `wrangler pages deploy cloudflare/public` (set `BACKEND_URL` to the live backend).

## Verify integrations

```bash
python scripts/verify_integrations.py   # reports configured + attempts real calls
```

## Deploy (ship to a live URL)

The app is packaged for any container/long-running host:

```bash
# Container
docker build -t nightdesk . && docker run -p 8000:8000 --env-file .env nightdesk

# Or a PaaS (Render/Fly/Railway/Heroku) — Procfile launches the FastAPI server
git push   # host builds from Dockerfile / Procfile, exposes $PORT
```

Then point Telegram at the public URL:

- Webhook mode: `POST https://<your-host>/webhook/telegram` (configure via BotFather or your bot setup).
- Or polling mode: run `python -m app.telegram_bot` as a separate worker.

The Cloudflare dashboard (`cloudflare/`) deploys independently:

```bash
wrangler pages deploy cloudflare/public   # set BACKEND_URL to the host above
```

Health: `GET /health` → `{"status":"ok"}`. Status: `GET /api/status`.

## Status / honesty note

When external services (Hermes gateway, Convex, LLM keys) are not configured, the
pipeline degrades gracefully and returns **clearly-labelled `staged` responses** rather
than faking success. This keeps the buildathon scoring boundary honest.
