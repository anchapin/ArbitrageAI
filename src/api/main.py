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
# Import other required modules
import os

from fastapi import Depends, HTTPException
from pydantic import BaseModel, ValidationInfo, field_validator
from sqlalchemy.orm import Session

import stripe

# Import payments module for webhook
from .payments import stripe_webhook

from .database import get_db

# Import auth for endpoints
from src.api.auth import verify_client_token

# Import Agent Arena modules
# Import executor for backward compatibility
# Import Market Scanner
# Import Agent execution modules
# Import API routes
from src.api.analytics import register_analytics_routes
from src.api.disaster_recovery import router as disaster_recovery_router

# Import Config Manager
from src.config.config_manager import ConfigManager

# Import LLM Service
# Import client authentication
# Import file validation utility
from src.utils.file_validator import validate_file_upload

# Import logging module
from src.utils.logger import get_logger

# Import notifications
# Import telemetry
# Import database
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
from .tasks import (  # noqa: F401 - re-exported for tests
    _reset_redis_rate_limiter,
    delivery_router,
    get_arena_history,
    get_arena_stats,
    get_secure_delivery,
    get_task,
    get_task_by_session,
    router as tasks_router,
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
from .learning import (
    EXPERIENCE_DB_AVAILABLE,
    ArenaLearningLogger,
    ExperienceLogger,
    _log_arena_learning,
    experience_logger,
)

# Import models for backward compatibility
from .models import (
    ArenaCompetition,
    ArenaCompetitionStatus,
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
    TaskStatus,
    ThresholdPetition,
    UserQuota,
    VirtualWallet,
    WebhookSecret,
)

# Import Rate Limiting Middleware
# Import Scheduler modules
from .scheduler_endpoints import register_scheduler_routes

# Import Security Headers Middleware
from .system import (
    EXPERIENCE_DB_AVAILABLE as SYSTEM_EXPERIENCE_DB_AVAILABLE,
    create_app,
    get_system_mode,
    lifespan,
    set_system_mode,
)
from .threshold import (
    HIGH_VALUE_THRESHOLD,
    MAX_RETRY_ATTEMPTS,
    _escalate_task,
    _should_escalate_task,
)

# Import API Versioning Middleware

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

# Register disaster recovery router (router already has prefix="/api/disaster-recovery")
app.include_router(disaster_recovery_router, tags=["disaster-recovery"])

# Register tasks router for task delivery and management endpoints
app.include_router(tasks_router, prefix="/api", tags=["tasks"])

# Register delivery router (delivery_router already has prefix="/delivery")
app.include_router(delivery_router, prefix="/api", tags=["delivery"])

# Register scheduler routes
register_scheduler_routes(app)

# Register analytics routes
register_analytics_routes(app)

# Register payments webhook
app.add_api_route("/api/webhook", stripe_webhook, methods=["POST"], tags=["payments"])


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


@app.post("/api/client/calculate-price-with-discount")
async def calculate_price_with_discount(
    domain: str,
    complexity: str = "medium",
    urgency: str = "standard",
    email: str | None = None,
    token: str | None = None,
    db: Session = Depends(get_db),  # noqa: B008 - FastAPI dependency injection pattern
):
    """Calculate price with repeat-client discount for authenticated users."""
    # Verify the client token
    if not email or not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    if not verify_client_token(email, token):
        raise HTTPException(status_code=401, detail="Invalid token")

    # Count completed tasks for this client
    completed_count = (
        db.query(Task)
        .filter(Task.client_email == email, Task.status == TaskStatus.COMPLETED)
        .count()
    )

    # Calculate base price
    base_price = calculate_task_price(domain, complexity, urgency)

    # Get discount
    discount = get_client_discount(completed_count)
    discount_amount = base_price * discount
    final_price = base_price - discount_amount

    return {
        "domain": domain,
        "complexity": complexity,
        "urgency": urgency,
        "base_price": base_price,
        "completed_tasks": completed_count,
        "is_repeat_client": completed_count >= 1,
        "discount_percentage": discount,
        "discount_amount": discount_amount,
        "final_price": final_price,
    }


# Import remaining endpoints from original file for backward compatibility
# These will be gradually migrated to specialized modules
from .main_original import (  # noqa: E402
    add_seed_money,
    # Import the router for registered endpoints
    router as compatibility_router,
    # Import remaining functions
    create_checkout_session,
    # Threshold endpoints
    create_threshold_petition,
    decide_threshold_petition,
    # Auto-threshold endpoints
    evaluate_auto_threshold,
    generate_proposal,
    get_auto_threshold_status,
    get_client_discount_info,
    get_client_task_history,
    # Confidence endpoints
    get_confidence_recommendation,
    get_confidence_summary,
    get_cost_history,
    get_current_threshold,
    # System mode endpoints
    get_financial_status,
    get_learning_insights,
    get_oauth_status,
    get_prediction_accuracy,
    get_profitable_strategies,
    get_roi_by_marketplace,
    get_roi_by_strategy,
    # Marketplace OAuth endpoints
    initiate_oauth,
    list_threshold_petitions,
    oauth_callback,
    process_task_async,
    # Learning endpoints
    record_job_completion,
    refresh_oauth_token,
    revoke_oauth_token,
    rollback_auto_threshold,
    # Arena endpoints
    run_arena_competition,
    run_autonomous_loop,
    set_budget,
)

# Register compatibility router for backward compatibility endpoints
app.include_router(compatibility_router)

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
