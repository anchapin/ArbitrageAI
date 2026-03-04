"""
Payment processing and pricing endpoints for ArbitrageAI.

Handles:
- Stripe checkout session creation
- Pricing calculations (Task Price Formula)
- Stripe webhook handling
- Payment status management
"""

from datetime import datetime, timedelta, timezone
import os
import secrets
import uuid

from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
import stripe

from src.config.config_manager import ConfigManager
from src.utils.file_validator import validate_file_upload
from src.utils.logger import get_logger

from .database import get_db
from .models import Task, TaskStatus, WebhookSecret

# Initialize logger
logger = get_logger(__name__)

# Configure Stripe (use environment variable in production)
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "sk_test_placeholder")

# Stripe webhook secret (use environment variable in production)
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_placeholder")

# Import Config Manager for thresholds
HIGH_VALUE_THRESHOLD = ConfigManager.get("HIGH_VALUE_THRESHOLD")

# Delivery token TTL in hours (configurable via env)
DELIVERY_TOKEN_TTL_HOURS = ConfigManager.get("DELIVERY_TOKEN_TTL_HOURS")

# Base URL for success/cancel pages (configure in production)
BASE_URL = os.environ.get("BASE_URL", "http://localhost:5173")


# =============================================================================
# PRICING ENGINE - Task Price Formula (Pillar 1.4)
# Price = Base Rate × Complexity × Urgency
# =============================================================================

# Base rates per domain (USD)
DOMAIN_BASE_RATES = {
    "accounting": 100,
    "legal": 175,
    "data_analysis": 150,
}

# Complexity multipliers
COMPLEXITY_MULTIPLIERS = {
    "simple": 1.0,
    "medium": 1.5,
    "complex": 2.0,
}

# Urgency multipliers
URGENCY_MULTIPLIERS = {
    "standard": 1.0,
    "rush": 1.25,
    "urgent": 1.5,
}

# Legacy support - map old flat prices to new base rates for backward compatibility
DOMAIN_PRICES = DOMAIN_BASE_RATES


def calculate_task_price(
    domain: str,
    complexity: str = "medium",
    urgency: str = "standard",
) -> int:
    """
    Calculate task price using the Task Price Formula:
    Price = Base Rate × Complexity × Urgency.

    Args:
        domain: The domain of the task (accounting, legal, data_analysis)
        complexity: Task complexity (simple, medium, complex)
        urgency: Task urgency (standard, rush, urgent)

    Returns:
        Calculated price in USD (cents for Stripe)

    Raises:
        ValueError: If domain, complexity, or urgency is invalid
    """
    # Validate domain
    if domain not in DOMAIN_BASE_RATES:
        valid_domains = ", ".join(DOMAIN_BASE_RATES.keys())
        raise ValueError(f"Invalid domain '{domain}'. Must be one of: {valid_domains}")

    # Validate complexity
    if complexity not in COMPLEXITY_MULTIPLIERS:
        valid_complexities = ", ".join(COMPLEXITY_MULTIPLIERS.keys())
        raise ValueError(
            f"Invalid complexity '{complexity}'. Must be one of: {valid_complexities}",
        )

    # Validate urgency
    if urgency not in URGENCY_MULTIPLIERS:
        valid_urgencies = ", ".join(URGENCY_MULTIPLIERS.keys())
        raise ValueError(
            f"Invalid urgency '{urgency}'. Must be one of: {valid_urgencies}",
        )

    # Calculate price: Base Rate × Complexity × Urgency
    base_rate = DOMAIN_BASE_RATES[domain]
    complexity_multiplier = COMPLEXITY_MULTIPLIERS[complexity]
    urgency_multiplier = URGENCY_MULTIPLIERS[urgency]

    price = base_rate * complexity_multiplier * urgency_multiplier

    # Round to nearest dollar
    return round(price)


# =============================================================================
# STRIPE CHECKOUT ENDPOINTS
# =============================================================================


