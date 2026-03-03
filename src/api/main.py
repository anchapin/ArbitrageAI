"""
FastAPI backend for ArbitrageAI - Main Module.

This module has been refactored to import from specialized submodules:
- files: File upload validation, delivery endpoints, rate limiting
- financial: Pricing calculation, discount tiers
- threshold: Escalation logic, human-in-the-loop (HITL)
- learning: Experience logging, arena learning
- system: App initialization, lifespan, middleware

Backward compatibility is maintained by re-exporting all symbols.
"""

# Import from new modular structure
from .files import (
    AddressValidationModel,
    DeliveryAmountModel,
    DeliveryResponse,
    DeliveryTimestampModel,
    DeliveryTokenRequest,
    _check_delivery_ip_rate_limit,
    _check_delivery_rate_limit,
    _delivery_ip_rate_limits,
    _delivery_rate_limits,
    _record_delivery_failure,
    _record_ip_delivery_attempt,
    _sanitize_string,
)

from .financial import (
    COMPLEXITY_MULTIPLIERS,
    DOMAIN_BASE_RATES,
    DOMAIN_PRICES,
    MAX_DISCOUNT,
    REPEAT_CLIENT_DISCOUNTS,
    URGENCY_MULTIPLIERS,
    calculate_task_price,
    get_client_discount,
    get_discount_tier,
)

from .threshold import (
    HIGH_VALUE_THRESHOLD,
    MAX_RETRY_ATTEMPTS,
    _escalate_task,
    _should_escalate_task,
)

from .learning import (
    EXPERIENCE_DB_AVAILABLE,
    ArenaLearningLogger,
    ExperienceLogger,
    _log_arena_learning,
    experience_logger,
)

from .system import (
    EXPERIENCE_DB_AVAILABLE as SYSTEM_EXPERIENCE_DB_AVAILABLE,
    create_app,
    get_system_mode,
    lifespan,
    set_system_mode,
)

# Import models for backward compatibility
from .models import (
    ArenaCompetition,
    ArenaCompetitionStatus,
    Base,
    Bid,
    BidStatus,
    ClientProfile,
    ConfidenceAdjustment,
    ConfidenceEntry,
    CostEntry,
    DistributedLock,
    EscalationLog,
    ExecutionStatus,
    LearningEntry,
    OutputType,
    PlanningStatus,
    PricingTier,
    QuotaUsage,
    RateLimitLog,
    ReviewStatus,
    SimulationBid,
    Task,
    TaskArena,
    TaskExecution,
    TaskOutput,
    TaskPlanning,
    TaskReview,
    TaskStatus,
    ThresholdPetition,
    UserQuota,
    VirtualWallet,
    WebhookSecret,
)

# Import database
from .database import SessionLocal, get_db, init_db

# Import other required modules
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import json
import logging
import os
import random
import re
import secrets
import time as _time
from typing import Any
import uuid

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
import httpx
from pydantic import BaseModel, Field, ValidationError, ValidationInfo, field_validator
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session
import stripe

# Import Agent Arena modules
from src.agent_execution.arena import (
    ArenaLearningLogger as ArenaArenaLearningLogger,
    ArenaRouter,
    CompetitionType,
    run_agent_arena,
)

# Import executor for backward compatibility
from src.agent_execution.executor import OutputFormat, execute_task

# Import Market Scanner
from src.agent_execution.market_scanner import run_single_scan

# Import Agent execution modules
from src.agent_execution.planning import (
    ContextExtractor,
    ResearchAndPlanOrchestrator,
    WorkPlanGenerator,
    get_client_preferences_from_tasks,
    save_client_preferences,
)

# Import Config Manager
from src.config.config_manager import ConfigManager, validate_production_configuration

# Import LLM Service
from src.llm_service import LLMService

# Import client authentication
from src.utils.client_auth import generate_client_token, verify_client_token

# Import file validation utility
from src.utils.file_validator import validate_file_upload

# Import logging module
from src.utils.logger import get_logger

# Import notifications
from src.utils.notifications import TelegramNotifier

# Import telemetry
from src.utils.telemetry import init_observability

# Import API routes
from src.api.analytics import register_analytics_routes
from src.api.disaster_recovery import router as disaster_recovery_router
from src.api.experience_logger import experience_logger as exp_logger

# Import Rate Limiting Middleware
from .rate_limit_middleware import RateLimitMiddleware

# Import Scheduler modules
from .scheduler_endpoints import register_scheduler_routes

# Import Security Headers Middleware
from .security_headers import SecurityHeadersMiddleware

# Import API Versioning Middleware
from .versioning import APIVersionMiddleware

# Initialize logger
logger = get_logger(__name__)

