"""
Marketplace Adapters Package

Provides extensible adapter pattern for multiple freelance marketplaces.
Implements unified interface for searching, bidding, and tracking across
different platforms (Fiverr, Upwork, PeoplePerHour, etc.).
"""

from .base import (
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
from .fiverr_adapter import FiverrAdapter
from .peoplehour_adapter import PeoplePerHourAdapter
from .registry import MarketplaceRegistry
from .upwork_adapter import UpworkAdapter

# Register adapters in the registry
MarketplaceRegistry.register("fiverr", FiverrAdapter)
MarketplaceRegistry.register("upwork", UpworkAdapter)
MarketplaceRegistry.register("peoplehour", PeoplePerHourAdapter)

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