async def create_checkout_session(task_data, db: Session = Depends(get_db)):  # noqa: B008
    """
    Create a Stripe checkout session based on task submission.

    Calculates price using the Task Price Formula (Pillar 1.4):
    Price = Base Rate × Complexity × Urgency

    Creates a real Stripe checkout session.
    Stores the task in the database with PENDING status.

    Args:
        task_data: TaskSubmission model with task details
        db: Database session

    Returns:
        CheckoutResponse with session ID and URL
    """
    from .main import CheckoutResponse

    # Calculate price using the Task Price Formula
    try:
        amount = calculate_task_price(
            domain=task_data.domain,
            complexity=task_data.complexity,
            urgency=task_data.urgency,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        # Sanitize filename and validate file if present (Issue #34)
        sanitized_filename = task_data.filename
        if task_data.file_content and task_data.filename:
            try:
                sanitized_filename, _, _ = validate_file_upload(
                    filename=task_data.filename,
                    file_content_base64=task_data.file_content,
                    file_type=task_data.file_type,
                )
            except ValueError as e:
                # Should have been caught by Pydantic validator, but safety first
                raise HTTPException(
                    status_code=422,
                    detail=f"File validation failed: {e!s}",
                ) from e

        # Determine if this is a high-value task (Pillar 1.7 - Profit Protection)
        is_high_value = amount >= HIGH_VALUE_THRESHOLD

        # Create a task in the database with PENDING status
        new_task = Task(
            id=str(uuid.uuid4()),
            title=task_data.title,
            description=task_data.description,
            domain=task_data.domain,
            status=TaskStatus.PENDING,
            stripe_session_id=None,
            csv_data=task_data.csvContent,
            file_type=task_data.file_type,
            file_content=task_data.file_content,
            filename=sanitized_filename,
            client_email=task_data.client_email,
            amount_paid=amount * 100,  # Store amount in cents
            delivery_token=secrets.token_urlsafe(32),
            delivery_token_expires_at=datetime.now(timezone.utc)
            + timedelta(hours=DELIVERY_TOKEN_TTL_HOURS),
            is_high_value=is_high_value,
        )
        db.add(new_task)
        db.commit()
        db.refresh(new_task)

        # Create Stripe checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"{task_data.domain.title()} Task: {task_data.title}",
                            "description": task_data.description[:500]
                            if task_data.description
                            else "",
                        },
                        "unit_amount": amount * 100,  # Stripe uses cents
                    },
                    "quantity": 1,
                },
            ],
            mode="payment",
            success_url=f"{BASE_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{BASE_URL}/cancel",
            metadata={
                "task_id": new_task.id,
                "domain": task_data.domain,
                "title": task_data.title,
            },
            billing_address_collection="required",
            shipping_address_collection=None,
            customer_email=task_data.client_email,
        )

        # Update task with Stripe session ID
        new_task.stripe_session_id = checkout_session.id
        db.commit()

        # Generate client auth token for dashboard access (Issue #17)
        from src.utils.client_auth import generate_client_token

        client_token = None
        if task_data.client_email:
            client_token = generate_client_token(task_data.client_email)

        return CheckoutResponse(
            session_id=checkout_session.id,
            url=checkout_session.url,
            amount=amount,
            domain=task_data.domain,
            title=task_data.title,
            client_auth_token=client_token,
        )

    except stripe.error.APIConnectionError as e:
        logger.error(f"Stripe network error: {e}")
        raise HTTPException(
            status_code=503,
            detail="Stripe API is temporarily unavailable (network timeout). Please try again later.",
        ) from e
    except stripe.error.StripeError as e:
        logger.error(f"Stripe general error: {e}")
        raise HTTPException(status_code=500, detail=f"Stripe error: {e!s}") from e
    except OperationalError as e:
        logger.error(f"Database operational error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Database error occurred. Our team has been notified.",
        ) from e
    except Exception as e:
        # Check for concurrency conflicts (Issue #29)
        from sqlalchemy.orm.exc import StaleDataError

        if isinstance(e, StaleDataError):
            logger.warning(f"Concurrency conflict detected: {e}")
            raise HTTPException(
                status_code=409,
                detail="A concurrency conflict occurred. Please try again.",
            ) from e

        logger.error(
            f"Unexpected error creating checkout session: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {e!s}") from e


