"""FastAPI application for fraud detection bot."""

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import asyncio
import logging
import sys
import os
from datetime import datetime

from .core.config import settings
from .services.blacklist_service import get_blacklist_service

# Import routers (v1.0)
from .routers import health, blacklist, history, fraud, webhook

# Import v2.0 routers
from .routers import conversation, fraud_v2, verification

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            f'logs/gungong_{datetime.now().strftime("%Y%m%d")}.log',
            encoding='utf-8'
        ) if os.path.exists('logs') or os.makedirs('logs', exist_ok=True) else logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

# Initialize FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="LINE Bot for detecting fraud and spam messages using Gemini AI",
    version="1.0.0",
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
ALLOWED_ORIGINS = [
    "https://liff.line.me",  # LINE LIFF
    "http://localhost:8000",  # Local development
    "http://127.0.0.1:8000",  # Local development
]

# Add ngrok URL from environment if available (for development/testing)
if settings.debug:
    ALLOWED_ORIGINS.extend([
        "http://localhost:*",
        "http://127.0.0.1:*",
        "*",  # Allow all in debug mode for ngrok testing
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if not settings.debug else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Line-Signature", "ngrok-skip-browser-warning"],
)

# Register v1.0 routers
app.include_router(health.router, tags=["health"])
app.include_router(blacklist.router, tags=["blacklist"])
app.include_router(history.router, tags=["history"])
app.include_router(fraud.router, tags=["fraud"])
app.include_router(webhook.router, tags=["webhook"])

# Register v2.0 routers
app.include_router(conversation.router, tags=["v2-conversation"])
app.include_router(fraud_v2.router, tags=["v2-fraud"])
app.include_router(verification.router, tags=["v2-verification"])

# Mount static files (frontend built by Vite)
# Check for Vite build output first (production), then fallback to old frontend
static_path = os.path.join(os.path.dirname(__file__), "static")
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

if os.path.exists(static_path):
    # Production: Serve Vite-built React app
    # Mount assets (JS/CSS bundles from Vite)
    assets_path = os.path.join(static_path, "assets")
    if os.path.exists(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

    # Mount img folder (copied from public/img by Vite)
    img_path = os.path.join(static_path, "img")
    if os.path.exists(img_path):
        app.mount("/img", StaticFiles(directory=img_path), name="img")
        logger.info(f"Images mounted from {img_path}")

    logger.info(f"Frontend (Vite build) mounted from {static_path}")
elif os.path.exists(frontend_path):
    # Fallback: Old frontend structure
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")
    app.mount("/img", StaticFiles(directory=os.path.join(frontend_path, "img")), name="img")
    app.mount("/js", StaticFiles(directory=os.path.join(frontend_path, "js")), name="js")
    app.mount("/style", StaticFiles(directory=os.path.join(frontend_path, "style")), name="style")
    logger.info(f"Frontend mounted from {frontend_path}")
else:
    logger.warning(f"Frontend directory not found")


@app.on_event("startup")
async def startup_event():
    """Run on startup."""
    logger.info("Application starting up...")

    # Seed mock blacklist data
    try:
        blacklist_service = get_blacklist_service()
        if blacklist_service:
            blacklist_service.seed_mock_data()
            logger.info("Mock blacklist data seeded")
    except Exception as e:
        logger.warning(f"Failed to seed mock data: {e}")

    # Playwright browser warmup disabled to prevent Cloud Run startup timeout
    # Browser will be initialized on first use (lazy loading)
    logger.info("Startup complete (browser will lazy load)")


@app.get("/", response_class=FileResponse)
async def root():
    """Serve the frontend index.html."""
    # Try Vite build first, then fallback
    if os.path.exists(os.path.join(static_path, "index.html")):
        return FileResponse(os.path.join(static_path, "index.html"))
    elif os.path.exists(os.path.join(frontend_path, "index.html")):
        return FileResponse(os.path.join(frontend_path, "index.html"))
    return {"status": "healthy", "message": "Frontend not found, but API is running"}