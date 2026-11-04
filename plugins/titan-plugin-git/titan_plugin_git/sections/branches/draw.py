"""What the branch toolbar and the stashes list draw, from `m.state` only: the new-branch form and the stashes."""

from titan_cli.ui.components import ai_assist_button, error_card, fix_prompt
from titan_cli.ui.elements import Box, Button, Input, Text
from titan_plugin_git.readers import Branches

from . import branches as branch_actions_api
from . import new_branch as new_branch_api

CLEAR_CONFIRM = "stash_clear_confirm"  # the clear-list press is waiting for its second
SEARCH_SHOWN = 12  # matches listed under the search; the rest are counted


def stash_label(s, selected: str):
    """A stash by its message, branch and age, marked when it is the one on screen."""
    line = f"{s.message}" + (f" · {s.branch}" if s.branch else "") + (f" · {s.formatted_date}" if s.formatted_date else "")
    return Text(Text("▶ " if s.hash == selected else "  ", color="info", bold=True), line)


def stash_list_box(m, state: Branches, selected: str = "") -> Box:
    """
    The stashes, one button each, and the line that empties the list behind a second press.
    `selected` is the hash of the stash on screen; pressing one shows it (the workspace's `pick_stash`).
    """
    def clear():
        m.state.set(CLEAR_CONFIRM, False)
        branch_actions_api.start_stash(m, "clear")

    confirming = m.state.get(CLEAR_CONFIRM, False)
    return Box(
        *[
            Button(
                stash_label(s, selected),
                lambda s=s: m.state.get("pick_stash")(s),
            )
            for s in state.stashes
        ],
        Text(" "),
        not confirming and Button("✗ Clear stash list…", lambda: m.state.set(CLEAR_CONFIRM, True), dim=True),
        confirming and Text(f"Drops all {len(state.stashes)} stashes. This cannot be undone.", color="warning", wrap=True),
        confirming and Box(
            Button("✓ Confirm clear", clear, variant="error"),
            Button("Cancel", lambda: m.state.set(CLEAR_CONFIRM, False), variant="default"),
            row=True,
        ),
    )


def new_branch_form(m, branch, options) -> Box:
    """The new branch's name field, the AI's suggestion and the checkout: the content of its dropdown, or of a fold of its own."""
    doing = new_branch_api.status(m)
    name = m.state.get(new_branch_api.NAME) or ""
    error = m.state.get(new_branch_api.ERROR)

    return Box(
        Input(
            value=name,
            placeholder="feat/short-description",
            size="normal",
            on_change=lambda value: new_branch_api.set_name(m, value),
            on_submit=lambda value: new_branch_api.create(m, branch.name, options),
        ),
        doing == "suggesting" and Text("… naming the uncommitted work", dim=True),
        doing == "creating" and Text(f"… creating {name}", dim=True),
        not doing and Button(
            "✦ Suggest with AI",
            lambda: new_branch_api.suggest(m, options),
            dim=True,
        ),
        not doing and name and Button(
            f"✓ Create {name} and switch",
            lambda: new_branch_api.create(m, branch.name, options),
            variant="primary",
        ),
        error and error_card(
            error,
            copy=m.ui.copy,
            # Only the model's own failure is worth a CLI session: a taken name or a
            # missing plugin has nothing to debug.
            actions=[ai_assist_button(
                m,
                fix_prompt(error, "Titan's git mod asked the AI to suggest a branch name for the uncommitted work and the request failed."),
                "✦ Fix with AI",
            )] if error.startswith(new_branch_api.AI_ERROR_PREFIX) else [],
        ),
    )
