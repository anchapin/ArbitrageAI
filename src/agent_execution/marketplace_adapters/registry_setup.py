"""Marketplace adapter registry setup.

This module handles the registration of marketplace adapters with the registry.
It is imported for its side effects (registering adapters).
"""

from src.agent_execution.marketplace_adapters.fiverr_adapter import FiverrAdapter
from src.agent_execution.marketplace_adapters.peoplehour_adapter import PeoplePerHourAdapter
from src.agent_execution.marketplace_adapters.registry import MarketplaceRegistry
from src.agent_execution.marketplace_adapters.upwork_adapter import UpworkAdapter

# Register adapters in the registry
MarketplaceRegistry.register("fiverr", FiverrAdapter)
MarketplaceRegistry.register("upwork", UpworkAdapter)
MarketplaceRegistry.register("peoplehour", PeoplePerHourAdapter)
