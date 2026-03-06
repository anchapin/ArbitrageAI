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

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationInfo, field_validator, ValidationError
import stripe
import secrets
from datetime import datetime, timezone

# Import Agent Arena modules
# Import executor for backward compatibility
# Import Market Scanner
# Import Agent execution modules
# Import API routes
from src.api.analytics import register_analytics_routes
from src.api.disaster_recovery import router as disaster_recovery_router
from src.api.payments import router as payments_router

# Import function for checkout endpoint
from src.api.payments import create_checkout_session as payments_create_checkout_session

# Import files module for rate limiting functions
from src.api import files

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
from .database import Session, get_db

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
app.include_router(payments_router, prefix="/api", tags=["payments"])

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


@app.post("/api/create-checkout-session", response_model=CheckoutResponse)
async def create_checkout_session_endpoint(
    task: TaskSubmission,
    db: Session = Depends(get_db),  # noqa: B008
):
    """Create a Stripe checkout session based on task submission.

    Calculates price using the Task Price Formula (Pillar 1.4):
    Price = Base Rate × Complexity × Urgency

    Creates a real Stripe checkout session.
    Stores the task in the database with PENDING status.

    Args:
        task: TaskSubmission model with task details
        db: Database session

    Returns:
        CheckoutResponse with session ID and URL
    """
    # Call the function from payments module
    return await payments_create_checkout_session(task, db)


