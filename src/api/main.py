"""FastAPI backend for ArbitrageAI - Main Module.

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

from fastapi import HTTPException
from pydantic import BaseModel, ValidationInfo, field_validator
import stripe

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
from .tasks import (
    get_arena_history,
    get_arena_stats,
    get_secure_delivery,
    get_task,
    get_task_by_session,
    run_arena_competition,
)
from .auth import (
    get_client_discount_info,
    get_client_task_history,
    get_oauth_status,
    initiate_oauth,
    oauth_callback,
    refresh_oauth_token,
    revoke_oauth_token,
)
from .payments import create_checkout_session

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
        """Validate file upload content against filename and type.

        Args:
            v: The file content value to validate
            info: Validation info containing other field values

        Returns:
            The validated file content

        Raises:
            ValueError: If file validation fails
        """
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
        """Validate that filename is present when file_content is provided.

        Args:
            v: The filename value to validate
            info: Validation info containing other field values

        Returns:
            The validated filename

        Raises:
            ValueError: If filename is missing when file_content is provided
        """
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


# Import remaining endpoints from specialized modules (done above)
# See tasks, auth, payments modules for full implementations

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
    # Endpoints - from tasks module
    "create_checkout_session",
    "get_domains",
    "get_price_estimate",
    "get_task",
    "get_task_by_session",
    "get_client_task_history",
    "get_client_discount_info",
    "get_secure_delivery",
    # Arena
    "run_arena_competition",
    "get_arena_history",
    "get_arena_stats",
    # OAuth
    "initiate_oauth",
    "oauth_callback",
    "get_oauth_status",
    "refresh_oauth_token",
    "revoke_oauth_token",
]
