"""
Task management endpoints for ArbitrageAI.

Handles:
- Task retrieval and status
- Task delivery with secure tokens
- Arena competitions
- Admin metrics
- System mode management

Issue #193: Fix N+1 Query Problems with Eager Loading
- Added joinedload/selectinload for Task relationships
- Preloads execution, planning, review, arena, and outputs
"""

from datetime import datetime, timezone
import os
import time as _time

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from src.config.config_manager import ConfigManager
from src.utils.logger import get_logger

from .database import get_db
from .models import (
    ArenaCompetition,
    ArenaCompetitionStatus,
    EscalationLog,
    ReviewStatus,
    Task,
    TaskStatus,
)

# Create router for task endpoints
router = APIRouter(prefix="/tasks", tags=["tasks"])

# Create separate router for delivery endpoints (needs /api/delivery path)
delivery_router = APIRouter(prefix="/delivery", tags=["delivery"])

# Initialize logger
logger = get_logger(__name__)

# =============================================================================
# ESCALATION & HUMAN-IN-THE-LOOP (HITL) CONFIGURATION (Pillar 1.7)
# =============================================================================

# High-value threshold for profit protection (in dollars)
HIGH_VALUE_THRESHOLD = ConfigManager.get("HIGH_VALUE_THRESHOLD")

# Maximum number of retry attempts before escalation (matches executor.py)
MAX_RETRY_ATTEMPTS = ConfigManager.get("MAX_RETRY_ATTEMPTS")

# Delivery token TTL in hours (configurable via env)
DELIVERY_TOKEN_TTL_HOURS = ConfigManager.get("DELIVERY_TOKEN_TTL_HOURS")

# Rate limiting: max failed delivery attempts per task before lockout
DELIVERY_MAX_FAILED_ATTEMPTS = ConfigManager.get("DELIVERY_MAX_FAILED_ATTEMPTS")
DELIVERY_LOCKOUT_SECONDS = ConfigManager.get("DELIVERY_LOCKOUT_SECONDS")

# IP-based rate limiting
DELIVERY_MAX_ATTEMPTS_PER_IP = ConfigManager.get("DELIVERY_MAX_ATTEMPTS_PER_IP")
DELIVERY_IP_LOCKOUT_SECONDS = ConfigManager.get("DELIVERY_IP_LOCKOUT_SECONDS")

# In-memory rate limiter for backward compatibility with tests
# In production, Redis is used instead (QAQC-009)
# These are imported from main.py where they're properly initialized
# to avoid circular import issues
_delivery_rate_limits: dict[str, tuple[int, float]] = {}
_delivery_ip_rate_limits: dict[str, tuple[int, float]] = {}


def _get_delivery_rate_limits():
    """Get the delivery rate limits dict from main module."""
    from .main import _delivery_rate_limits as main_limits
    return main_limits


def _get_delivery_ip_rate_limits():
    """Get the delivery IP rate limits dict from main module."""
    from .main import _delivery_ip_rate_limits as main_ip_limits
    return main_ip_limits


# Redis rate limiter instance (lazy-loaded)
_redis_rate_limiter = None


def _get_redis_rate_limiter():
    """Get or create Redis rate limiter instance."""
    global _redis_rate_limiter
    if _redis_rate_limiter is None:
        # Check if rate limiting should be disabled (for tests)
        if os.getenv("DISABLE_RATE_LIMITING") == "true":
            return None

        try:
            from src.utils.redis_rate_limiter import RedisRateLimiter
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            _redis_rate_limiter = RedisRateLimiter(redis_url=redis_url, key_prefix="delivery")
            return _redis_rate_limiter
        except ImportError:
            logger.warning("Redis rate limiter module not available, using in-memory")
            return None
        except Exception as e:
            logger.warning(f"Redis rate limiter initialization failed: {e}, using in-memory")
            return None
    return _redis_rate_limiter


def _reset_redis_rate_limiter() -> None:
    """Reset the Redis rate limiter. Useful for testing."""
    global _redis_rate_limiter
    _redis_rate_limiter = None


