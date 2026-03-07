"""Marketplace Adapters Package.

Provides extensible adapter pattern for multiple freelance marketplaces.
Implements unified interface for searching, bidding, and tracking across
different platforms (Fiverr, Upwork, PeoplePerHour, etc.).
"""

from src.agent_execution.marketplace_adapters.base import (
    AuthenticationError,
    BidProposal,
    BidStatus,
    MarketplaceAdapter,
    MarketplaceError,
    NotFoundError,
    PricingModel,
    RateLimitError,
    SearchQuery,
    SearchResult,
)
from src.agent_execution.marketplace_adapters.fiverr_adapter import FiverrAdapter
from src.agent_execution.marketplace_adapters.peoplehour_adapter import PeoplePerHourAdapter
from src.agent_execution.marketplace_adapters.registry import MarketplaceRegistry
from src.agent_execution.marketplace_adapters.upwork_adapter import UpworkAdapter

# Import for side effects (registering adapters)
import src.agent_execution.marketplace_adapters.registry_setup  # noqa: F401

__all__ = [
    "AuthenticationError",
    "BidProposal",
    "BidStatus",
    "FiverrAdapter",
    "MarketplaceAdapter",
    "MarketplaceError",
    "MarketplaceRegistry",
    "NotFoundError",
    "PeoplePerHourAdapter",
    "PricingModel",
    "RateLimitError",
    "SearchQuery",
    "SearchResult",
    "UpworkAdapter",
]
