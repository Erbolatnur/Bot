import base64
import hashlib
import importlib.util
import hmac
import json
import re
import secrets
import time
import tempfile
import uuid
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.concurrency import run_in_threadpool

from app import storage


class Settings(BaseSettings):
    app_name: str = "CS2 DEMO HUB API"
    app_env: str = "production"
    frontend_origin: str = "http://localhost:3000"
    faceit_api_key: str | None = None
    faceit_download_token: str | None = None
    faceit_oauth_client_id: str | None = None
    faceit_oauth_client_secret: str | None = None
    faceit_oauth_redirect_url: str | None = None
    steam_web_api_key: str | None = None
    steam_openid_enabled: bool = False
    steam_openid_return_url: str | None = None
    steam_openid_realm: str | None = None
    session_secret: str | None = None
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class SteamMatchImportRequest(BaseModel):
    authentication_code: str = Field(min_length=10, max_length=32)
    known_match_code: str = Field(min_length=20, max_length=64)

class SteamShareCodeRequest(BaseModel):
    share_code: str = Field(min_length=34, max_length=34)


class ProjectCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    data: dict = Field(default_factory=dict)


class ProjectUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    status: str | None = Field(default=None, pattern="^(created|processing|completed|failed|archived)$")
    data: dict | None = None




settings = Settings()
storage_ready = False
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
FACEIT_COOKIE_NAME = "cs2dh_faceit_session"
FACEIT_STATE_COOKIE = "cs2dh_faceit_oauth_state"
FACEIT_AUTHORIZATION_ENDPOINT = "https://accounts.faceit.com"
FACEIT_TOKEN_ENDPOINT = "https://api.faceit.com/auth/v1/oauth/token"
FACEIT_USERINFO_ENDPOINT = "https://api.faceit.com/auth/v1/resources/userinfo"


@app.on_event("startup")
def startup_storage():
    global storage_ready
    if storage.available():
        try:
            storage.init_storage()
            storage_ready = True
        except Exception:
            storage_ready = False


def _require_storage():
    if not storage_ready:
        raise HTTPException(status_code=503, detail="Persistent database is not connected")


def _request_identity(request: Request) -> tuple[str, str] | None:
    faceit = _read_signed_cookie(request.cookies.get(FACEIT_COOKIE_NAME), "faceit-session")
    if faceit and faceit.get("faceit_id"):
        return ("faceit", str(faceit["faceit_id"]))
    steam = _read_session(request.cookies.get(COOKIE_NAME))
    if steam and steam.get("steam_id"):
        return ("steam", str(steam["steam_id"]))
    return None


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _make_session(steam_id: str) -> str:
    if not settings.session_secret:
        raise HTTPException(status_code=503, detail="Steam login session secret is not configured")
    payload = _b64(json.dumps({"steam_id": steam_id, "iat": int(time.time())}).encode())
    signature = hmac.new(settings.session_secret.encode(), payload.encode(), hashlib.sha256).digest()
    return payload + "." + _b64(signature)



def _signed_cookie(payload_data: dict, purpose: str) -> str:
    if not settings.session_secret:
        raise HTTPException(status_code=503, detail="Session secret is not configured")
    payload = _b64(json.dumps(payload_data, separators=(",", ":")).encode())
    signature = hmac.new(settings.session_secret.encode(), f"{purpose}:{payload}".encode(), hashlib.sha256).digest()
    return payload + "." + _b64(signature)


