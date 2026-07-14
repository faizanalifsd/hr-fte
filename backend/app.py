"""
FastAPI Main Application - AI Job Application System.

Architecture:
- Python backend with FastAPI
- MySQL persistence
- AI sub-agents: OpenRouter (primary) → Groq (fallback) → rule-based
- MCP integration (Apify + Gmail)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
from pathlib import Path

# Load .env file before anything else
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv not installed, rely on system env vars

from .models import init_db
from .routes import (
    mission_router,
    job_router,
    email_router,
    application_router,
    cv_router
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="AI Job Application System",
    description="Autonomous job application agent with HITL approval",
    version="1.0.0"
)

# CORS configuration (for frontend)
# Use allow_origin_regex so any localhost port works regardless of which
# port Vite picks (5173, 5174, 5175, … depend on what's free).
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# STARTUP & SHUTDOWN EVENTS
# ============================================================

@app.on_event("startup")
async def startup_event():
    """
    Initialize system on startup.

    - Validate environment variables
    - Initialize database connection
    - Validate MCP API keys
    """
    logger.info("=== AI JOB APPLICATION SYSTEM STARTUP ===")

    # Build DATABASE_URL from individual DB_* params if not set
    if not os.getenv("DATABASE_URL"):
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "3306")
        db_user = os.getenv("DB_USER", "")
        db_pass = os.getenv("DB_PASS", "")
        db_name = os.getenv("DB_NAME", "")
        if db_user and db_name:
            constructed_url = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
            os.environ["DATABASE_URL"] = constructed_url
            logger.info(f"DATABASE_URL constructed from DB_* params: mysql+pymysql://{db_user}:***@{db_host}:{db_port}/{db_name}")

    # Check required environment variables
    required_vars = [
        "DATABASE_URL",
        "APIFY_API_KEY",
        "GMAIL_CLIENT_ID",
        "GMAIL_CLIENT_SECRET",
        "GMAIL_REFRESH_TOKEN",
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing_vars)}\n"
            "Please set all required variables in .env file"
        )

    # Log LLM provider status (non-fatal — rule-based fallback always available)
    or_key = os.getenv("OPENROUTER_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")
    if or_key:
        logger.info("✓ OpenRouter API key found (primary LLM provider)")
    if groq_key:
        logger.info("✓ Groq API key found (fallback LLM provider)")
    if not or_key and not groq_key:
        logger.warning("⚠ No LLM API keys — sub-agents will use rule-based fallback")

    # Initialize database
    try:
        database_url = os.getenv("DATABASE_URL")
        init_db(database_url)
        logger.info("✓ Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise

    # Validate MCP services
    try:
        from .services.mcp import ApifyService, GmailService

        # Validate Apify
        apify = ApifyService()
        if apify.validate_api_key():
            logger.info("✓ Apify MCP validated")
        else:
            logger.warning("⚠ Apify API key validation failed")

        # Validate Gmail
        gmail = GmailService()
        if gmail.validate_credentials():
            logger.info("✓ Gmail MCP validated")
        else:
            logger.warning("⚠ Gmail credentials validation failed")

    except Exception as e:
        logger.warning(f"MCP validation warning: {str(e)}")

    logger.info("=== SYSTEM READY ===")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("=== SYSTEM SHUTDOWN ===")


# ============================================================
# ROUTES
# ============================================================

# Include routers
app.include_router(mission_router)
app.include_router(job_router)
app.include_router(email_router)
app.include_router(application_router)
app.include_router(cv_router)


# ============================================================
# HEALTH CHECK & INFO
# ============================================================

@app.get("/")
def read_root():
    """Root endpoint - system info."""
    return {
        "name": "AI Job Application System",
        "version": "2.0.0",
        "status": "running",
        "architecture": {
            "ai_sub_agents": "OpenRouter → Groq → Rule-based",
            "mcp": ["Apify", "Gmail"],
            "database": "MySQL",
            "framework": "FastAPI",
        },
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/system/status")
def system_status():
    """System status with environment validation."""
    env_status = {
        "database": bool(os.getenv("DATABASE_URL")),
        "apify_api": bool(os.getenv("APIFY_API_KEY")),
        "gmail_configured": all([
            os.getenv("GMAIL_CLIENT_ID"),
            os.getenv("GMAIL_CLIENT_SECRET"),
            os.getenv("GMAIL_REFRESH_TOKEN"),
        ]),
    }

    optional_status = {
        "openrouter_api": bool(os.getenv("OPENROUTER_API_KEY")),
        "groq_api": bool(os.getenv("GROQ_API_KEY")),
    }

    all_configured = all(env_status.values())
    llm_mode = (
        "OpenRouter + Groq" if optional_status["openrouter_api"] and optional_status["groq_api"]
        else "OpenRouter" if optional_status["openrouter_api"]
        else "Groq" if optional_status["groq_api"]
        else "Rule-based only"
    )

    return {
        "mode": llm_mode,
        "configured": all_configured,
        "required_services": env_status,
        "optional_services": optional_status,
        "message": (
            "All required systems operational"
            if all_configured
            else "Some required services not configured"
        ),
    }


# ============================================================
# RUN SERVER (for development)
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes (dev only)
        log_level="info"
    )
