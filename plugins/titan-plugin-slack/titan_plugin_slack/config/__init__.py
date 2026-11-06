"""Slack plugin config helpers."""

from titan_cli.core.security import OAuthApp, OAuthProvider

OAUTH_REDIRECT_PORT = 8765

OAUTH_SCOPES = (
    "users:read",
    "channels:read",
    "channels:history",
    "groups:read",
    "groups:history",
    "im:history",
    "mpim:history",
    "chat:write",
    "im:write",
    "mpim:write",
    "channels:write",
    "groups:write",
    "files:write",
)

SLACK_OAUTH = OAuthProvider(
    name="Slack",
    authorize_url="https://slack.com/oauth/v2_user/authorize",
    token_url="https://slack.com/api/oauth.v2.user.access",
    scopes=OAUTH_SCOPES,
    scope_separator=",",
    callback_path="/slack/callback",
    success_flag="ok",
    token_container="authed_user",
    metadata_fields={
        "team_id": "team.id",
        "team_name": "team.name",
        "user_id": "authed_user.id",
    },
    api_hosts=("slack.com",),
)


def slack_oauth_app(client_id: str) -> OAuthApp:
    """The project's Slack App; Slack matches the redirect URL exactly."""
    return OAuthApp(client_id=client_id, redirect_port=OAUTH_REDIRECT_PORT)


def build_project_slack_oauth_key(project_name: str | None) -> str:
    """Return the secret key holding the current project's Slack OAuth grant."""
    if not project_name:
        raise ValueError("Slack project token key requires a configured project name.")
    return f"{project_name}_slack_oauth"


__all__ = [
    "OAUTH_REDIRECT_PORT",
    "OAUTH_SCOPES",
    "SLACK_OAUTH",
    "build_project_slack_oauth_key",
    "slack_oauth_app",
]
