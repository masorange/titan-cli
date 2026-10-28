import requests

from titan_cli.core.result import ClientError, ClientResult, ClientSuccess


class ExampleClient:
    """Reusable project-level client facade for a stable integration.

    The credential arrives only at construction, inside the broker call:

        client = ctx.secret_broker.create_client(
            "example_api_token",
            lambda token: ExampleClient(base_url, token),
        )

    Never accept a token from ctx.data, config, argv or os.environ.
    """

    def __init__(self, base_url: str, token: str) -> None:
        self._base_url = base_url
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {token}"

    def fetch_items(self) -> ClientResult[list[str]]:
        try:
            response = self._session.get(f"{self._base_url}/items", timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            return ClientError(error_message=str(exc), error_code="REQUEST_FAILED")
        return ClientSuccess(data=[item["name"] for item in response.json()])