def _check_delivery_rate_limit(task_id: str) -> bool:
    """
    Check if a task_id is rate-limited for delivery attempts.

    Uses Redis for distributed rate limiting (QAQC-009).
    Falls back to in-memory limiting when Redis unavailable.

    Returns True if the request is allowed, False if rate-limited.
    """
    # Try Redis first
    limiter = _get_redis_rate_limiter()
    if limiter:
        try:
            allowed, _ = limiter.check_rate_limit(
                key=f"task:{task_id}",
                max_requests=DELIVERY_MAX_FAILED_ATTEMPTS,
                window_seconds=DELIVERY_LOCKOUT_SECONDS,
                algorithm="sliding",
            )
            return allowed
        except Exception as e:
            logger.warning(f"Redis rate limit check failed: {e}, using in-memory fallback")

    # Fallback to in-memory (for tests or when Redis unavailable)
    limits = _get_delivery_rate_limits()
    entry = limits.get(task_id)
    if entry is None:
        return True

    fail_count, first_fail_ts = entry
    # Reset if lockout window has passed
    if _time.time() - first_fail_ts > DELIVERY_LOCKOUT_SECONDS:
        del limits[task_id]
        return True

    return fail_count < DELIVERY_MAX_FAILED_ATTEMPTS


def _record_delivery_failure(task_id: str, ip: str | None = None) -> None:
    """
    Record a failed delivery attempt for rate limiting.

    Uses Redis for distributed tracking (QAQC-009).
    Also updates in-memory dict for backward compatibility.
    """
    # Record in Redis
    limiter = _get_redis_rate_limiter()
    if limiter:
        try:
            limiter.record_event(f"task:{task_id}", "failure")
            if ip:
                limiter.record_event(f"ip:{ip}", "failure")
        except Exception as e:
            logger.warning(f"Failed to record delivery failure in Redis: {e}")

    # Also update in-memory for backward compatibility
    limits = _get_delivery_rate_limits()
    entry = limits.get(task_id)
    if entry is None:
        limits[task_id] = (1, _time.time())
    else:
        fail_count, first_fail_ts = entry
        limits[task_id] = (fail_count + 1, first_fail_ts)


def _check_delivery_ip_rate_limit(ip: str) -> bool:
    """
    Check if an IP is rate-limited for delivery attempts.

    Uses in-memory dict first for consistent test behavior,
    then Redis for distributed rate limiting (QAQC-009).

    Returns True if the request is allowed, False if rate-limited.
    """
    # Check in-memory first for consistent behavior
    ip_limits = _get_delivery_ip_rate_limits()
    entry = ip_limits.get(ip)
    if entry is not None:
        attempt_count, first_attempt_ts = entry
        # Reset if lockout window has passed
        if _time.time() - first_attempt_ts > DELIVERY_IP_LOCKOUT_SECONDS:
            del ip_limits[ip]
        else:
            # Allow if under limit, deny if at or over limit
            return attempt_count < DELIVERY_MAX_ATTEMPTS_PER_IP

    # Try Redis for distributed rate limiting
    limiter = _get_redis_rate_limiter()
    if limiter:
        try:
            allowed, _ = limiter.check_rate_limit(
                key=f"ip:{ip}",
                max_requests=DELIVERY_MAX_ATTEMPTS_PER_IP,
                window_seconds=DELIVERY_IP_LOCKOUT_SECONDS,
                algorithm="sliding",
            )
            return allowed
        except Exception as e:
            logger.warning(f"Redis IP rate limit check failed: {e}, using in-memory fallback")

    # Default allow
    return True


def _record_ip_delivery_attempt(ip: str) -> None:
    """
    Record a delivery attempt for IP rate limiting.

    Uses Redis for distributed tracking (QAQC-009).
    Also updates in-memory dict for backward compatibility.
    """
    # Record in Redis
    limiter = _get_redis_rate_limiter()
    if limiter:
        try:
            limiter.record_event(f"ip:{ip}", "attempt")
        except Exception as e:
            logger.warning(f"Failed to record IP attempt in Redis: {e}")

    # Also update in-memory for backward compatibility
    ip_limits = _get_delivery_ip_rate_limits()
    entry = ip_limits.get(ip)
    if entry is None:
        ip_limits[ip] = (1, _time.time())
    else:
        attempt_count, first_attempt_ts = entry
        ip_limits[ip] = (attempt_count + 1, first_attempt_ts)


