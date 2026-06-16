"""Slack plugin config helpers."""


def build_project_slack_token_key(project_name: str | None) -> str:
    """Return the keyring key used for the current project's Slack token."""
    if not project_name:
        raise ValueError("Slack project token key requires a configured project name.")
    return f"{project_name}_slack_user_token"


__all__ = ["build_project_slack_token_key"]