@app.get("/api/delivery/{task_id}/{token}")
async def get_secure_delivery(
    task_id: str, token: str, request: Request, db: Session = Depends(get_db),  # noqa: B008
) -> DeliveryResponse:
    """
    Secure delivery link endpoint with comprehensive validation (Issue #18).

    Security Measures:
    1. Input Validation: Pydantic model validates task_id (UUID) and token format
    2. IP-based Rate Limiting: Max 20 attempts per IP per hour
    3. Task-based Rate Limiting: Max 5 failed attempts per task per hour
    4. Token Verification: Constant-time comparison to prevent timing attacks
    5. Token Expiration: Configurable TTL (default 1 hour)
    6. One-Time Use: Token invalidated after successful download
    7. Status Validation: Task must be COMPLETED
    8. Audit Logging: All attempts logged for security analysis
    9. Input Sanitization: String fields sanitized for injection prevention
    """
    logger = get_logger(__name__)
    client_ip = request.client.host if request.client else "unknown"

    # 1. INPUT VALIDATION - Pydantic validation with strict rules
    try:
        validated = DeliveryTokenRequest(task_id=task_id, token=token)
        validated_task_id = validated.task_id
        validated_token = validated.token
    except ValidationError as e:
        logger.warning(f"[DELIVERY] Validation failed: {e!s} ip={client_ip}")
        files._record_ip_delivery_attempt(client_ip)
        files._record_delivery_failure(task_id, client_ip)
        raise HTTPException(status_code=400, detail=f"Invalid input: {e!s}") from e
    except (ValueError, TypeError) as e:
        logger.warning(f"[DELIVERY] Type validation failed: {e!s} ip={client_ip}")
        files._record_ip_delivery_attempt(client_ip)
        files._record_delivery_failure(task_id, client_ip)
        raise HTTPException(status_code=400, detail=f"Invalid input: {e!s}") from e
    except Exception as e:
        logger.warning(f"[DELIVERY] Validation failed: {e!s} ip={client_ip}")
        files._record_ip_delivery_attempt(client_ip)
        files._record_delivery_failure(task_id, client_ip)
        raise HTTPException(status_code=400, detail=f"Invalid input: {e!s}") from e

    # 2. IP-level rate limiting (Issue #18)
    if not files._check_delivery_ip_rate_limit(client_ip):
        logger.warning(f"[DELIVERY] IP rate limited: ip={client_ip}")
        raise HTTPException(
            status_code=429,
            detail="Too many delivery requests from your IP. Try again later.",
        )

    # 3. Task-level rate limiting
    if not files._check_delivery_rate_limit(validated_task_id):
        logger.warning(
            f"[DELIVERY] Task rate limited: task={validated_task_id} ip={client_ip}",
        )
        files._record_delivery_failure(validated_task_id, client_ip)
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts for this task. Try again later.",
        )

    task = db.query(Task).filter(Task.id == validated_task_id).options().first()

    if not task:
        files._record_ip_delivery_attempt(client_ip)
        files._record_delivery_failure(validated_task_id, client_ip)
        logger.warning(f"[DELIVERY] Not found: task={validated_task_id} ip={client_ip}")
        raise HTTPException(status_code=404, detail="Task not found")

    # 4. Token verification (constant-time comparison)
    if not task.delivery_token or not secrets.compare_digest(
        task.delivery_token, validated_token,
    ):
        files._record_ip_delivery_attempt(client_ip)
        files._record_delivery_failure(validated_task_id, client_ip)
        logger.warning(
            f"[DELIVERY] Invalid token: task={validated_task_id} ip={client_ip}",
        )
        raise HTTPException(status_code=403, detail="Invalid delivery token")

    # 5. Token expiration check
    if task.delivery_token_expires_at:
        expires_at = task.delivery_token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires_at:
            files._record_ip_delivery_attempt(client_ip)
            files._record_delivery_failure(validated_task_id, client_ip)
            logger.warning(
                f"[DELIVERY] Token expired: task={validated_task_id} ip={client_ip}",
            )
            raise HTTPException(status_code=410, detail="Delivery token has expired")

    # 5b. Check if token was already used
    if task.delivery_token_used:
        files._record_ip_delivery_attempt(client_ip)
        files._record_delivery_failure(validated_task_id, client_ip)
        logger.warning(
            f"[DELIVERY] Already used token: task={validated_task_id} ip={client_ip}",
        )
        raise HTTPException(
            status_code=403, detail="Delivery link has already been used",
        )

    # 6. Check if task is completed
    if task.status != TaskStatus.COMPLETED:
        files._record_ip_delivery_attempt(client_ip)
        files._record_delivery_failure(validated_task_id, client_ip)
        logger.warning(
            f"[DELIVERY] Task not completed: task={validated_task_id} status={task.status} ip={client_ip}",
        )
        raise HTTPException(
            status_code=400,
            detail=f"Task is not ready for delivery. Current status: {task.status.value}",
        )

    # 7. Validate result URLs
    result_url = (
        task.result_spreadsheet_url
        or task.result_document_url
        or task.result_image_url
    )
    if not result_url:
        logger.warning(
            f"[DELIVERY] No result URL: task={validated_task_id} ip={client_ip}",
        )
        raise HTTPException(
            status_code=404, detail="No delivery content available for this task",
        )

    # 8. Mark token as used (one-time use)
    task.delivery_token_used = True
    db.commit()

    # 8. Success - clear rate limits and return delivery
    # Clear IP-level rate limit on success (reward successful requests)
    files._record_ip_delivery_attempt(client_ip)
    logger.info(
        f"[DELIVERY] Success: task={validated_task_id} ip={client_ip}",
    )

    # Get the delivery URL
    result_url = (
        task.result_spreadsheet_url
        or task.result_document_url
        or task.result_image_url
    )

    # Return using JSONResponse to match the original response format

    return JSONResponse(
        content={
            "task_id": task.id,
            "title": files._sanitize_string(task.title),
            "domain": files._sanitize_string(task.domain),
            "result_type": task.result_type,
            "result_url": result_url,
            "result_image_url": task.result_image_url,
            "result_document_url": task.result_document_url,
            "result_spreadsheet_url": task.result_spreadsheet_url,
            "delivered_at": datetime.now(timezone.utc).isoformat(),
        },
        headers={
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
            "Content-Security-Policy": "default-src 'none'",
        },
    )


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
