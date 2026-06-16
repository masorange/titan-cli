"""Reusable Slack target selection steps for users and channels."""

from titan_cli.ui.tui.widgets import OptionItem

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult
from ..operations import (
    build_channel_target,
    build_user_target,
    normalize_search_query,
)


MIN_QUERY_LENGTH = 2
MAX_TARGET_OPTIONS = 20
SEARCH_ANOTHER_CHANNEL = "__search_another_channel__"


def select_user_target_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Select a Slack user target through query filtering and final confirmation.

    Requires:
        ctx.slack: An initialized SlackClient.

    Inputs (from ctx.data):
        slack_target_query (str, optional): Pre-filled query used to filter Slack users.
        slack_search_limit (int, optional): Maximum number of matches to return. Defaults to 20.
        slack_search_page_size (int, optional): Page size used while scanning Slack users. Defaults to 200.
        slack_search_max_pages (int, optional): Maximum pages to scan while searching. Defaults to 50.

    Outputs (saved to ctx.data):
        slack_target (UISlackTarget): Canonical selected Slack target.
        slack_target_type (str): Selected target type (`user`).
        slack_target_id (str): Slack user ID.
        slack_target_name (str): User-facing target name.
        slack_target_query (str): Query used to resolve the selection.

    Returns:
        Success: If the user target is selected successfully.
        Error: If Slack is unavailable, the query is invalid, the search fails, or no match is selected.
    """
    return _select_target_step(
        ctx,
        step_title="Select Slack User Target",
        empty_list_error="No Slack users are available for selection.",
        query_prompt="Search Slack users by name or real name:",
        short_query_error=f"Enter at least {MIN_QUERY_LENGTH} characters to search Slack users.",
        no_match_error="No Slack users matched that query.",
        options_prompt="Select the Slack user target:",
        search_func=lambda query, limit, page_size, max_pages, exclude_archived: ctx.slack.search_users(
            query,
            max_matches=limit,
            page_size=page_size,
            max_pages=max_pages,
        ),
        option_builder=_build_user_option,
        target_builder=lambda item, team_id, connection_id: build_user_target(
            item,
            team_id=team_id,
            connection_id=connection_id,
        ),
    )


def select_channel_target_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Select a Slack channel target through query filtering and final confirmation.

    Requires:
        ctx.slack: An initialized SlackClient.

    Inputs (from ctx.data):
        slack_target_query (str, optional): Pre-filled query used to filter Slack channels.
        slack_search_limit (int, optional): Maximum number of matches to return. Defaults to 20.
        slack_search_page_size (int, optional): Page size used while scanning Slack channels. Defaults to 200.
        slack_search_max_pages (int, optional): Maximum pages to scan while searching. Defaults to 50.
        slack_exclude_archived (bool, optional): Whether to exclude archived channels while searching. Defaults to True.

    Outputs (saved to ctx.data):
        slack_target (UISlackTarget): Canonical selected Slack target.
        slack_target_type (str): Selected target type (`channel`).
        slack_target_id (str): Slack channel ID.
        slack_target_name (str): User-facing target name.
        slack_target_query (str): Query used to resolve the selection.

    Returns:
        Success: If the channel target is selected successfully.
        Error: If Slack is unavailable, the query is invalid, the search fails, or no match is selected.
    """
    return _select_target_step(
        ctx,
        step_title="Select Slack Channel Target",
        empty_list_error="No Slack channels are available for selection.",
        query_prompt="Search Slack channels by name:",
        short_query_error=f"Enter at least {MIN_QUERY_LENGTH} characters to search Slack channels.",
        no_match_error="No Slack channels matched that query.",
        options_prompt="Select the Slack channel target:",
        search_func=lambda query, limit, page_size, max_pages, exclude_archived: ctx.slack.search_channels(
            query,
            max_matches=limit,
            page_size=page_size,
            max_pages=max_pages,
            exclude_archived=exclude_archived,
        ),
        option_builder=_build_channel_option,
        target_builder=lambda item, team_id, connection_id: build_channel_target(
            item,
            team_id=team_id,
            connection_id=connection_id,
        ),
    )


