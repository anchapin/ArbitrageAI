"""
Authentication and OAuth endpoints for ArbitrageAI.

Handles:
- OAuth integration (Upwork, Freelancer, Fiverr)
- Client token generation and verification
- Authentication state management
"""

from datetime import datetime, timezone
import logging

from fastapi import Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.utils.client_auth import generate_client_token, verify_client_token
from src.utils.logger import get_logger

from .database import get_db
from .models import Task

# Initialize logger
logger = get_logger(__name__)


# =============================================================================
# OAUTH INTEGRATION ENDPOINTS
# =============================================================================


async def initiate_oauth(platform: str, redirect_uri: str | None = None):
    """
    Initiate OAuth flow for a marketplace platform.

    Args:
        platform: Marketplace platform (upwork, freelancer, fiverr)
        redirect_uri: Optional redirect URI override

    Returns:
        OAuth authorization URL
    """
    # Placeholder for OAuth implementation
    # In production, this would redirect to the marketplace's OAuth endpoint
    logger.info(f"OAuth initiation requested for platform: {platform}")

    # For now, return a placeholder response
    return {
        "platform": platform,
        "status": "not_configured",
        "message": f"OAuth for {platform} is not yet configured",
    }


async def oauth_callback(
    platform: str,
    code: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),  # noqa: B008
):
    """
    Handle OAuth callback from marketplace platform.

    Args:
        platform: Marketplace platform
        code: Authorization code from marketplace
        error: Error message if OAuth failed
        db: Database session

    Returns:
        Success or error response
    """
    if error:
        logger.error(f"OAuth error for {platform}: {error}")
        return {"status": "error", "message": f"OAuth failed: {error}"}

    if not code:
        raise HTTPException(status_code=400, detail="Authorization code required")

    # Placeholder for OAuth token exchange
    # In production, this would exchange the code for access/refresh tokens
    logger.info(f"OAuth callback received for platform: {platform}")

    return {
        "platform": platform,
        "status": "success",
        "message": f"OAuth successful for {platform}",
    }


async def get_oauth_status(platform: str):
    """
    Get OAuth connection status for a platform.

    Args:
        platform: Marketplace platform

    Returns:
        OAuth status information
    """
    # Placeholder for OAuth status check
    return {
        "platform": platform,
        "connected": False,
        "message": f"OAuth for {platform} is not configured",
    }


async def refresh_oauth_token(platform: str):
    """
    Refresh OAuth access token for a platform.

    Args:
        platform: Marketplace platform

    Returns:
        Token refresh result
    """
    # Placeholder for token refresh
    return {
        "platform": platform,
        "status": "not_configured",
        "message": f"Token refresh for {platform} is not configured",
    }


async def revoke_oauth_token(platform: str):
    """
    Revoke OAuth access token for a platform.

    Args:
        platform: Marketplace platform

    Returns:
        Revocation result
    """
    # Placeholder for token revocation
    return {
        "platform": platform,
        "status": "not_configured",
        "message": f"Token revocation for {platform} is not configured",
    }


# =============================================================================
# CLIENT AUTHENTICATION ENDPOINTS
# =============================================================================


async def get_client_task_history(
    email: str,
    token: str,
    db: Session = Depends(get_db),  # noqa: B008
):
    """
    Get task history for a client by email (authenticated).

    Requires a valid HMAC token proving ownership of the email address.
    The token is provided when a task is created.

    Args:
        email: Client email address
        token: HMAC authentication token for this email
        db: Database session

    Returns:
        Task history with statistics and discount information
    """
    from .main import get_client_discount, get_discount_tier, TaskStatus

    if not verify_client_token(email, token):
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    # Get all tasks for this client
    tasks = (
        db.query(Task)
        .filter(Task.client_email == email)
        .order_by(Task.id.desc())  # Most recent first
        .all()
    )

    # Calculate statistics
    total_tasks = len(tasks)
    completed_tasks = [t for t in tasks if t.status == TaskStatus.COMPLETED]
    completed_count = len(completed_tasks)

    # Calculate total spent (in dollars)
    total_spent = sum(t.amount_paid or 0 for t in completed_tasks) / 100

    # Get current discount
    current_discount = get_client_discount(completed_count)
    current_tier = get_discount_tier(completed_count)

    # Determine next discount tier
    next_tier_info = None
    if current_tier == 0:
        next_tier_info = {"tasks_needed": 1, "discount": 0.05, "label": "5% off"}
    elif current_tier == 1:
        next_tier_info = {"tasks_needed": 1, "discount": 0.10, "label": "10% off"}
    elif current_tier == 2:
        next_tier_info = {"tasks_needed": 3, "discount": 0.15, "label": "15% off"}
    else:
        next_tier_info = None  # Already at max discount

    # Convert tasks to dictionaries
    task_list = []
    for task in tasks:
        task_dict = task.to_dict()
        task_list.append(task_dict)

    return {
        "email": email,
        "total_tasks": total_tasks,
        "completed_tasks": completed_count,
        "total_spent_dollars": total_spent,
        "current_discount": current_discount,
        "current_discount_percent": int(current_discount * 100),
        "next_discount_tier": next_tier_info,
        "tasks": task_list,
    }


async def get_client_discount_info(
    email: str,
    token: str,
    db: Session = Depends(get_db),  # noqa: B008
):
    """
    Get discount information for a client (authenticated).

    Args:
        email: Client email address
        token: HMAC authentication token
        db: Database session

    Returns:
        Discount tier information and progress to next tier
    """
    from .main import get_client_discount, get_discount_tier, TaskStatus

    if not verify_client_token(email, token):
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    # Count completed tasks
    completed_count = (
        db.query(Task)
        .filter(Task.client_email == email, Task.status == TaskStatus.COMPLETED)
        .count()
    )

    # Calculate current discount
    current_discount = get_client_discount(completed_count)
    current_tier = get_discount_tier(completed_count)

    # Determine next tier
    next_tier_info = None
    if current_tier == 0:
        next_tier_info = {
            "tasks_needed": 1,
            "discount": 0.05,
            "discount_percent": 5,
            "label": "5% off",
        }
    elif current_tier == 1:
        next_tier_info = {
            "tasks_needed": 1,
            "discount": 0.10,
            "discount_percent": 10,
            "label": "10% off",
        }
    elif current_tier == 2:
        next_tier_info = {
            "tasks_needed": 3,
            "discount": 0.15,
            "discount_percent": 15,
            "label": "15% off",
        }
    else:
        next_tier_info = {"message": "Maximum discount reached!"}

    return {
        "email": email,
        "completed_tasks": completed_count,
        "current_discount": current_discount,
        "current_discount_percent": int(current_discount * 100),
        "current_tier": current_tier,
        "next_tier": next_tier_info,
        "max_discount": 0.15,
        "max_discount_percent": 15,
    }


# =============================================================================
# BACKWARD COMPATIBILITY RE-EXPORTS
# =============================================================================

# Re-export authentication utilities for backward compatibility
__all__ = [
    "generate_client_token",
    "verify_client_token",
    "initiate_oauth",
    "oauth_callback",
    "get_oauth_status",
    "refresh_oauth_token",
    "revoke_oauth_token",
    "get_client_task_history",
    "get_client_discount_info",
]
