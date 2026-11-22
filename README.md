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
