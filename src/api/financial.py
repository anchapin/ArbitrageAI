"""
Financial endpoints module.

This module contains pricing calculation, wallet management,
and financial tracking endpoints.
"""


# Domain base rates (USD)
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
    domain: str, complexity: str = "medium", urgency: str = "standard",
) -> int:
    """
    Calculate task price using the Task Price Formula:
    Price = Base Rate x Complexity x Urgency.

    Args:
        domain: The domain of the task (accounting, legal, data_analysis)
        complexity: Task complexity (simple, medium, complex)
        urgency: Task urgency (standard, rush, urgent)

    Returns:
        Calculated price in USD (cents for Stripe)

    Raises:
        ValueError: If domain, complexity, or urgency is invalid
    """
    if domain not in DOMAIN_BASE_RATES:
        valid_domains = ", ".join(DOMAIN_BASE_RATES.keys())
        raise ValueError(f"Invalid domain '{domain}'. Must be one of: {valid_domains}")

    if complexity not in COMPLEXITY_MULTIPLIERS:
        valid_complexities = ", ".join(COMPLEXITY_MULTIPLIERS.keys())
        raise ValueError(
            f"Invalid complexity '{complexity}'. Must be one of: {valid_complexities}",
        )

    if urgency not in URGENCY_MULTIPLIERS:
        valid_urgencies = ", ".join(URGENCY_MULTIPLIERS.keys())
        raise ValueError(
            f"Invalid urgency '{urgency}'. Must be one of: {valid_urgencies}",
        )

    base_rate = DOMAIN_BASE_RATES[domain]
    complexity_multiplier = COMPLEXITY_MULTIPLIERS[complexity]
    urgency_multiplier = URGENCY_MULTIPLIERS[urgency]

    price = base_rate * complexity_multiplier * urgency_multiplier
    return round(price)


# Repeat-client discount tiers
REPEAT_CLIENT_DISCOUNTS = {
    0: 0.0,  # First order - no discount
    1: 0.05,  # 2nd order - 5% discount
    2: 0.10,  # 3rd order - 10% discount
    5: 0.15,  # 6th+ order - 15% discount
}

# Maximum discount cap
MAX_DISCOUNT = 0.15


def get_client_discount(completed_tasks_count: int) -> float:
    """Calculate repeat-client discount based on number of completed tasks."""
    if completed_tasks_count >= 5:
        return 0.15
    if completed_tasks_count >= 2:
        return 0.10
    if completed_tasks_count >= 1:
        return 0.05
    return 0.0


def get_discount_tier(completed_tasks_count: int) -> int:
    """Get the discount tier based on completed tasks count."""
    if completed_tasks_count >= 5:
        return 5
    if completed_tasks_count >= 2:
        return 2
    if completed_tasks_count >= 1:
        return 1
    return 0


__all__ = [
    "COMPLEXITY_MULTIPLIERS",
    "DOMAIN_BASE_RATES",
    "DOMAIN_PRICES",
    "MAX_DISCOUNT",
    "REPEAT_CLIENT_DISCOUNTS",
    "URGENCY_MULTIPLIERS",
    "calculate_task_price",
    "get_client_discount",
    "get_discount_tier",
]
