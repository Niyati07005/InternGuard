import logging
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .auth import router as auth_router
from .database import Base, engine, migrate_database
from .models import Scan, User
from .routes import router

Base.metadata.create_all(bind=engine)
migrate_database()

logger = logging.getLogger(__name__)
environment = os.getenv("ENVIRONMENT", "development").lower()
session_secret = os.getenv("SESSION_SECRET")
if not session_secret:
    if environment == "production":
        raise RuntimeError("SESSION_SECRET is required in production.")
    session_secret = secrets.token_urlsafe(48)
    logger.warning("SESSION_SECRET is unset; sessions will expire when the backend restarts.")
elif environment == "production" and len(session_secret) < 32:
    raise RuntimeError("SESSION_SECRET must contain at least 32 characters in production.")

session_max_age = int(os.getenv("SESSION_MAX_AGE_SECONDS", str(8 * 60 * 60)))
secure_cookie = os.getenv(
    "SESSION_COOKIE_SECURE", "true" if environment == "production" else "false"
).lower() == "true"
same_site = os.getenv(
    "SESSION_COOKIE_SAMESITE", "none" if environment == "production" else "lax"
).lower()
if same_site not in {"lax", "strict", "none"}:
    raise RuntimeError("SESSION_COOKIE_SAMESITE must be lax, strict, or none.")
if same_site == "none" and not secure_cookie:
    raise RuntimeError("SameSite=None requires SESSION_COOKIE_SECURE=true.")

configured_origins = os.getenv("CORS_ORIGINS", "").strip()
if configured_origins:
    allowed_origins = [origin.strip().rstrip("/") for origin in configured_origins.split(",") if origin.strip()]
elif environment == "production":
    raise RuntimeError("Set CORS_ORIGINS to the exact deployed frontend origin in production.")
else:
    allowed_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
    ]
if "*" in allowed_origins:
    raise RuntimeError("CORS_ORIGINS cannot contain '*' when credentialed sessions are enabled.")

app = FastAPI(title="InternGuard API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret,
    session_cookie="internguard_session",
    max_age=session_max_age,
    same_site=same_site,
    https_only=secure_cookie,
)
app.include_router(auth_router)
app.include_router(router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "InternGuard"}