async def stripe_webhook(
    request,
    background_tasks,
    db: Session = Depends(get_db),  # noqa: B008
    stripe_signature: str | None = None,
):
    """
    Stripe webhook endpoint to handle checkout events.

    Listens for checkout.session.completed events and updates task status to PAID.
    When a task is marked as PAID, a background task is added to process the task asynchronously.

    Args:
        request: FastAPI request object
        background_tasks: FastAPI background tasks
        db: Database session
        stripe_signature: Stripe webhook signature header

    Returns:
        Webhook response
    """
    payload = await request.body()

    # Get all active webhook secrets from the database
    secrets_list = db.query(WebhookSecret).filter(WebhookSecret.is_active).all()

    event = None
    for secret in secrets_list:
        try:
            event = stripe.Webhook.construct_event(
                payload,
                stripe_signature,
                secret.secret,
            )
            # If successful, break the loop
            break
        except stripe.error.SignatureVerificationError:
            # Try the next secret
            continue

    if event is None:
        return JSONResponse(status_code=400, content={"error": "Invalid signature"})

    # Handle the checkout.session.completed event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        session_id = session.get("id")

        # Look up task by stripe_session_id
        task = db.query(Task).filter(Task.stripe_session_id == session_id).first()

        if task:
            # Update task status to PAID
            task.status = TaskStatus.PAID
            db.commit()

            # Add background task to process the visualization asynchronously
            from src.api.main import process_task_async
            from src.experience_vector_db import get_background_job_queue

            EXPERIENCE_DB_AVAILABLE = True
            try:
                from src.experience_vector_db import get_background_job_queue
            except ImportError:
                EXPERIENCE_DB_AVAILABLE = False

            queue = get_background_job_queue() if EXPERIENCE_DB_AVAILABLE else None
            if queue and queue._running:
                await queue.queue_job(
                    job_type="task_processing",
                    task_func=process_task_async,
                    task_args=(task.id,),
                    max_retries=3,
                )
            else:
                background_tasks.add_task(process_task_async, task.id)

            return {
                "status": "success",
                "message": f"Task {task.id} marked as PAID, processing started",
            }
        return {
            "status": "warning",
            "message": f"No task found for session {session_id}",
        }

    # Handle other event types if needed
    if event["type"] == "checkout.session.expired":
        session = event["data"]["object"]
        session_id = session.get("id")

        task = db.query(Task).filter(Task.stripe_session_id == session_id).first()

        if task:
            task.status = TaskStatus.FAILED
            db.commit()

            return {
                "status": "success",
                "message": f"Task {task.id} marked as FAILED (expired)",
            }

    # Return 200 for events we don't handle
    return {"status": "received"}


async def get_domains():
    """
    Get available domains and their pricing configuration.

    Returns:
        Dictionary with domains, complexity levels, and urgency levels
    """
    return {
        "domains": [
            {
                "value": domain,
                "label": domain.replace("_", " ").title(),
                "base_price": price,
            }
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


async def get_price_estimate(
    domain: str,
    complexity: str = "medium",
    urgency: str = "standard",
):
    """
    Calculate a price estimate based on domain, complexity, and urgency.

    Args:
        domain: The task domain (accounting, legal, data_analysis)
        complexity: Task complexity (simple, medium, complex)
        urgency: Task urgency (standard, rush, urgent)

    Returns:
        Calculated price and breakdown of the calculation
    """
    try:
        amount = calculate_task_price(domain, complexity, urgency)
        base_rate = DOMAIN_BASE_RATES[domain]
        complexity_mult = COMPLEXITY_MULTIPLIERS[complexity]
        urgency_mult = URGENCY_MULTIPLIERS[urgency]

        return {
            "domain": domain,
            "complexity": complexity,
            "urgency": urgency,
            "base_rate": base_rate,
            "complexity_multiplier": complexity_mult,
            "urgency_multiplier": urgency_mult,
            "calculated_price": amount,
            "formula": f"${base_rate} × {complexity_mult} × {urgency_mult} = ${amount}",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# =============================================================================
# BACKWARD COMPATIBILITY RE-EXPORTS
# =============================================================================

__all__ = [
    "BASE_URL",
    "COMPLEXITY_MULTIPLIERS",
    "DELIVERY_TOKEN_TTL_HOURS",
    "DOMAIN_BASE_RATES",
    "DOMAIN_PRICES",
    "HIGH_VALUE_THRESHOLD",
    "URGENCY_MULTIPLIERS",
    "calculate_task_price",
    "create_checkout_session",
    "get_domains",
    "get_price_estimate",
    "stripe_webhook",
]
