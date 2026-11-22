# Integration plan

## Steam

Steam OpenID is used only to authenticate a user. It does not grant demo-download access. A separate Steam Game Coordinator (GC) integration is required for match-sharing-code workflows. GC access generally requires an authenticated Steam client session; keep this behind a dedicated worker/agent and never request or store a user's Steam password.

## FACEIT

Use the official FACEIT Data API for player and match metadata. Demo URLs are available only when exposed by the API/provider for that match and may expire. Store provider IDs and fetch fresh URLs when needed. API key is a server-side secret.

## Demo processing

Validate file size and extension, store uploads outside the web root, queue parsing, and retain parsed event summaries separately from raw demo files. `demoparser2` can extract event and player data; a complete 2D replay requires map geometry, event timeline and client rendering.

## Free deployment constraints

Do not rely on ephemeral web-service disks for durable demo storage. Keep demo uploads disabled until persistent storage is configured. Large parsing and FFmpeg rendering are worker workloads and may exceed free-tier CPU/time limits.