def _should_escalate_task(
    task,
    retry_count: int,
    error_message: str | None = None,
) -> tuple:
    """
    Determine if a task should be escalated to human review.

    Escalation criteria (Pillar 1.7):
    1. Agent failed after MAX_RETRY_ATTEMPTS (3 retries)
    2. High-value task ($200+) failed (profit protection)

    Args:
        task: The Task object
        retry_count: Number of retry attempts made
        error_message: Optional error message from the failure

    Returns:
        Tuple of (should_escalate: bool, reason: str or None)
    """
    # Check if this is a high-value task
    amount_dollars = (task.amount_paid / 100) if task.amount_paid else 0
    is_high_value = amount_dollars >= HIGH_VALUE_THRESHOLD

    # Check if retries were exhausted
    if retry_count >= MAX_RETRY_ATTEMPTS:
        reason = "max_retries_exceeded"
        if is_high_value:
            reason = "max_retries_exceeded_high_value"
        return True, reason

    # High-value task failed - always escalate for profit protection
    if is_high_value and error_message:
        reason = "high_value_task_failed"
        return True, reason

    return False, None


async def _escalate_task(
    db,
    task,
    reason: str,
    error_message: str | None = None,
):
    """
    Escalate a task to human review with idempotent notification.

    Uses a database transaction (savepoint) to atomically update the task
    status and create the EscalationLog entry.

    Args:
        db: Database session
        task: The Task object to escalate
        reason: Reason for escalation
        error_message: Optional error details
    """
    # Get logger instance
    logger = get_logger(__name__)

    # Log the escalation for profit protection
    amount_dollars = (task.amount_paid / 100) if task.amount_paid else 0
    is_high_value = amount_dollars >= HIGH_VALUE_THRESHOLD

    logger.warning(f"[ESCALATION] Task {task.id} escalated: {reason}")
    logger.warning(
        f"[ESCALATION] Amount: ${amount_dollars}, High-value: {is_high_value}",
    )

    if error_message:
        logger.warning(f"[ESCALATION] Error: {error_message[:200]}...")

    # Check for idempotency via EscalationLog
    idempotency_key = f"{task.id}_{reason}"
    should_send_notification = False
    escalation_log = None

    try:
        # Use a savepoint so that if escalation log fails, we can still
        # update the task status without losing the outer transaction
        db.begin_nested()

        # Update task status atomically with escalation log
        task.status = TaskStatus.ESCALATION
        task.escalation_reason = reason
        task.escalated_at = datetime.now(timezone.utc)
        task.last_error = error_message
        task.review_status = ReviewStatus.PENDING

        escalation_log = (
            db.query(EscalationLog)
            .filter(EscalationLog.idempotency_key == idempotency_key)
            .first()
        )

        if escalation_log is None:
            # First escalation - create new log
            escalation_log = EscalationLog(
                task_id=task.id,
                reason=reason,
                error_message=error_message,
                idempotency_key=idempotency_key,
                amount_paid=task.amount_paid,
                domain=task.domain,
                client_email=task.client_email,
                notification_sent=False,
                notification_attempt_count=0,
            )
            db.add(escalation_log)

        # Determine if notification should be sent (before commit)
        should_send_notification = (
            is_high_value and not escalation_log.notification_sent
        )

        # Commit the savepoint
        db.commit()

    except Exception as e:
        db.rollback()
        logger.error(
            f"[ESCALATION] Database error in escalation transaction: {e}",
            exc_info=True,
        )
        task.status = TaskStatus.ESCALATION
        task.escalation_reason = reason
        task.escalated_at = datetime.now(timezone.utc)
        task.last_error = error_message
        task.review_status = ReviewStatus.PENDING
        db.commit()
        return

    # Send notification AFTER DB commit succeeds
    if should_send_notification and escalation_log is not None:
        try:
            from src.utils.notifications import TelegramNotifier

            notifier = TelegramNotifier()
            context = f"Reason: {reason}"
            if error_message:
                context += f"\nError: {error_message[:200]}"

            notification_sent = await notifier.request_human_help(
                task_id=task.id,
                context=context,
                amount_paid=task.amount_paid,
                domain=task.domain,
                client_email=task.client_email,
            )

            # Update escalation log with notification result
            escalation_log.notification_sent = notification_sent
            escalation_log.notification_attempt_count += 1
            escalation_log.last_notification_attempt_at = datetime.now(timezone.utc)

            if notification_sent:
                logger.info(
                    f"[ESCALATION] Telegram notification sent for high-value task {task.id}",
                )
            else:
                escalation_log.notification_error = (
                    "Notification returned False after retries"
                )
                logger.warning(
                    f"[ESCALATION] Telegram notification failed for task {task.id}",
                )

            db.commit()
        except Exception as e:
            escalation_log.notification_attempt_count += 1
            escalation_log.last_notification_attempt_at = datetime.now(timezone.utc)
            escalation_log.notification_error = str(e)[:500]
            logger.error(
                f"[ESCALATION] Failed to send Telegram notification: {e}",
                exc_info=True,
            )
            db.commit()
    elif escalation_log is not None and not should_send_notification:
        escalation_log.notification_attempt_count += 1
        escalation_log.last_notification_attempt_at = datetime.now(timezone.utc)
        db.commit()


