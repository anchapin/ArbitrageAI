"""
System configuration and lifespan module.

This module contains FastAPI app initialization, lifespan management,
middleware setup, and system mode endpoints.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.utils.logger import get_logger
from src.config.config_manager import ConfigManager, validate_production_configuration
from src.utils.telemetry import init_observability

# Import background job queue
try:
    from src.async_rag_service import get_async_rag_service
    from src.background_job_queue import get_background_job_queue
    from src.experience_vector_db import get_experience_db
    EXPERIENCE_DB_AVAILABLE = True
except ImportError:
    EXPERIENCE_DB_AVAILABLE = False

logger = get_logger(__name__)


async def start_autonomous_loop():
    """Start the autonomous scanning loop if enabled."""
    from .main import _autonomous_loop_task, AUTONOMOUS_SCAN_ENABLED

    global _autonomous_loop_task  # noqa: PLW0603

    if AUTONOMOUS_SCAN_ENABLED:
        logger.info("[STARTUP] Autonomous scanning is ENABLED")
        import asyncio
        from .main import run_autonomous_loop
        _autonomous_loop_task = asyncio.create_task(run_autonomous_loop())
        logger.info("[STARTUP] Autonomous scanning loop started")
    else:
        logger.info("[STARTUP] Autonomous scanning is DISABLED")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Validate production configuration BEFORE anything else
    validate_production_configuration()

    # Initialize DB and Observability
    from .database import init_db
    init_db()
    init_observability()

    # Initialize Background Job Queue
    if EXPERIENCE_DB_AVAILABLE:
        queue = await get_background_job_queue(max_workers=3)
        logger.info("Background job queue started")

        vector_db = get_experience_db()
        if vector_db:
            get_async_rag_service(vector_db)
            logger.info("Async RAG service initialized")

    # Start autonomous scanning loop if enabled
    await start_autonomous_loop()

    yield

    # Shutdown logic
    if EXPERIENCE_DB_AVAILABLE:
        queue = get_background_job_queue()
        await queue.stop()
        logger.info("Background job queue stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    from .rate_limit_middleware import RateLimitMiddleware
    from .security_headers import SecurityHeadersMiddleware
    from .versioning import APIVersionMiddleware

    app = FastAPI(title="ArbitrageAI API", lifespan=lifespan)

    # Add Rate Limiting Middleware
    app.add_middleware(RateLimitMiddleware)

    # Add Security Headers Middleware
    app.add_middleware(SecurityHeadersMiddleware)
    logger.info("Security headers middleware added")

    # Add API Versioning Middleware
    app.add_middleware(APIVersionMiddleware)
    logger.info("API versioning middleware added")

    return app


# System mode configuration
def get_system_mode() -> dict:
    """Get current system mode (training or production)."""
    training_mode = ConfigManager.get("TRAINING_MODE", False)
    return {
        "training_mode": training_mode,
        "status": "training" if training_mode else "production",
        "available_modes": ["production", "training"],
    }


def set_system_mode(training_mode: bool) -> dict:
    """Set system mode (training or production)."""
    ConfigManager._config_cache["TRAINING_MODE"] = training_mode
    mode = "training" if training_mode else "production"
    return {
        "training_mode": training_mode,
        "status": mode,
        "message": f"System mode changed to {mode}",
    }


__all__ = [
    "lifespan",
    "create_app",
    "get_system_mode",
    "set_system_mode",
    "EXPERIENCE_DB_AVAILABLE",
]