# Experience DB availability (check both modules)
EXPERIENCE_DB_AVAILABLE = EXPERIENCE_DB_AVAILABLE or SYSTEM_EXPERIENCE_DB_AVAILABLE

# Base URL for success/cancel pages
BASE_URL = os.environ.get("BASE_URL", "http://localhost:5173")

# Stripe configuration
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "sk_test_placeholder")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_placeholder")

# Delivery token TTL
DELIVERY_TOKEN_TTL_HOURS = ConfigManager.get("DELIVERY_TOKEN_TTL_HOURS")
DELIVERY_MAX_FAILED_ATTEMPTS = ConfigManager.get("DELIVERY_MAX_FAILED_ATTEMPTS")
DELIVERY_LOCKOUT_SECONDS = ConfigManager.get("DELIVERY_LOCKOUT_SECONDS")
DELIVERY_MAX_ATTEMPTS_PER_IP = ConfigManager.get("DELIVERY_MAX_ATTEMPTS_PER_IP")
DELIVERY_IP_LOCKOUT_SECONDS = ConfigManager.get("DELIVERY_IP_LOCKOUT_SECONDS")

# Autonomous loop configuration
AUTONOMOUS_SCAN_ENABLED = os.environ.get("AUTONOMOUS_SCAN_ENABLED", "false").lower() == "true"
AUTONOMOUS_SCAN_INTERVAL_MIN = int(ConfigManager.get("MARKET_SCAN_INTERVAL")) // 60
AUTONOMOUS_SCAN_INTERVAL_MAX = int(ConfigManager.get("MARKET_SCAN_INTERVAL")) // 60 * 2
AUTONOMOUS_MIN_BID_THRESHOLD = ConfigManager.get("MIN_BID_THRESHOLD")

# Track if autonomous loop is running
_autonomous_loop_task = None


# Task submission model
class TaskSubmission(BaseModel):
    """Model for task submission data."""
    domain: str
    title: str
    description: str
    csvContent: str | None = None
    file_type: str | None = None
    file_content: str | None = None
    filename: str | None = None
    complexity: str = "medium"
    urgency: str = "standard"
    client_email: str | None = None

    @field_validator("file_content")
    @classmethod
    def validate_file_upload_content(cls, v, info: ValidationInfo):
        values = info.data
        filename = values.get("filename")
        file_type = values.get("file_type")
        if v and filename:
            try:
                validate_file_upload(filename=filename, file_content_base64=v, file_type=file_type)
            except ValueError as e:
                raise ValueError(f"File validation failed: {e!s}") from e
        return v

    @field_validator("filename")
    @classmethod
    def validate_filename_present_with_content(cls, v, info: ValidationInfo):
        values = info.data
        if values.get("file_content") and not v:
            raise ValueError("filename is required when file_content is provided")
        return v


# Checkout response model
class CheckoutResponse(BaseModel):
    """Model for checkout session response."""
    session_id: str
    url: str
    amount: int
    domain: str
    title: str
    client_auth_token: str = None


# Create the FastAPI app
app = create_app()

# Register disaster recovery router
app.include_router(disaster_recovery_router, prefix="/api", tags=["disaster-recovery"])

# Register scheduler routes
register_scheduler_routes(app)

# Register analytics routes
register_analytics_routes(app)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "ArbitrageAI API is running"}


@app.get("/api/domains")
async def get_domains():
    """Get available domains and their pricing configuration."""
    return {
        "domains": [
            {"value": domain, "label": domain.replace("_", " ").title(), "base_price": price}
            for domain, price in DOMAIN_BASE_RATES.items()
        ],
        "complexity": [
            {"value": key, "label": key.title(), "multiplier": value}
            for key, value in COMPLEXITY_MULTIPLIERS.items()
        ],
        "urgency": [
            {"value": key, "label": key.title(), "multiplier": value}
            for key, value in URGENCY_MULTIPLIERS.items()
        ],
    }