def _read_signed_cookie(token: str | None, purpose: str) -> dict | None:
    if not token or not settings.session_secret or "." not in token:
        return None
    payload, signature = token.rsplit(".", 1)
    expected = _b64(hmac.new(settings.session_secret.encode(), f"{purpose}:{payload}".encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if int(time.time()) - int(data.get("iat", 0)) > 30 * 86400:
            return None
        return data
    except (ValueError, TypeError, json.JSONDecodeError):
        return None

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



def _signed_payload(data: dict) -> str:
    if not settings.session_secret:
        raise HTTPException(status_code=503, detail="SESSION_SECRET is not configured")
    payload = _b64(json.dumps(data, separators=(",", ":")).encode())
    signature = hmac.new(settings.session_secret.encode(), payload.encode(), hashlib.sha256).digest()
    return payload + "." + _b64(signature)


def _verify_signed_payload(token: str | None, max_age: int = 600) -> dict | None:
    if not token or not settings.session_secret or "." not in token:
        return None
    payload, signature = token.rsplit(".", 1)
    expected = _b64(hmac.new(settings.session_secret.encode(), payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if int(time.time()) - int(data.get("iat", 0)) > max_age:
            return None
        return data
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def _decode_steam_share_code(raw_code: str) -> dict:
    """Decode a legacy CSGO- match share code into its Valve match identifiers."""
    alphabet = "ABCDEFGHJKLMNOPQRSTUVWXYZabcdefhijkmnopqrstuvwxyz23456789"
    code = raw_code.strip()
    match = re.fullmatch(r"(?i:CSGO)-(.{5})-(.{5})-(.{5})-(.{5})-(.{5})", code)
    if not match:
        raise HTTPException(status_code=422, detail="Invalid match sharing code format")
    compact = "".join(match.groups())
    if any(char not in alphabet for char in compact):
        raise HTTPException(status_code=422, detail="Match sharing code contains unsupported characters")
    value = 0
    for char in reversed(compact):
        value = value * len(alphabet) + alphabet.index(char)
    try:
        payload = value.to_bytes(18, byteorder="big")
    except OverflowError:
        raise HTTPException(status_code=422, detail="Match sharing code is outside the valid range")
    match_id = int.from_bytes(payload[0:8], byteorder="little")
    reservation_id = int.from_bytes(payload[8:16], byteorder="little")
    tv_port = int.from_bytes(payload[16:18], byteorder="little")
    if match_id == 0 or reservation_id == 0:
        raise HTTPException(status_code=422, detail="Match sharing code does not contain valid match identifiers")
    return {
        "match_id": str(match_id),
        "reservation_id": str(reservation_id),
        "tv_port": tv_port,
    }


def _faceit_oauth_ready() -> bool:
    return bool(settings.faceit_oauth_client_id and settings.faceit_oauth_client_secret
                and settings.faceit_oauth_redirect_url and settings.session_secret)


@app.api_route("/", methods=["GET", "HEAD"], tags=["system"])
async def root():
    return {"service": "CS2 DEMO HUB API", "docs": "/docs", "health": "/health"}


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "service": "cs2-demo-hub-api", "version": "0.2.0"}


@app.get("/api/v1/status", tags=["system"])
async def status():
    steam_ready = bool(settings.steam_openid_enabled and settings.steam_openid_return_url and settings.steam_openid_realm and settings.session_secret)
    return {
        "project": "CS2 DEMO HUB",
        "phase": "provider-integration",
        "integrations": {
            "steam_openid": "ready" if steam_ready else "needs_configuration",
            "steam_match_provider": "ready" if settings.steam_web_api_key else "needs_steam_web_api_key",
            "faceit_data_api": "configured" if settings.faceit_api_key else "needs_api_key",
            "faceit_oauth": "configured" if _faceit_oauth_ready() else "needs_oauth_credentials",
            "faceit_downloads_api": "configured" if settings.faceit_download_token else "access_application_required",
            "database": "connected" if storage_ready else ("configured_but_unavailable" if storage.available() else "not_configured"),
            "demo_parser": "available" if importlib.util.find_spec("demoparser2") else "not_installed",
            "video_renderer": "not_deployed",
        },
        "capabilities": ["health", "status", "faceit_player_search", "faceit_match_history", "steam_openid_login", "steam_match_next_code_import", "faceit_oauth_login", "projects_crud", "persistent_match_history", "authenticated_demo_upload", "demo_event_parser", "demo_download"],
    }


@app.get("/api/v1/matches", tags=["matches"])
async def list_matches(request: Request, source: str = "all", limit: int = Query(default=100, ge=1, le=200)):
    if source not in ("all", "steam", "faceit"):
        raise HTTPException(status_code=422, detail="Source must be all, steam, or faceit")
    identities: list[tuple[str, str]] = []
    faceit = _read_signed_cookie(request.cookies.get(FACEIT_COOKIE_NAME), "faceit-session")
    if faceit and faceit.get("faceit_id"):
        identities.append(("faceit", str(faceit["faceit_id"])))
    steam = _read_session(request.cookies.get(COOKIE_NAME))
    if steam and steam.get("steam_id"):
        identities.append(("steam", str(steam["steam_id"])))
    if not identities:
        raise HTTPException(status_code=401, detail="Sign in with Steam or FACEIT to view saved matches")
    _require_storage()
    items: list[dict] = []
    for owner_provider, owner_id in identities:
        items.extend(storage.list_matches(owner_provider, owner_id, limit))
    if source != "all":
        items = [item for item in items if item["provider"] == source]
    items.sort(key=lambda item: item.get("updated_at") or item.get("created_at"), reverse=True)
    return {"items": items[:limit], "source": source, "configured": True}


@app.post("/api/v1/steam/matches/decode", tags=["steam"])
async def decode_steam_match_code(payload: SteamShareCodeRequest, request: Request):
    decoded = _decode_steam_share_code(payload.share_code)
    normalized = "CSGO-" + "-".join(re.fullmatch(r"(?i:CSGO)-(.{5})-(.{5})-(.{5})-(.{5})-(.{5})", payload.share_code.strip()).groups())
    steam_uri = "steam://run/730//+csgo_download_match%20" + normalized
    persisted = False
    steam_session = _read_session(request.cookies.get(COOKIE_NAME))
    if steam_session and storage_ready:
        storage.save_match("steam", decoded["match_id"], "steam", str(steam_session["steam_id"]),
                           {"share_code": normalized, **decoded, "metadata_available": False})
        persisted = True
    return {
        "status": "decoded",
        "share_code": normalized,
        **decoded,
        "steam_launch_uri": steam_uri,
        "metadata_available": False,
        "persisted": persisted,
        "message": "The code identifies a Valve match. Full match metadata and cloud demo download require a Steam Game Coordinator connection.",
    }



DEMO_MAX_BYTES = 100 * 1024 * 1024


def _parse_demo_file(path: str) -> dict:
    try:
        from demoparser2 import DemoParser
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="CS2 demo parser is not installed on this service") from exc
    try:
        parser = DemoParser(path)
        deaths = parser.parse_event("player_death")
        rounds_started = parser.parse_event("round_start")
        rounds_ended = parser.parse_event("round_end")

        def records(frame, limit: int = 500) -> list[dict]:
            if frame is None or frame.empty:
                return []
            return json.loads(frame.head(limit).to_json(orient="records"))

        death_rows = records(deaths)
        kill_counts: dict[str, int] = {}
        for row in death_rows:
            attacker = row.get("attacker_name")
            victim = row.get("user_name")
            if attacker and attacker != victim:
                key = str(attacker)
                kill_counts[key] = kill_counts.get(key, 0) + 1
        return {
            "parser": "demoparser2",
            "parsed": True,
            "rounds_started": int(len(rounds_started)) if rounds_started is not None else 0,
            "rounds_ended": int(len(rounds_ended)) if rounds_ended is not None else 0,
            "deaths_total": int(len(deaths)) if deaths is not None else 0,
            "kills_by_player": sorted(
                [{"player": name, "kills": count} for name, count in kill_counts.items()],
                key=lambda item: item["kills"], reverse=True
            )[:20],
            "player_deaths": death_rows,
            "events_truncated": bool(deaths is not None and len(deaths) > 500),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse this CS2 demo: {type(exc).__name__}") from exc


@app.post("/api/v1/demos", tags=["demos"], status_code=201)
async def upload_demo(request: Request, file: UploadFile = File(...)):
    identity = _request_identity(request)
    if not identity:
        raise HTTPException(status_code=401, detail="Sign in with Steam or FACEIT to upload demos")
    _require_storage()
    filename = (file.filename or "match.dem").rsplit("/", 1)[-1].rsplit(chr(92), 1)[-1]
    if not filename.lower().endswith(".dem"):
        raise HTTPException(status_code=415, detail="Only .dem files are accepted")
    chunks = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > DEMO_MAX_BYTES:
            raise HTTPException(status_code=413, detail="Demo file exceeds the 250 MB upload limit")
        chunks.append(chunk)
    raw_data = b"".join(chunks)
    if len(raw_data) < 8 or not (raw_data.startswith(b"PBDEMS2") or raw_data.startswith(b"HL2DEMO")):
        raise HTTPException(status_code=415, detail="File header does not look like a Source/CS2 demo")
    digest = hashlib.sha256(raw_data).hexdigest()
    with tempfile.NamedTemporaryFile(suffix=".dem") as temp:
        temp.write(raw_data)
        temp.flush()
        analysis = await run_in_threadpool(_parse_demo_file, temp.name)
    demo_id = str(uuid.uuid4())
    item = storage.save_demo(demo_id, identity[0], identity[1], filename, total,
                             digest, raw_data, analysis, "parsed")
    return {"item": item}


@app.get("/api/v1/demos", tags=["demos"])
async def list_demos(request: Request):
    identity = _request_identity(request)
    if not identity:
        raise HTTPException(status_code=401, detail="Sign in with Steam or FACEIT to view demos")
    _require_storage()
    return {"items": storage.list_demos(identity[0], identity[1])}


@app.get("/api/v1/demos/{demo_id}", tags=["demos"])
async def get_demo(demo_id: str, request: Request):
    identity = _request_identity(request)
    if not identity:
        raise HTTPException(status_code=401, detail="Sign in with Steam or FACEIT to view demos")
    _require_storage()
    item = storage.get_demo(identity[0], identity[1], demo_id)
    if not item:
        raise HTTPException(status_code=404, detail="Demo not found")
    return {"item": item}


@app.get("/api/v1/demos/{demo_id}/download", tags=["demos"])
async def download_demo(demo_id: str, request: Request):
    identity = _request_identity(request)
    if not identity:
        raise HTTPException(status_code=401, detail="Sign in with Steam or FACEIT to download demos")
    _require_storage()
    item = storage.get_demo(identity[0], identity[1], demo_id, include_data=True)
    if not item:
        raise HTTPException(status_code=404, detail="Demo not found")
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", item["filename"])
    return Response(content=bytes(item["raw_data"]), media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{safe_name}"'})


@app.delete("/api/v1/demos/{demo_id}", tags=["demos"])
async def delete_demo(demo_id: str, request: Request):
    identity = _request_identity(request)
    if not identity:
        raise HTTPException(status_code=401, detail="Sign in with Steam or FACEIT to delete demos")
    _require_storage()
    if not storage.delete_demo(identity[0], identity[1], demo_id):
        raise HTTPException(status_code=404, detail="Demo not found")
    return {"deleted": True, "demo_id": demo_id}


@app.get("/api/v1/projects", tags=["projects"])
async def projects_list(request: Request):
    identity = _request_identity(request)
    if not identity:
        raise HTTPException(status_code=401, detail="Sign in with Steam or FACEIT first")
    _require_storage()
    return {"items": storage.list_projects(identity[0], identity[1])}


@app.post("/api/v1/projects", tags=["projects"], status_code=201)
async def projects_create(payload: ProjectCreateRequest, request: Request):
    identity = _request_identity(request)
    if not identity:
        raise HTTPException(status_code=401, detail="Sign in with Steam or FACEIT first")
    _require_storage()
    item = storage.create_project(identity[0], identity[1], payload.title.strip(),
                                  payload.description.strip(), payload.data)
    return {"item": item}


@app.get("/api/v1/projects/{project_id}", tags=["projects"])
async def projects_get(project_id: str, request: Request):
    identity = _request_identity(request)
    if not identity:
        raise HTTPException(status_code=401, detail="Sign in with Steam or FACEIT first")
    _require_storage()
    item = storage.get_project(identity[0], identity[1], project_id)
    if not item:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"item": item}


@app.patch("/api/v1/projects/{project_id}", tags=["projects"])
async def projects_update(project_id: str, payload: ProjectUpdateRequest, request: Request):
    identity = _request_identity(request)
    if not identity:
        raise HTTPException(status_code=401, detail="Sign in with Steam or FACEIT first")
    _require_storage()
    fields = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not fields:
        raise HTTPException(status_code=422, detail="No project fields supplied")
    item = storage.update_project(identity[0], identity[1], project_id, fields)
    if not item:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"item": item}


@app.delete("/api/v1/projects/{project_id}", tags=["projects"])
async def projects_delete(project_id: str, request: Request):
    identity = _request_identity(request)
    if not identity:
        raise HTTPException(status_code=401, detail="Sign in with Steam or FACEIT first")
    _require_storage()
    if not storage.delete_project(identity[0], identity[1], project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"deleted": True, "project_id": project_id}


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


@app.get("/api/v1/auth/faceit/matches", tags=["faceit-auth"])
async def faceit_my_matches(request: Request, limit: int = Query(default=20, ge=1, le=100)):
    """Return the connected FACEIT user's public CS2 match history."""
    identity = _read_signed_cookie(request.cookies.get(FACEIT_COOKIE_NAME), "faceit-session")
    if not identity:
        raise HTTPException(status_code=401, detail="Connect your FACEIT account first")
    nickname = identity.get("nickname")
    if not nickname:
        raise HTTPException(status_code=422, detail="FACEIT profile did not provide a nickname")

    player = await _faceit_get("/players", {"nickname": nickname, "game": "cs2"})
    player_id = player.get("player_id")
    if not player_id:
        raise HTTPException(status_code=404, detail="Could not match the connected FACEIT profile to a CS2 player")

    history = await _faceit_get(f"/players/{player_id}/history", {"game": "cs2", "offset": 0, "limit": limit})
    items = []
    for match in history.get("items", []):
        demo_values = match.get("demo_url") or match.get("demo_urls") or []
        items.append({
            "match_id": match.get("match_id"),
            "started_at": match.get("started_at"),
            "finished_at": match.get("finished_at"),
            "game_mode": match.get("game_mode"),
            "map": (match.get("demo") or {}).get("map") if isinstance(match.get("demo"), dict) else None,
            "demo_available": bool(demo_values),
        })
    if storage_ready:
        for item in items:
            if item.get("match_id"):
                storage.save_match("faceit", str(item["match_id"]), "faceit",
                                   str(identity["faceit_id"]), item)
    return {"items": items, "source": "FACEIT Data API", "player_id": player_id, "nickname": nickname}


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



@app.get("/api/v1/auth/faceit/login", tags=["faceit-auth"])
async def faceit_login():
    if not (settings.faceit_oauth_client_id and settings.faceit_oauth_client_secret and
            settings.faceit_oauth_redirect_url and settings.session_secret):
        raise HTTPException(status_code=503, detail="FACEIT OAuth is not configured. Add FACEIT_OAUTH_CLIENT_ID, FACEIT_OAUTH_CLIENT_SECRET and FACEIT_OAUTH_REDIRECT_URL.")
    import secrets
    verifier = _b64(secrets.token_bytes(48))
    challenge = _b64(hashlib.sha256(verifier.encode()).digest())
    state = _b64(secrets.token_bytes(32))
    signed_state = _signed_cookie({"state": state, "verifier": verifier, "iat": int(time.time())}, "faceit-oauth-state")
    params = {
        "client_id": settings.faceit_oauth_client_id,
        "response_type": "code",
        "redirect_uri": settings.faceit_oauth_redirect_url,
        "scope": "openid profile",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    response = RedirectResponse(FACEIT_AUTHORIZATION_ENDPOINT + "?" + urlencode(params), status_code=302)
    response.set_cookie(FACEIT_STATE_COOKIE, signed_state, httponly=True, secure=True,
                        samesite="lax", max_age=600, path="/")
    return response


@app.get("/api/v1/auth/faceit/callback", tags=["faceit-auth"])
async def faceit_callback(request: Request):
    if request.query_params.get("error"):
        raise HTTPException(status_code=401, detail="FACEIT authorization was declined or failed")
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    pending = _read_signed_cookie(request.cookies.get(FACEIT_STATE_COOKIE), "faceit-oauth-state")
    if not code or not state or not pending or not hmac.compare_digest(state, str(pending.get("state", ""))):
        raise HTTPException(status_code=400, detail="Invalid or expired FACEIT OAuth state")
    if not (settings.faceit_oauth_client_id and settings.faceit_oauth_client_secret and settings.faceit_oauth_redirect_url):
        raise HTTPException(status_code=503, detail="FACEIT OAuth credentials are not configured")
    async with httpx.AsyncClient(timeout=20) as client:
        token_response = await client.post(
            FACEIT_TOKEN_ENDPOINT,
            data={"grant_type": "authorization_code", "code": code,
                  "redirect_uri": settings.faceit_oauth_redirect_url,
                  "code_verifier": pending["verifier"]},
            auth=(settings.faceit_oauth_client_id, settings.faceit_oauth_client_secret),
            headers={"Accept": "application/json"},
        )
        if token_response.is_error:
            raise HTTPException(status_code=502, detail=f"FACEIT token exchange failed (HTTP {token_response.status_code})")
        access_token = token_response.json().get("access_token")
        if not access_token:
            raise HTTPException(status_code=502, detail="FACEIT did not return an access token")
        user_response = await client.get(FACEIT_USERINFO_ENDPOINT,
                                         headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"})
        if user_response.is_error:
            raise HTTPException(status_code=502, detail=f"FACEIT user profile request failed (HTTP {user_response.status_code})")
        profile = user_response.json()
    identity = {
        "provider": "faceit",
        "faceit_id": profile.get("guid") or profile.get("sub") or profile.get("id"),
        "nickname": profile.get("nickname") or profile.get("name"),
        "picture": profile.get("picture"),
        "iat": int(time.time()),
    }
    if not identity["faceit_id"]:
        raise HTTPException(status_code=502, detail="FACEIT profile response did not contain a user identifier")
    response = RedirectResponse(settings.frontend_origin.rstrip("/") + "/?faceit=connected", status_code=303)
    response.set_cookie(FACEIT_COOKIE_NAME, _signed_cookie(identity, "faceit-session"),
                        httponly=True, secure=True, samesite="none", max_age=30 * 86400, path="/")
    response.delete_cookie(FACEIT_STATE_COOKIE, path="/", secure=True, httponly=True, samesite="lax")
    return response


@app.get("/api/v1/auth/faceit/me", tags=["faceit-auth"])
async def faceit_auth_me(request: Request):
    session = _read_signed_cookie(request.cookies.get(FACEIT_COOKIE_NAME), "faceit-session")
    if not session:
        return {"authenticated": False, "provider": "faceit"}
    return {"authenticated": True, "provider": "faceit", "faceit_id": session.get("faceit_id"),
            "nickname": session.get("nickname"), "picture": session.get("picture")}


@app.post("/api/v1/auth/faceit/logout", tags=["faceit-auth"])
async def faceit_auth_logout():
    response = RedirectResponse(settings.frontend_origin, status_code=303)
    response.delete_cookie(FACEIT_COOKIE_NAME, path="/", secure=True, httponly=True, samesite="none")
    return response


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


_STEAM_AUTH_CODE_RE = re.compile(r"^[A-Z0-9]{4,5}(?:-[A-Z0-9]{4,5}){2,3}$", re.IGNORECASE)
_STEAM_MATCH_CODE_RE = re.compile(r"^CSGO-[A-Z0-9]{5}(?:-[A-Z0-9]{5}){4,5}$", re.IGNORECASE)


@app.post("/api/v1/steam/matches/next", tags=["steam-matches"])
async def steam_next_match(request: Request, payload: SteamMatchImportRequest):
    """Fetch one next match-sharing code. Submitted credentials are not persisted."""
    session = _read_session(request.cookies.get(COOKIE_NAME))
    if not session:
        raise HTTPException(status_code=401, detail="Sign in with Steam before importing matches")
    if not settings.steam_web_api_key:
        raise HTTPException(status_code=503, detail="Steam Web API key is not configured on the server")
    if not _STEAM_AUTH_CODE_RE.fullmatch(payload.authentication_code):
        raise HTTPException(status_code=422, detail="Invalid Steam Game Authentication Code format")
    if not _STEAM_MATCH_CODE_RE.fullmatch(payload.known_match_code):
        raise HTTPException(status_code=422, detail="Invalid CS2 Match Sharing Code format")
    params = {"key": settings.steam_web_api_key, "steamid": session["steam_id"],
              "steamidkey": payload.authentication_code, "knowncode": payload.known_match_code}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get("https://api.steampowered.com/ICSGOPlayers_730/GetNextMatchSharingCode/v1/",
                                        params=params, headers={"Accept": "application/json"})
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Steam did not respond in time; try again later")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Could not reach Steam match-history service")
    if response.status_code == 202:
        return {"status": "up_to_date", "next_code": None, "message": "No newer match is available"}
    if response.status_code == 412:
        raise HTTPException(status_code=422, detail="Match Sharing Code is invalid or does not belong to this Steam account")
    if response.status_code == 403:
        raise HTTPException(status_code=403, detail="Steam rejected the Game Authentication Code")
    if response.status_code in (429, 503):
        raise HTTPException(status_code=503, detail="Steam rate limit or temporary restriction; retry later")
    if response.is_error:
        raise HTTPException(status_code=502, detail=f"Steam match-history service returned HTTP {response.status_code}")
    try:
        next_code = response.json().get("result", {}).get("nextcode")
    except ValueError:
        raise HTTPException(status_code=502, detail="Steam returned an unreadable response")
    if not isinstance(next_code, str) or not next_code.startswith("CSGO-"):
        raise HTTPException(status_code=502, detail="Steam response did not contain a valid next match code")
    decoded = _decode_steam_share_code(next_code)
    if storage_ready:
        storage.save_match("steam", decoded["match_id"], "steam", str(session["steam_id"]),
                           {"share_code": next_code, **decoded, "metadata_available": False})
    return {"status": "next_match_available", "next_code": next_code, "decoded": decoded}


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