# =============================================================================
# TASK RETRIEVAL ENDPOINTS
# =============================================================================


@router.get("/{task_id}", response_model=dict)
async def get_task(task_id: str, db: Session = Depends(get_db)):  # noqa: B008
    """
    Get task by ID.

    Uses eager loading to prevent N+1 queries on relationships.

    Args:
        task_id: Task ID
        db: Database session

    Returns:
        Task details
    """
    task = (
        db.query(Task)
        .filter(Task.id == task_id)
        .options(
            joinedload(Task.execution),
            joinedload(Task.planning),
            joinedload(Task.review),
            joinedload(Task.arena),
            selectinload(Task.outputs),
        )
        .first()
    )

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task.to_dict()


@router.get("/session/{session_id}")
async def get_task_by_session(
    session_id: str,
    db: Session = Depends(get_db),  # noqa: B008
):
    """
    Get task ID and authentication token by Stripe checkout session ID.

    Uses eager loading to prevent N+1 queries on relationships.

    Args:
        session_id: Stripe session ID
        db: Database session

    Returns:
        Task ID and client authentication token
    """
    from src.utils.client_auth import generate_client_token

    task = (
        db.query(Task)
        .filter(Task.stripe_session_id == session_id)
        .options(
            joinedload(Task.execution),
            joinedload(Task.planning),
            joinedload(Task.review),
            joinedload(Task.arena),
            selectinload(Task.outputs),
        )
        .first()
    )

    if not task:
        raise HTTPException(status_code=404, detail="Task not found for this session")

    # Generate client auth token if email was provided
    client_token = None
    if task.client_email:
        client_token = generate_client_token(task.client_email)

    return {
        "task_id": task.id,
        "client_email": task.client_email,
        "client_auth_token": client_token,
    }


