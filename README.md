# CS2 DEMO HUB

Multilingual platform foundation for Counter-Strike 2 demo discovery, downloads, parsing and match analytics.

## Current status

Phase 1 foundation: API health/status, provider boundaries, and multilingual web shell. Steam Game Coordinator demo retrieval and FACEIT demo access are separate integrations and require their own credentials/runtime capabilities.

## Architecture

- `backend/` — FastAPI service and provider interfaces
- `frontend/` — Next.js web application (Russian, Kazakh, English)
- `docs/` — architecture and integration notes

## Local development

Backend: `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload`

Frontend: `cd frontend && npm install && npm run dev`

Copy `.env.example` to `.env` and configure credentials. Never commit secrets.

## Free-tier note

Free hosting may sleep and impose CPU, memory, bandwidth, and storage limits. Large demo files and MP4 rendering should run on a separate worker or user-controlled machine; do not promise permanent storage on ephemeral disks.

## Steam match import

- Steam OpenID confirms the account identity; it does not expose the match list.
- The authenticated match-sharing endpoint can walk forward from a user-supplied recent Valve share code using the user's Game Authentication Code and a Steam Web API key.
- `POST /api/v1/steam/matches/decode` validates and decodes a `CSGO-` match share code into Valve's match, reservation, and TV-port identifiers.
- The web app keeps manually imported share codes in that browser's local storage and provides a `steam://` launch link to open the replay in the installed CS2 client.
- The decoder does not fabricate map names, scores, player lists, or demo URLs. Full metadata and cloud demo downloads require a separate Steam Game Coordinator client connection. Steam OpenID and a Steam Web API key alone cannot perform that step.
- The Game Authentication Code is sent only to the API over HTTPS for the explicit match-history request; it must never be committed, logged, or pasted into chat. Revoke it in Steam Support if it is exposed.



## Persistent projects and match history

- PostgreSQL storage is optional and enabled with `DATABASE_URL`. The API creates its `projects` and `matches` tables on startup.
- Authenticated Steam and FACEIT identities are isolated by provider and account ID. Project list, create, read, update, and delete routes are available under `/api/v1/projects`.
- The authenticated FACEIT match-history route stores the returned public match metadata when PostgreSQL is connected. Steam next-share-code imports store decoded identifiers, never the Game Authentication Code.
- Without `DATABASE_URL`, persistent endpoints return a clear 503 response rather than pretending that data was saved.
- Render's free PostgreSQL instance currently has a 30-day expiry. It is suitable for a temporary prototype only; do not store irreplaceable data until a durable free database and backup policy are confirmed.


## CS2 demo library limits

- Demo uploads require a signed-in Steam or FACEIT account.
- Each `.dem` upload is limited to 100 MB.
- Each account can store up to 250 MB of demos; the shared demo store is capped at 700 MB to protect the free PostgreSQL instance.
- Demo files are account-scoped and can be listed, downloaded, or deleted by their owner.
- Parsed kill totals are derived from recorded `player_death` events with a valid attacker; event totals and kill totals are kept separate.