def select_default_or_search_channel_target_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Select a Slack channel from the configured defaults or search for another one.

    Requires:
        ctx.slack: An initialized SlackClient.

    Inputs (from ctx.data):
        slack_target_query (str, optional): Pre-filled query used if the user chooses to search manually.
        slack_search_limit (int, optional): Maximum number of matches to return during manual search. Defaults to 20.
        slack_search_page_size (int, optional): Page size used while scanning Slack channels. Defaults to 200.
        slack_search_max_pages (int, optional): Maximum pages to scan while searching. Defaults to 50.
        slack_exclude_archived (bool, optional): Whether to exclude archived channels while searching. Defaults to True.

    Outputs (saved to ctx.data):
        slack_target (UISlackTarget): Canonical selected Slack target.
        slack_target_type (str): Selected target type (`channel`).
        slack_target_id (str): Slack channel ID.
        slack_target_name (str): User-facing target name.
        slack_target_query (str): Query used to resolve the selection, when manual search was used.

    Returns:
        Success: If the channel target is selected successfully.
        Error: If Slack is unavailable, the configured channel cannot be resolved, or no match is selected.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    if not ctx.slack:
        return Error("Slack client not available")

    configured_channels = getattr(ctx.slack, "default_channels", []) or []
    if not configured_channels:
        return select_channel_target_step(ctx)

    ctx.textual.begin_step("Select Slack Channel Target")

    options = [
        OptionItem(
            value=channel_name,
            title=f"#{channel_name}",
            description="Configured default channel",
        )
        for channel_name in configured_channels
    ]
    options.append(
        OptionItem(
            value=SEARCH_ANOTHER_CHANNEL,
            title="Search another channel",
            description="Look up a channel by name",
        )
    )

    selected = ctx.textual.ask_option(
        "Select a configured channel or search for another one:",
        options=options,
    )
    if not selected:
        ctx.textual.error_text("No Slack channel was selected.")
        ctx.textual.end_step("error")
        return Error("No Slack channel was selected.")

    if selected == SEARCH_ANOTHER_CHANNEL:
        ctx.textual.end_step("skip")
        return select_channel_target_step(ctx)

    configured_channel_name = str(selected)
    resolved = _resolve_channel_by_name(ctx, configured_channel_name)
    match resolved:
        case ClientSuccess(data=channel):
            team_id = ctx.get("slack_team_id")
            connection_id = ctx.get("slack_connection_id")
            target = build_channel_target(
                channel,
                team_id=team_id,
                connection_id=connection_id,
            )
            ctx.textual.success_text(
                f"Selected Slack target: {target.target_name} ({target.target_id})"
            )
            ctx.textual.end_step("success")
            return Success(
                "Selected Slack channel target",
                metadata={
                    "slack_target": target,
                    "slack_target_type": target.target_type,
                    "slack_target_id": target.target_id,
                    "slack_target_name": target.target_name,
                    "slack_target_query": configured_channel_name,
                },
            )
        case ClientError(error_message=err):
            ctx.textual.error_text(err)
            ctx.textual.end_step("error")
            return Error(err)


