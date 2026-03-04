"""
Backward compatibility module for API endpoints.

This module re-exports endpoints from their new modular locations
for backward compatibility with existing code.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.database import get_db

# Import from payments module
from src.api.payments import create_checkout_session

# Import from virtual_wallet module
from src.agent_execution.virtual_wallet import VirtualWallet

# Create router
router = APIRouter(prefix="/api", tags=["compatibility"])


# Define schema classes inline to avoid circular imports
class TaskSubmission(BaseModel):
    """Task submission schema for checkout session creation."""
    domain: str
    title: str
    description: str = ""
    complexity: str = "medium"
    urgency: str = "standard"
    client_email: str
    filename: str | None = None
    file_content: str | None = None
    csvContent: str | None = None
    file_type: str | None = None


class CheckoutResponse(BaseModel):
    """Checkout session response schema."""
    session_id: str
    url: str


# Create instance for methods that require instance
_virtual_wallet = VirtualWallet()


def add_seed_money(amount_cents: int) -> bool:
    """Add seed money to virtual wallet (backward compatibility)."""
    return _virtual_wallet.add_seed_money(amount_cents)


# =============================================================================
# Stub implementations for missing functions
# These functions were expected by the API but don't have implementations
# =============================================================================


@router.post("/create-checkout-session", response_model=CheckoutResponse)
async def create_checkout_session_endpoint(
    task_data: TaskSubmission,
    db=Depends(get_db),  # noqa: B008
):
    """Create a Stripe checkout session for task payment."""
    return await create_checkout_session(task_data, db)


async def create_threshold_petition(db, petition_data):
    """Create a threshold petition (stub - not implemented)."""
    raise HTTPException(status_code=501, detail="Threshold petitions not yet implemented")


async def decide_threshold_petition(db, petition_id, decision):
    """Decide a threshold petition (stub - not implemented)."""

    raise HTTPException(status_code=501, detail="Threshold petitions not yet implemented")


async def evaluate_auto_threshold(db, task_id):
    """Evaluate auto threshold (stub - not implemented)."""

    raise HTTPException(status_code=501, detail="Auto threshold not yet implemented")


async def generate_proposal(db, task_id):
    """Generate proposal (stub - not implemented)."""

    raise HTTPException(status_code=501, detail="Proposal generation not yet implemented")


async def get_auto_threshold_status(db):
    """Get auto threshold status (stub - not implemented)."""

    raise HTTPException(status_code=501, detail="Auto threshold not yet implemented")


async def rollback_auto_threshold(db, threshold_id):
    """Rollback auto threshold (stub - not implemented)."""

    raise HTTPException(status_code=501, detail="Auto threshold not yet implemented")


async def list_threshold_petitions(db, status=None, limit=50, offset=0):
    """List threshold petitions (stub - not implemented)."""
    return {"petitions": [], "total": 0}


# Stub: get_current_threshold
async def get_current_threshold(db):
    """Get current threshold (stub - not implemented)."""
    return {"threshold": 0, "domain": "default"}


# Stub: get_financial_status
async def get_financial_status(db):
    """Get financial status (stub - not implemented)."""
    return {"balance": 0, "currency": "USD"}


# Stub: get_secure_delivery
async def get_secure_delivery(db, delivery_token):
    """Get secure delivery (stub - not implemented)."""

    raise HTTPException(status_code=501, detail="Secure delivery not yet implemented")


# Stub: get_task
async def get_task(db, task_id):
    """Get task (stub - not implemented)."""

    raise HTTPException(status_code=501, detail="Task retrieval not yet implemented")


# Stub: get_task_by_session
async def get_task_by_session(db, session_id):
    """Get task by session (stub - not implemented)."""

    raise HTTPException(status_code=501, detail="Task by session not yet implemented")


# Stub: set_budget
async def set_budget(db, budget_data):
    """Set budget (stub - not implemented)."""

    raise HTTPException(status_code=501, detail="Budget management not yet implemented")


# Stub Arena endpoints from learning module
async def get_arena_history(db, limit=50):
    """Get arena history (stub - not implemented)."""
    return {"history": [], "total": 0}


async def get_arena_stats(db):
    """Get arena stats (stub - not implemented)."""
    return {"total_competitions": 0, "win_rate": 0.0}


async def run_arena_competition(db, competition_data):
    """Run arena competition (stub - not implemented)."""

    raise HTTPException(status_code=501, detail="Arena competition not yet implemented")


async def run_autonomous_loop(db):
    """Run autonomous loop (stub - not implemented)."""

    raise HTTPException(status_code=501, detail="Autonomous loop not yet implemented")


async def get_learning_insights(db):
    """Get learning insights (stub - not implemented)."""
    return {"insights": []}


async def get_prediction_accuracy(db):
    """Get prediction accuracy (stub - not implemented)."""
    return {"accuracy": 0.0, "sample_size": 0}


async def get_profitable_strategies(db):
    """Get profitable strategies (stub - not implemented)."""
    return {"strategies": []}


async def get_roi_by_marketplace(db, marketplace):
    """Get ROI by marketplace (stub - not implemented)."""
    return {"marketplace": marketplace, "roi": 0.0}


async def get_roi_by_strategy(db, strategy):
    """Get ROI by strategy (stub - not implemented)."""
    return {"strategy": strategy, "roi": 0.0}


async def record_job_completion(db, job_data):
    """Record job completion (stub - not implemented)."""
    return {"success": True}


# Stub confidence endpoints from analytics module
async def get_confidence_recommendation(db, task_id):
    """Get confidence recommendation (stub - not implemented)."""
    return {"recommendation": "medium", "confidence": 0.5}


async def get_confidence_summary(db):
    """Get confidence summary (stub - not implemented)."""
    return {"summary": {"high": 0, "medium": 0, "low": 0}}


async def get_cost_history(db, days=30):
    """Get cost history (stub - not implemented)."""
    return {"costs": [], "total": 0}


# Stub OAuth endpoints from oauth module
async def get_client_discount_info(db, client_id):
    """Get client discount info (stub - not implemented)."""
    return {"discount": 0, "tier": "standard"}


async def get_client_task_history(db, client_id, limit=50):
    """Get client task history (stub - not implemented)."""
    return {"tasks": [], "total": 0}


async def get_oauth_status(db, provider):
    """Get OAuth status (stub - not implemented)."""
    return {"connected": False, "provider": provider}


async def initiate_oauth(db, provider):
    """Initiate OAuth (stub - not implemented)."""

    raise HTTPException(status_code=501, detail="OAuth not yet implemented")


async def oauth_callback(db, provider, code):
    """OAuth callback (stub - not implemented)."""

    raise HTTPException(status_code=501, detail="OAuth not yet implemented")


async def refresh_oauth_token(db, provider, refresh_token):
    """Refresh OAuth token (stub - not implemented)."""

    raise HTTPException(status_code=501, detail="OAuth not yet implemented")


async def revoke_oauth_token(db, provider):
    """Revoke OAuth token (stub - not implemented)."""

    raise HTTPException(status_code=501, detail="OAuth not yet implemented")


# Stub task processing
async def process_task_async(db, task_id):
    """Process task async (stub - not implemented)."""


# Export all symbols for backward compatibility
__all__ = [
    "add_seed_money",
    "create_checkout_session",
    "create_threshold_petition",
    "decide_threshold_petition",
    "evaluate_auto_threshold",
    "generate_proposal",
    "get_arena_history",
    "get_arena_stats",
    "get_auto_threshold_status",
    "get_client_discount_info",
    "get_client_task_history",
    "get_confidence_recommendation",
    "get_confidence_summary",
    "get_cost_history",
    "get_current_threshold",
    "get_financial_status",
    "get_learning_insights",
    "get_oauth_status",
    "get_prediction_accuracy",
    "get_profitable_strategies",
    "get_roi_by_marketplace",
    "get_roi_by_strategy",
    "get_secure_delivery",
    "get_task",
    "get_task_by_session",
    "initiate_oauth",
    "list_threshold_petitions",
    "oauth_callback",
    "process_task_async",
    "record_job_completion",
    "refresh_oauth_token",
    "revoke_oauth_token",
    "rollback_auto_threshold",
    "run_arena_competition",
    "run_autonomous_loop",
    "set_budget",
]
