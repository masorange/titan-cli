def transform_items(items: list[str]) -> list[str]:
    """Example operation: pure, reusable business logic."""

    return [item.strip() for item in items if item and item.strip()]
