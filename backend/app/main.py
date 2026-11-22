from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "CS2 DEMO HUB API"
    app_env: str = "development"
    frontend_origin: str = "http://localhost:3000"
    faceit_api_key: str | None = None
    steam_openid_enabled: bool = False
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
app = FastAPI(title=settings.app_name, version="0.1.0", description="CS2 match and demo platform API")
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_credentials=True, allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Authorization", "Content-Type"])

@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "service": "cs2-demo-hub-api", "version": "0.1.0"}

@app.get("/api/v1/status", tags=["system"])
async def status():
    return {
        "project": "CS2 DEMO HUB",
        "phase": "foundation",
        "integrations": {
            "steam_openid": "configured" if settings.steam_openid_enabled else "not_configured",
            "steam_match_provider": "adapter_required",
            "faceit_api": "configured" if settings.faceit_api_key else "not_configured",
            "demo_parser": "planned",
            "video_renderer": "planned",
        },
        "capabilities": ["health", "status", "provider_architecture"],
    }

@app.get("/api/v1/matches", tags=["matches"])
async def list_matches(source: str = "all"):
    # Intentionally returns an empty collection until a real provider is configured.
    # Never fabricate matches or demo download URLs.
    return {"items": [], "source": source, "configured": False, "message": "Подключите Steam/FACEIT provider для получения реальных матчей."}
