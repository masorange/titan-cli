class ExampleClient:
    """Reusable project-level client facade for a stable integration."""

    def __init__(self, token: str) -> None:
        self.token = token

    def fetch_items(self) -> list[dict]:
        raise NotImplementedError