@app.get("/api/calculate-price")
async def get_price_estimate(
    domain: str, complexity: str = "medium", urgency: str = "standard",
):
    """Calculate a price estimate based on domain, complexity, and urgency."""
    try:
        amount = calculate_task_price(domain, complexity, urgency)
        base_rate = DOMAIN_BASE_RATES[domain]
        complexity_mult = COMPLEXITY_MULTIPLIERS[complexity]
        urgency_mult = URGENCY_MULTIPLIERS[urgency]
        return {
            "domain": domain, "complexity": complexity, "urgency": urgency,
            "base_rate": base_rate, "complexity_multiplier": complexity_mult,
            "urgency_multiplier": urgency_mult, "calculated_price": amount,
            "formula": f"${base_rate} x {complexity_mult} x {urgency_mult} = ${amount}",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# Import remaining endpoints from original file for backward compatibility
# These will be gradually migrated to specialized modules
from .main_original import (
    create_checkout_session,
    get_task,
    get_task_by_session,
    get_client_task_history,
    get_client_discount_info,
    get_secure_delivery,
    process_task_async,
    run_autonomous_loop,
    start_autonomous_loop as original_start_autonomous_loop,
    generate_proposal,
    # Arena endpoints
    run_arena_competition,
    get_arena_history,
    get_arena_stats,
    # System mode endpoints
    get_system_mode as original_get_system_mode,
    set_system_mode as original_set_system_mode,
    # Financial endpoints
    get_financial_status,
    add_seed_money,
    set_budget,
    get_roi_by_marketplace,
    get_roi_by_strategy,
    get_profitable_strategies,
    get_cost_history,
    # Confidence endpoints
    get_confidence_recommendation,
    get_confidence_summary,
    # Threshold endpoints
    create_threshold_petition,
    get_current_threshold,
    list_threshold_petitions,
    decide_threshold_petition,
    # Auto-threshold endpoints
    evaluate_auto_threshold,
    rollback_auto_threshold,
    get_auto_threshold_status,
    # Marketplace OAuth endpoints
    initiate_oauth,
    oauth_callback,
    get_oauth_status,
    refresh_oauth_token,
    revoke_oauth_token,
    # Learning endpoints
    record_job_completion,
    get_prediction_accuracy,
    get_learning_insights,
)

# Export all symbols for backward compatibility
__all__ = [
    # App
    "app",
    "lifespan",
    # Models
    "TaskSubmission",
    "CheckoutResponse",
    "DeliveryTokenRequest",
    "DeliveryResponse",
    "AddressValidationModel",
    "DeliveryAmountModel",
    "DeliveryTimestampModel",
    # Database models
    "Task",
    "Bid",
    "ArenaCompetition",
    "ClientProfile",
    "UserQuota",
    "QuotaUsage",
    "RateLimitLog",
    "SimulationBid",
    "ThresholdPetition",
    "CostEntry",
    "ConfidenceEntry",
    "ConfidenceAdjustment",
    "VirtualWallet",
    "WebhookSecret",
    "LearningEntry",
    "DistributedLock",
    "EscalationLog",
    # Enums
    "TaskStatus",
    "ExecutionStatus",
    "PlanningStatus",
    "ReviewStatus",
    "OutputType",
    "ArenaCompetitionStatus",
    "BidStatus",
    "PricingTier",
    # Financial
    "DOMAIN_BASE_RATES",
    "COMPLEXITY_MULTIPLIERS",
    "URGENCY_MULTIPLIERS",
    "DOMAIN_PRICES",
    "REPEAT_CLIENT_DISCOUNTS",
    "MAX_DISCOUNT",
    "calculate_task_price",
    "get_client_discount",
    "get_discount_tier",
    # Threshold
    "HIGH_VALUE_THRESHOLD",
    "MAX_RETRY_ATTEMPTS",
    "_should_escalate_task",
    "_escalate_task",
    # Files/Delivery
    "_delivery_rate_limits",
    "_delivery_ip_rate_limits",
    "_check_delivery_rate_limit",
    "_record_delivery_failure",
    "_check_delivery_ip_rate_limit",
    "_record_ip_delivery_attempt",
    "_sanitize_string",
    # Learning
    "EXPERIENCE_DB_AVAILABLE",
    "ExperienceLogger",
    "ArenaLearningLogger",
    "_log_arena_learning",
    "experience_logger",
    # System
    "create_app",
    "get_system_mode",
    "set_system_mode",
    # Endpoints
    "create_checkout_session",
    "get_domains",
    "get_price_estimate",
    "get_task",
    "get_task_by_session",
    "get_client_task_history",
    "get_client_discount_info",
    "get_secure_delivery",
    "process_task_async",
    "run_autonomous_loop",
    # Arena
    "run_arena_competition",
    "get_arena_history",
    "get_arena_stats",
    # Financial endpoints
    "get_financial_status",
    "add_seed_money",
    "set_budget",
    "get_roi_by_marketplace",
    "get_roi_by_strategy",
    "get_profitable_strategies",
    "get_cost_history",
    # Confidence
    "get_confidence_recommendation",
    "get_confidence_summary",
    # Threshold
    "create_threshold_petition",
    "get_current_threshold",
    "list_threshold_petitions",
    "decide_threshold_petition",
    "evaluate_auto_threshold",
    "rollback_auto_threshold",
    "get_auto_threshold_status",
    # OAuth
    "initiate_oauth",
    "oauth_callback",
    "get_oauth_status",
    "refresh_oauth_token",
    "revoke_oauth_token",
    # Learning
    "record_job_completion",
    "get_prediction_accuracy",
    "get_learning_insights",
    # Utilities
    "generate_proposal",
]