def _select_target_step(
    ctx: WorkflowContext,
    *,
    step_title: str,
    empty_list_error: str,
    query_prompt: str,
    short_query_error: str,
    no_match_error: str,
    options_prompt: str,
    search_func,
    option_builder,
    target_builder,
) -> WorkflowResult:
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step(step_title)

    if not ctx.slack:
        ctx.textual.error_text("Slack client not available")
        ctx.textual.end_step("error")
        return Error("Slack client not available")

    raw_query = ctx.get("slack_target_query")
    if not raw_query:
        raw_query = ctx.textual.ask_text(query_prompt, default="")

    if not raw_query:
        ctx.textual.error_text(short_query_error)
        ctx.textual.end_step("error")
        return Error(short_query_error)

    normalized_query = normalize_search_query(raw_query)
    if len(normalized_query.lstrip("#")) < MIN_QUERY_LENGTH:
        ctx.textual.error_text(short_query_error)
        ctx.textual.end_step("error")
        return Error(short_query_error)

    search_limit = ctx.get("slack_search_limit", MAX_TARGET_OPTIONS)
    page_size = ctx.get("slack_search_page_size", 200)
    max_pages = ctx.get("slack_search_max_pages", 50)
    exclude_archived = ctx.get("slack_exclude_archived", True)

    with ctx.textual.loading("Searching Slack targets..."):
        result = search_func(
            raw_query,
            search_limit,
            page_size,
            max_pages,
            exclude_archived,
        )

    match result:
        case ClientSuccess(data=matches):
            if not matches:
                ctx.textual.error_text(no_match_error)
                ctx.textual.end_step("error")
                return Error(no_match_error)
        case ClientError(error_message=err):
            ctx.textual.error_text(err)
            ctx.textual.end_step("error")
            return Error(err)

    options = [option_builder(item) for item in matches]
    selected = ctx.textual.ask_option(options_prompt, options=options)
    if not selected:
        ctx.textual.error_text("No Slack target was selected.")
        ctx.textual.end_step("error")
        return Error("No Slack target was selected.")

    team_id = ctx.get("slack_team_id")
    connection_id = ctx.get("slack_connection_id")
    target = target_builder(selected, team_id, connection_id)

    ctx.textual.success_text(f"Selected Slack target: {target.target_name} ({target.target_id})")
    ctx.textual.end_step("success")
    return Success(
        f"Selected Slack {target.target_type} target",
        metadata={
            "slack_target": target,
            "slack_target_type": target.target_type,
            "slack_target_id": target.target_id,
            "slack_target_name": target.target_name,
            "slack_target_query": raw_query,
        },
    )


def _build_user_option(user) -> OptionItem:
    display_name = user.real_name or user.name or user.id
    description = f"@{user.name} ({user.id})"
    if not user.is_active:
        description += " - inactive"
    elif user.is_bot:
        description += " - bot"
    return OptionItem(value=user, title=display_name, description=description)


def _build_channel_option(channel) -> OptionItem:
    description = f"#{channel.name} ({channel.id})"
    if channel.is_private:
        description += " - private"
    return OptionItem(value=channel, title=f"#{channel.name}", description=description)


def _normalize_channel_name(value: str) -> str:
    return normalize_search_query(value).lstrip("#")


def _resolve_channel_by_name(ctx: WorkflowContext, channel_name: str):
    normalized_name = _normalize_channel_name(channel_name)
    if len(normalized_name) < MIN_QUERY_LENGTH:
        return ClientError(
            error_message="Configured Slack channel names must contain at least 2 characters.",
            error_code="CHANNEL_NAME_TOO_SHORT",
        )

    search_limit = ctx.get("slack_search_limit", MAX_TARGET_OPTIONS)
    page_size = ctx.get("slack_search_page_size", 200)
    max_pages = ctx.get("slack_search_max_pages", 50)
    exclude_archived = ctx.get("slack_exclude_archived", True)

    with ctx.textual.loading(f"Resolving configured channel #{normalized_name}..."):
        result = ctx.slack.search_channels(
            normalized_name,
            max_matches=search_limit,
            page_size=page_size,
            max_pages=max_pages,
            exclude_archived=exclude_archived,
        )

    match result:
        case ClientError() as err:
            return err
        case ClientSuccess(data=channels):
            exact_matches = [
                channel
                for channel in channels
                if _normalize_channel_name(channel.name) == normalized_name
            ]
            if not exact_matches:
                return ClientError(
                    error_message=(
                        f"Configured Slack channel '#{channel_name}' was not found in this workspace."
                    ),
                    error_code="CONFIGURED_CHANNEL_NOT_FOUND",
                )
            if len(exact_matches) > 1:
                return ClientError(
                    error_message=(
                        f"Configured Slack channel '#{channel_name}' matched multiple channels."
                    ),
                    error_code="CONFIGURED_CHANNEL_AMBIGUOUS",
                )
            return ClientSuccess(
                data=exact_matches[0],
                message="Configured Slack channel resolved",
            )


__all__ = [
    "select_user_target_step",
    "select_channel_target_step",
    "select_default_or_search_channel_target_step",
]