@delivery_router.get("/{task_id}/{token}")
async def get_secure_delivery(
    task_id: str,
    token: str,
    request: Request,
    db: Session = Depends(get_db),  # noqa: B008
):
    """
    Secure delivery endpoint with token validation and rate limiting.

    Args:
        task_id: Task ID
        token: Delivery token
        request: Request object for client IP extraction
        db: Database session

    Returns:
        Delivery response with artifact URLs
    """
    # Extract client IP for rate limiting
    ip = request.client.host if request.client else None

    from pydantic import ValidationError

    from .main import DeliveryResponse, DeliveryTokenRequest

    # Validate request
    try:
        DeliveryTokenRequest(task_id=task_id, token=token)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"Invalid request: {e!s}") from e

    # Check rate limits
    if not _check_delivery_rate_limit(task_id):
        logger.warning(f"Task {task_id} rate-limited for delivery")
        raise HTTPException(
            status_code=429,
            detail="Too many delivery attempts. Please try again later.",
        )

    if ip and not _check_delivery_ip_rate_limit(ip):
        logger.warning(f"IP {ip} rate-limited for delivery")
        raise HTTPException(
            status_code=429,
            detail="Too many requests from your IP. Please try again later.",
        )

    # Record IP attempt
    if ip:
        _record_ip_delivery_attempt(ip)

    # Validate token and get task
    task = (
        db.query(Task)
        .filter(Task.id == task_id)
        .options(
            joinedload(Task.execution),
            joinedload(Task.planning),
            joinedload(Task.review),
            joinedload(Task.arena),
            selectinload(Task.outputs),
        )
        .first()
    )

    if not task:
        _record_delivery_failure(task_id, ip)
        raise HTTPException(status_code=404, detail="Task not found")

    # Validate token
    if task.delivery_token != token:
        _record_delivery_failure(task_id, ip)
        logger.warning(f"Invalid delivery token for task {task_id}")
        raise HTTPException(status_code=401, detail="Invalid delivery token")

    # Check token expiration (skip if None for backward compatibility)
    if (
        task.delivery_token_expires_at is not None
        and task.delivery_token_expires_at < datetime.now(timezone.utc)
    ):
        _record_delivery_failure(task_id, ip)
        logger.warning(f"Expired delivery token for task {task_id}")
        raise HTTPException(status_code=401, detail="Delivery token has expired")

    # Check if token has already been used (one-time use)
    if task.delivery_token_used:
        _record_delivery_failure(task_id, ip)
        logger.warning(f"Delivery token already used for task {task_id}")
        raise HTTPException(status_code=403, detail="Delivery token has already been used")

    # Check if task is completed
    if task.status != TaskStatus.COMPLETED:
        _record_delivery_failure(task_id, ip)
        logger.warning(
            f"Task {task_id} not completed, status: {task.status}",
        )
        raise HTTPException(
            status_code=400,
            detail=f"Task not completed. Status: {task.status}",
        )

    # Mark token as used
    task.delivery_token_used = True
    db.commit()

    # Return delivery response
    return DeliveryResponse(
        task_id=task.id,
        title=task.title,
        domain=task.domain,
        result_type=task.result_type or "image",
        result_url=task.result_document_url or task.result_spreadsheet_url or task.result_image_url,
        result_image_url=task.result_image_url,
        result_document_url=task.result_document_url,
        result_spreadsheet_url=task.result_spreadsheet_url,
        delivered_at=datetime.now(timezone.utc).isoformat(),
    )


# =============================================================================
# ARENA COMPETITION ENDPOINTS
# =============================================================================


async def run_arena_competition(
    task_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),  # noqa: B008
):
    """
    Run an arena competition for a task.

    Args:
        task_id: Task ID
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Arena competition result
    """
    from src.agent_execution.arena import CompetitionType, run_agent_arena

    task = (
        db.query(Task)
        .filter(Task.id == task_id)
        .options(
            joinedload(Task.execution),
            joinedload(Task.planning),
            joinedload(Task.review),
            joinedload(Task.arena),
            selectinload(Task.outputs),
        )
        .first()
    )

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != TaskStatus.PAID:
        raise HTTPException(
            status_code=400,
            detail=f"Task must be in PAID status, current: {task.status}",
        )

    # Run arena in background
    async def run_arena_bg():
        await run_agent_arena(
            user_request=task.description or task.title,
            domain=task.domain,
            csv_data=task.csv_data,
            file_content=task.file_content,
            filename=task.filename,
            file_type=task.file_type,
            api_key=os.environ.get("E2B_API_KEY"),
            competition_type=CompetitionType.MODEL,
            task_revenue=task.amount_paid or 500,
            enable_learning=True,
            task_data={
                "id": task.id,
                "domain": task.domain,
                "description": task.description or task.title,
                "client_email": task.client_email,
            },
        )

    background_tasks.add_task(run_arena_bg)

    return {
        "task_id": task_id,
        "status": "arena_started",
        "message": "Arena competition started in background",
    }


async def get_arena_history(
    db: Session = Depends(get_db),  # noqa: B008
    limit: int = 20,
):
    """
    Get arena competition history.

    Uses eager loading to prevent N+1 queries on task relationships.

    Args:
        db: Database session
        limit: Number of results to return

    Returns:
        List of arena competitions
    """
    competitions = (
        db.query(ArenaCompetition)
        .filter(ArenaCompetition.status == ArenaCompetitionStatus.COMPLETED)
        .options(joinedload(ArenaCompetition.task))
        .order_by(ArenaCompetition.created_at.desc())
        .limit(limit)
        .all()
    )

    return [comp.to_dict() for comp in competitions]


