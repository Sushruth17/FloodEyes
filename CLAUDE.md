# Flood Eyes

Live street-level flood depth from crowdsourced photos. **"Flood Hub forecasts the flood. Flood Eyes measures it."**
Entry for the Google Cloud AI Builder Cup 2026 (Hack2skill, theme: Sustainability & Social Impact). The full plan is in `PLAN.md`.

## Status
- Plan v2 is awaiting the user's approval. **Write no application code until the user approves `PLAN.md`.**
- Target submission is **Oct 17, 2026** (official deadline Oct 18). Feature freeze Oct 12, code freeze Oct 15.

## Submission compliance (applies to every decision)
- **AI:** all core intelligence runs on Google AI models (Gemini) and/or Google ADK. **No other model providers anywhere in the product.**
- **Deployment:** the backend runs on **Cloud Run**; the dashboard and report page run on **Firebase Hosting**. Third parties (WhatsApp/Twilio/Meta, Telegram, Open-Meteo, DEM data) are only I/O channels or data sources, never the core.
- **English only:** all code, comments, README, docs, and the deck. Multilingual output inside the product is fine; the demo video needs English captions for it.
- **Judge access:** the dashboard has a public, no-login, read-only view that works in a fresh browser and is seeded with demo data so it's never empty.
- **Submission package:** PDF deck, live URLs, and a public 3-minute video link (YouTube, Vimeo, or Drive) tested in a logged-out browser. Theme: Sustainability & Social Impact.
- **Before any deploy**, check new work against this list (`scripts/precheck.sh` plus `PLAN.md` §8.1). **If something about to be built would break a rule, flag it to the user before writing it.**

## Judging weights
Technical merit & Gen AI 40% · Problem alignment & impact 25% · Innovation 25% · UX 10%. Optimise for a reliable end-to-end demo and measured results, not feature count.

## Key decisions
- **Three thin front ends, one Cloud Run backend:**
  - **Bot:** WhatsApp first (Twilio sandbox; Meta Cloud API is the production path), with a Telegram fallback. All channels sit behind the `MessagingChannel` adapter interface (`backend/app/channels/`). The WhatsApp attempt was time-boxed to one day.
  - **Mobile web report page:** vanilla TS, <100 KB, compression on the device, retry on upload.
  - **Dashboard:** React + Maps JS, a public read-only view, and a passcode-gated operator mode.
- **Models:** `gemini-3.8-flash` (per-photo work), `gemini-3.1-pro-preview` (control room, falls back to Flash), `gemini-embedding-2-preview` (duplicate detection). IDs live only in config.
- **Pipeline:** Pub/Sub → worker. Steps: blur (Cloud Vision) → locate → DepthAgent → TrustAgent → fusion (geohash-7, trust × confidence × time decay) → spread → reply.
- **Code vs agents:** passability, fusion, routing filters, and the spread heuristic are deterministic code. Gemini handles judgment (depth, trust, explanations, the control room).
- **Routes API can't avoid areas:** filter or rank the alternatives, with a via-waypoint detour fallback. Predicted-spread areas are a soft penalty only.
- **Water-spread prediction (phase 2):** elevation grid (Elevation API; Copernicus GLO-30 as fallback) plus steepest-descent and ponding heuristics, rainfall, and Flood Hub prior → predicted areas at +30 and +60 min, each explained by Gemini. **This is not a hydrological model.**
- **Flood Hub API** is waitlist-only, so it sits behind the `FloodForecastProvider` interface (live or mock).
- **Privacy:** faces and number plates are blurred before storage. Raw media and videos are never kept. Sender IDs are salted hashes; reply addresses are encrypted.
- **Optional:** 5–10 s video clips (first on the cut list).
- **Roadmap only:** rescue triage, Gemini Live voice line, native Android app, WhatsApp production rollout, proactive photo requests.

## Coding conventions
- **Python 3.12**, `uv`, FastAPI (async), Pydantic v2, `ruff` (lint and format), type hints everywhere, `pytest`.
- Every Gemini output is validated against a Pydantic schema. Prompts are versioned files in `backend/app/agents/prompts/` (`depth_v2.md` …), and each report records `promptVersion` and `model`.
- Every external call has a timeout, retries, and a fallback. A model failure degrades the report (`insufficient_evidence` / `needs_review`) and never crashes the pipeline.
- Secrets live only in Secret Manager or a local `.env`, never in the repo. Browser keys are referrer-restricted.
- Frontend: TypeScript strict, ESLint and Prettier. The dashboard is React; the report page is vanilla TS kept small.
- New channels go in `channels/`, and new city settings in `backend/cities/*.yaml`. Don't hard-code city data.

## Run / test / deploy (planned; update once scaffolded)
```bash
# backend
cd backend && uv sync && uv run uvicorn app.main:app --reload      # API mode
uv run pytest                                                        # tests
# frontend
cd web/dashboard && npm i && npm run dev
cd web/report && npm i && npm run dev
# eval
uv run python eval/run_depth_eval.py --models gemini-3.8-flash --prompts v1,v2 --split dev
# demo
uv run python scripts/replay.py --scenario blr_silkboard --speed 10x
# deploy (runs precheck.sh first)
./scripts/deploy.sh
```
