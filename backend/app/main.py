import base64
import hashlib
import hmac
import json
import re
import time
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CS2 DEMO HUB API"
    app_env: str = "production"
    frontend_origin: str = "http://localhost:3000"
    faceit_api_key: str | None = None
    faceit_download_token: str | None = None
    steam_openid_enabled: bool = False
    steam_openid_return_url: str | None = None
    steam_openid_realm: str | None = None
    session_secret: str | None = None
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
app = FastAPI(title=settings.app_name, version="0.2.0", description="CS2 match and demo platform API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

FACEIT_API = "https://open.faceit.com/data/v4"
STEAM_OPENID = "https://steamcommunity.com/openid/login"
COOKIE_NAME = "cs2dh_session"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _make_session(steam_id: str) -> str:
    if not settings.session_secret:
        raise HTTPException(status_code=503, detail="Steam login session secret is not configured")
    payload = _b64(json.dumps({"steam_id": steam_id, "iat": int(time.time())}).encode())
    signature = hmac.new(settings.session_secret.encode(), payload.encode(), hashlib.sha256).digest()
    return payload + "." + _b64(signature)


def _read_session(token: str | None) -> dict | None:
    if not token or not settings.session_secret or "." not in token:
        return None
    payload, signature = token.rsplit(".", 1)
    expected = _b64(hmac.new(settings.session_secret.encode(), payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if int(time.time()) - int(data.get("iat", 0)) > 30 * 86400:
            return None
        return data
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


async def _faceit_get(path: str, params: dict | None = None) -> dict:
    if not settings.faceit_api_key:
        raise HTTPException(status_code=503, detail="FACEIT_API_KEY is not configured")
    headers = {"Authorization": f"Bearer {settings.faceit_api_key}", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(f"{FACEIT_API}{path}", headers=headers, params=params)
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="FACEIT resource not found")
    if response.status_code in (401, 403):
        raise HTTPException(status_code=502, detail="FACEIT rejected the API key or its permissions")
    if response.status_code == 429:
        raise HTTPException(status_code=503, detail="FACEIT API rate limit reached; retry later")
    if response.is_error:
        raise HTTPException(status_code=502, detail=f"FACEIT API returned HTTP {response.status_code}")
    return response.json()


@app.get("/", tags=["system"])
async def root():
    return {"service": "CS2 DEMO HUB API", "docs": "/docs", "health": "/health"}


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "service": "cs2-demo-hub-api", "version": "0.2.0"}


@app.get("/api/v1/status", tags=["system"])
async def status():
    steam_ready = bool(settings.steam_openid_enabled and settings.steam_openid_return_url and settings.session_secret)
    return {
        "project": "CS2 DEMO HUB",
        "phase": "provider-integration",
        "integrations": {
            "steam_openid": "ready" if steam_ready else "needs_configuration",
            "steam_match_provider": "requires_authenticated_steam_client_worker",
            "faceit_data_api": "configured" if settings.faceit_api_key else "needs_api_key",
            "faceit_downloads_api": "configured" if settings.faceit_download_token else "access_application_required",
            "demo_parser": "not_deployed",
            "video_renderer": "not_deployed",
        },
        "capabilities": ["health", "status", "faceit_player_search", "faceit_match_history", "steam_openid_login"],
    }


@app.get("/api/v1/matches", tags=["matches"])
async def list_matches(source: str = "all"):
    return {"items": [], "source": source, "configured": False,
            "message": "Steam Game Coordinator and FACEIT player account must be connected before match history is shown."}


@app.get("/api/v1/faceit/players", tags=["faceit"])
async def faceit_player_search(nickname: str = Query(min_length=2, max_length=32)):
    data = await _faceit_get("/search/players", {"nickname": nickname, "game": "cs2", "limit": 10})
    items = []
    for player in data.get("items", []):
        items.append({
            "player_id": player.get("player_id"),
            "nickname": player.get("nickname"),
            "avatar": player.get("avatar"),
            "country": player.get("country"),
            "games": player.get("games", {}),
        })
    return {"items": items, "source": "FACEIT Data API"}


@app.get("/api/v1/faceit/players/{player_id}/matches", tags=["faceit"])
async def faceit_player_matches(player_id: str, limit: int = Query(default=20, ge=1, le=100)):
    data = await _faceit_get(f"/players/{player_id}/history", {"game": "cs2", "offset": 0, "limit": limit})
    items = []
    for match in data.get("items", []):
        items.append({
            "match_id": match.get("match_id"),
            "started_at": match.get("started_at"),
            "finished_at": match.get("finished_at"),
            "game_mode": match.get("game_mode"),
            "map": (match.get("demo") or {}).get("map") if isinstance(match.get("demo"), dict) else None,
            "demo_available": bool(match.get("demo_url") or match.get("demo_urls")),
        })
    return {"items": items, "source": "FACEIT Data API", "player_id": player_id}


@app.get("/api/v1/faceit/matches/{match_id}", tags=["faceit"])
async def faceit_match_details(match_id: str):
    return await _faceit_get(f"/matches/{match_id}")


@app.get("/api/v1/faceit/matches/{match_id}/demo-download-url", tags=["faceit"])
async def faceit_demo_download_url(match_id: str):
    match = await _faceit_get(f"/matches/{match_id}")
    demo_values = match.get("demo_url") or match.get("demo_urls") or []
    if isinstance(demo_values, str):
        demo_values = [demo_values]
    if not demo_values:
        raise HTTPException(status_code=404, detail="FACEIT has not exposed a demo resource for this match")
    if not settings.faceit_download_token:
        raise HTTPException(status_code=403, detail="FACEIT Downloads API access token is required; apply for access at FACEIT Developers")
    resource_url = demo_values[0]
    headers = {"Authorization": f"Bearer {settings.faceit_download_token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post("https://open.faceit.com/download/v2/demos/download",
                                     headers=headers, json={"resource_url": resource_url})
    if response.is_error:
        raise HTTPException(status_code=502, detail=f"FACEIT Downloads API returned HTTP {response.status_code}")
    payload = response.json().get("payload", {})
    download_url = payload.get("download_url")
    if not download_url:
        raise HTTPException(status_code=502, detail="FACEIT did not return a signed download URL")
    return {"download_url": download_url, "expires_or_access": "provider-controlled", "match_id": match_id}


@app.get("/api/v1/auth/steam/login", tags=["steam"])
async def steam_login():
    if not (settings.steam_openid_enabled and settings.steam_openid_return_url and settings.steam_openid_realm):
        raise HTTPException(status_code=503, detail="Steam OpenID callback URL and realm are not configured")
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "checkid_setup",
        "openid.return_to": settings.steam_openid_return_url,
        "openid.realm": settings.steam_openid_realm,
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }
    return RedirectResponse("https://steamcommunity.com/openid/login?" + urlencode(params), status_code=302)


@app.get("/api/v1/auth/steam/callback", tags=["steam"])
async def steam_callback(request: Request):
    query = dict(request.query_params)
    if query.get("openid.mode") != "id_res":
        raise HTTPException(status_code=400, detail="Steam OpenID authentication was not completed")
    if query.get("openid.return_to") != settings.steam_openid_return_url:
        raise HTTPException(status_code=400, detail="Steam OpenID return URL mismatch")
    claimed_id = query.get("openid.claimed_id", "")
    identity = query.get("openid.identity", "")
    match = re.fullmatch(r"https?://steamcommunity\.com/openid/id/(\d{17})", claimed_id)
    if not match or identity != claimed_id:
        raise HTTPException(status_code=400, detail="Invalid Steam identity")
    verification = {key: value for key, value in query.items() if key.startswith("openid.")}
    verification["openid.mode"] = "check_authentication"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(STEAM_OPENID, data=verification)
    if response.is_error or "is_valid:true" not in response.text.replace("\\r", "").replace("\\n", ""):
        raise HTTPException(status_code=401, detail="Steam could not verify the OpenID assertion")
    steam_id = match.group(1)
    target = settings.frontend_origin.rstrip("/") + "/?steam=connected"
    result = RedirectResponse(target, status_code=303)
    result.set_cookie(COOKIE_NAME, _make_session(steam_id), httponly=True, secure=True,
                      samesite="none", max_age=30 * 86400, path="/")
    return result


@app.get("/api/v1/auth/me", tags=["auth"])
async def auth_me(request: Request):
    session = _read_session(request.cookies.get(COOKIE_NAME))
    if not session:
        return {"authenticated": False, "steam_id": None}
    return {"authenticated": True, "steam_id": session["steam_id"]}


@app.post("/api/v1/auth/logout", tags=["auth"])
async def auth_logout():
    result = {"ok": True}
    response = RedirectResponse(settings.frontend_origin, status_code=303)
    response.delete_cookie(COOKIE_NAME, path="/", secure=True, httponly=True, samesite="none")
    return response
