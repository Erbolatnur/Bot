# Steam CS2 match import — implementation plan

## Current boundary

Steam OpenID proves the SteamID only. It does not return CS2 matchmaking history or demo URLs. A public Steam Web API key is not a substitute for a logged-in CS2 Game Coordinator session.

## Supported Valve flow

Valve's match-sharing flow uses two different values:

- **Game Authentication Code** — grants a third-party service permission to request the account's match history. It is a credential and must be treated as a secret.
- **Match Sharing Code** — identifies a known match and is used as the starting point for the history walk.

Valve announced that GetNextMatchSharingCode must be supplied a match sharing code no more than one month old. The flow is not interchangeable with a demo URL.

## Required architecture

1. User authenticates with Steam OpenID; bind the import to the verified SteamID64.
2. User explicitly starts an import and enters the Game Authentication Code and a recent CSGO- match sharing code over HTTPS.
3. Backend validates format, applies per-user rate limits and sends the values only to Valve's documented match-sharing endpoint. Never log either value.
4. Store only the latest successful Match Sharing Code and non-secret match metadata. Encrypt any credential that must persist; provide a revoke/delete action.
5. Retrieve demo metadata and download URLs only through the supported Valve/CS2 flow. Do not fabricate URLs.
6. For actual demo acquisition and Game Coordinator-only match details, use a dedicated Steam client worker. Do not run a Steam password login inside the public web request process.

## Hosting constraint

The current Render free web service is not a reliable always-on Steam client worker: it may sleep/restart and has no guaranteed persistent local disk. The web app can remain free, but reliable automatic polling and demo storage require a separate always-on worker and persistent storage. Do not silently introduce paid services.

## Security requirements

- Never request Steam password, Steam Guard code, recovery code, or session cookies.
- Never expose the Game Authentication Code in browser logs, API responses, analytics, or application logs.
- Do not store Steam credentials in the signed OpenID cookie.
- Require explicit user consent before importing; allow revocation and deletion.
- Enforce ownership: the authenticated SteamID must match the import target.
- Return clear provider errors; never show sample or invented matches as real data.

## Current implementation status

This repository currently implements Steam OpenID identity only. No Game Coordinator worker, match-history importer, or persistent match database is deployed. FACEIT history is separate and must not be presented as Steam history.


## Implemented API slice (branch only)

The backend now has a stateless endpoint:

- `POST /api/v1/steam/matches/next`
- Requires the existing signed Steam OpenID session cookie.
- Accepts `authentication_code` (Steam Game Authentication Code) and `known_match_code` (CSGO- Match Sharing Code) in a JSON request body over HTTPS.
- Uses the verified session SteamID; the caller cannot choose another SteamID.
- Calls Valve `ICSGOPlayers_730/GetNextMatchSharingCode/v1/` and returns at most the next share code.
- Does not persist either submitted code. The user must submit the returned code in the next request to walk forward through history.
- Requires server environment variable `STEAM_WEB_API_KEY`; it is not configured by this code change.

### Response handling

- HTTP 202: no newer match; return `up_to_date`.
- HTTP 412: reject the supplied match code; do not retry automatically.
- HTTP 403: authentication code rejected.
- HTTP 429/503: stop and retry later; do not loop.
- Other provider errors are surfaced as safe generic errors.

### Remaining before user-facing release

1. Consent text and a secure form are now present in the frontend. Keep the auth code out of URLs, local storage, analytics, and logs.
2. Configure `STEAM_WEB_API_KEY` directly in Render after obtaining a Steam Web API key.
3. CI now runs backend dependency installation + Python compile checks and a Next.js production build. Mocked Valve-response tests are still not implemented.
4. Decide whether to persist only non-secret match metadata. Persistent automatic sync needs encrypted secret handling and a database; neither is included here.
5. This endpoint only walks match-sharing codes. It does not yet fetch full match details or download demo files.


## Frontend form added (branch only)

The multilingual RU/KZ/EN frontend now has a Steam Match Sharing panel. It is disabled until Steam OpenID sign-in is present. It posts both codes in an HTTPS JSON request body, uses a password-style field for the authentication key, does not store the key in local storage, and clears the key after a successful response. It displays the returned next code so the user can continue walking the match-code chain.

This is not yet a complete match-history viewer: the API currently returns the next share code only. Match details, metadata persistence, and demo download are separate implementation stages. A GitHub Actions workflow is now configured; its current run status is visible in the PR checks.


## FACEIT session correction and CI

A review found that the first version of the connected-account history route still depended on an in-memory OAuth session map and that an obsolete duplicate set of FACEIT OAuth routes shadowed the stateless signed-cookie implementation. The obsolete routes and process-local token map have been removed. The history endpoint now reads the signed FACEIT identity cookie and resolves the user's public CS2 history through the configured FACEIT Data API key. The frontend session display now consumes the same stateless identity response.

A GitHub Actions workflow was added for pull requests and the feature branch. It installs backend dependencies and runs Python compile checks, then installs frontend dependencies and runs the Next.js production build. Actual pass/fail status must be confirmed from the workflow run after GitHub starts it.


## Latest verification checkpoint

For commit `8e2da2bf85a0b1924d3e2112c579d770aaf72a8f`, the backend syntax job has passed. The frontend production build is still running at the latest status check. The prior commit's frontend build and backend syntax checks both passed. Render production remains on the previous `main` commit until the pull request is reviewed and merged.
