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