async def get_arena_stats(db: Session = Depends(get_db)):  # noqa: B008
    """
    Get arena competition statistics.

    Args:
        db: Database session

    Returns:
        Arena statistics
    """
    total = db.query(ArenaCompetition).count()
    completed = (
        db.query(ArenaCompetition)
        .filter(ArenaCompetition.status == ArenaCompetitionStatus.COMPLETED)
        .count()
    )

    # Get win rates
    agent_a_wins = (
        db.query(ArenaCompetition)
        .filter(ArenaCompetition.winner == "agent_a")
        .count()
    )
    agent_b_wins = (
        db.query(ArenaCompetition)
        .filter(ArenaCompetition.winner == "agent_b")
        .count()
    )

    return {
        "total_competitions": total,
        "completed": completed,
        "agent_a_wins": agent_a_wins,
        "agent_b_wins": agent_b_wins,
        "agent_a_win_rate": (agent_a_wins / completed * 100) if completed > 0 else 0,
        "agent_b_win_rate": (agent_b_wins / completed * 100) if completed > 0 else 0,
    }


# =============================================================================
# ADMIN ENDPOINTS
# =============================================================================


async def get_admin_metrics(db: Session = Depends(get_db)):  # noqa: B008
    """
    Get admin metrics for system monitoring.

    Args:
        db: Database session

    Returns:
        System metrics and statistics
    """
    # Task statistics
    total_tasks = db.query(Task).count()
    pending_tasks = (
        db.query(Task).filter(Task.status == TaskStatus.PENDING).count()
    )
    paid_tasks = db.query(Task).filter(Task.status == TaskStatus.PAID).count()
    processing_tasks = (
        db.query(Task).filter(Task.status == TaskStatus.PROCESSING).count()
    )
    completed_tasks = (
        db.query(Task).filter(Task.status == TaskStatus.COMPLETED).count()
    )
    failed_tasks = db.query(Task).filter(Task.status == TaskStatus.FAILED).count()
    escalation_tasks = (
        db.query(Task).filter(Task.status == TaskStatus.ESCALATION).count()
    )

    # Revenue statistics
    total_revenue = (
        db.query(Task)
        .filter(Task.status == TaskStatus.COMPLETED)
        .with_entities(func.sum(Task.amount_paid))
        .scalar()
        or 0
    )

    # High-value tasks
    high_value_tasks = db.query(Task).filter(Task.is_high_value).count()

    return {
        "tasks": {
            "total": total_tasks,
            "pending": pending_tasks,
            "paid": paid_tasks,
            "processing": processing_tasks,
            "completed": completed_tasks,
            "failed": failed_tasks,
            "escalation": escalation_tasks,
        },
        "revenue": {
            "total_cents": total_revenue,
            "total_dollars": total_revenue / 100,
        },
        "high_value_tasks": high_value_tasks,
        "success_rate": (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0,
    }


# =============================================================================
# BACKWARD COMPATIBILITY RE-EXPORTS
# =============================================================================

__all__ = [
    "DELIVERY_IP_LOCKOUT_SECONDS",
    "DELIVERY_LOCKOUT_SECONDS",
    "DELIVERY_MAX_ATTEMPTS_PER_IP",
    "DELIVERY_MAX_FAILED_ATTEMPTS",
    "DELIVERY_TOKEN_TTL_HOURS",
    "HIGH_VALUE_THRESHOLD",
    "MAX_RETRY_ATTEMPTS",
    "_check_delivery_ip_rate_limit",
    "_check_delivery_rate_limit",
    "_escalate_task",
    "_record_delivery_failure",
    "_record_ip_delivery_attempt",
    "_should_escalate_task",
    "get_admin_metrics",
    "get_arena_history",
    "get_arena_stats",
    "get_secure_delivery",
    "get_task",
    "get_task_by_session",
    "run_arena_competition",
]
