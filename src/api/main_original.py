"""Backward compatibility module for main.py.

This module re-exports functions from their correct module locations.
Some functions have been moved to specialized modules while maintaining
backward compatibility through this file.
"""

# Import from original locations or created shims

# Wallet functions - from virtual_wallet (as module-level functions)
from src.agent_execution.virtual_wallet import get_virtual_wallet


def add_seed_money(amount_cents: int) -> bool:
    """Add seed money to the virtual wallet."""
    wallet = get_virtual_wallet()
    return wallet.add_seed_money(amount_cents)


def set_budget_cap(amount_cents: int) -> bool:
    """Set budget cap on the virtual wallet."""
    wallet = get_virtual_wallet()
    return wallet.set_budget_cap(amount_cents)


# Payment functions - from payments
from src.api.payments import create_checkout_session

# Task functions - from tasks
from src.api.tasks import (
    get_task,
    get_task_by_session,
    get_secure_delivery,
    run_arena_competition,
    get_arena_history,
    get_arena_stats,
)

# Auth/OAuth functions - from auth
from src.api.auth import (
    initiate_oauth,
    oauth_callback,
    get_oauth_status,
    refresh_oauth_token,
    revoke_oauth_token,
    get_client_task_history,
    get_client_discount_info,
)

# Cost tracking - from cost_tracker (as module-level functions)
from src.agent_execution.cost_tracker import CostTracker, get_cost_tracker


def get_profitable_strategies(min_entries: int = 10) -> list[dict]:
    """Get list of profitable strategies."""
    tracker = get_cost_tracker()
    return tracker.get_profitable_strategies(min_entries)


def get_cost_history(limit: int = 100, task_id: str | None = None, bid_id: str | None = None):
    """Get cost history."""
    return CostTracker.get_cost_history(limit, task_id, bid_id)

# Learning - from learning
from src.api.learning import (
    ExperienceLogger,
    _log_arena_learning,
    experience_logger,
)

# Threshold-related functions - stubs for backward compatibility
# These functions are not yet implemented in the codebase
async def create_threshold_petition(*args, **kwargs):
    """Stub for threshold petition creation."""
    raise NotImplementedError("Threshold petitions not yet implemented")


async def decide_threshold_petition(*args, **kwargs):
    """Stub for threshold petition decision."""
    raise NotImplementedError("Threshold petitions not yet implemented")


async def evaluate_auto_threshold(*args, **kwargs):
    """Stub for auto threshold evaluation."""
    raise NotImplementedError("Auto-threshold not yet implemented")


async def generate_proposal(*args, **kwargs):
    """Stub for proposal generation."""
    raise NotImplementedError("Proposals not yet implemented")


async def get_auto_threshold_status(*args, **kwargs):
    """Stub for auto threshold status."""
    raise NotImplementedError("Auto-threshold not yet implemented")


async def get_current_threshold(*args, **kwargs):
    """Stub for current threshold."""
    raise NotImplementedError("Threshold not yet implemented")


async def get_confidence_recommendation(*args, **kwargs):
    """Stub for confidence recommendation."""
    raise NotImplementedError("Confidence recommendations not yet implemented")


async def get_confidence_summary(*args, **kwargs):
    """Stub for confidence summary."""
    raise NotImplementedError("Confidence summaries not yet implemented")


async def get_prediction_accuracy(*args, **kwargs):
    """Stub for prediction accuracy."""
    raise NotImplementedError("Prediction accuracy not yet implemented")


async def get_financial_status(*args, **kwargs):
    """Stub for financial status."""
    raise NotImplementedError("Financial status not yet implemented")


async def get_learning_insights(*args, **kwargs):
    """Stub for learning insights."""
    raise NotImplementedError("Learning insights not yet implemented")


async def get_roi_by_marketplace(*args, **kwargs):
    """Stub for ROI by marketplace."""
    raise NotImplementedError("ROI by marketplace not yet implemented")


async def get_roi_by_strategy(*args, **kwargs):
    """Stub for ROI by strategy."""
    raise NotImplementedError("ROI by strategy not yet implemented")


async def list_threshold_petitions(*args, **kwargs):
    """Stub for listing threshold petitions."""
    raise NotImplementedError("Threshold petitions not yet implemented")


async def process_task_async(*args, **kwargs):
    """Stub for async task processing."""
    raise NotImplementedError("Async task processing not yet implemented")


async def record_job_completion(*args, **kwargs):
    """Stub for recording job completion."""
    raise NotImplementedError("Job completion recording not yet implemented")


async def rollback_auto_threshold(*args, **kwargs):
    """Stub for rolling back auto threshold."""
    raise NotImplementedError("Auto-threshold not yet implemented")


async def run_autonomous_loop(*args, **kwargs):
    """Stub for autonomous loop."""
    raise NotImplementedError("Autonomous loop not yet implemented")


async def set_budget(*args, **kwargs):
    """Stub for setting budget."""
    raise NotImplementedError("Budget setting not yet implemented")
