"""How a failed GitHub call becomes a `ClientError`."""
from titan_cli.core.result import ClientError

from ...exceptions import GitHubAPIError


def api_error(e: GitHubAPIError) -> ClientError:
    """
    The `ClientError` for a failed call. While the rate limit lasts every poll is refused
    the same way: that is a warning with its own code, not one more error per timer tick,
    since the pause itself was logged once when GitHub answered (`gh_command_failed`).
    """
    if getattr(e, "rate_limited", False):
        return ClientError(error_message=str(e), error_code="RATE_LIMITED", log_level="warning")
    return ClientError(error_message=str(e), error_code="API_ERROR")
