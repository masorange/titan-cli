"""The pane's element tree, drawn from `m.state` only: it never waits on the network."""
from typing import Optional

from titan_cli.ui.components import error_card
from titan_cli.ui.elements import Box, Button, Text
from titan_plugin_git.readers import Repo
from titan_plugin_git.sections.branches.draw import branches_section


def standing(m) -> Text:
    """The branch you are on, how it stands against its upstream and how much is uncommitted."""
    repo: Optional[Repo] = m.state.get("repo")
    if repo is None:
        return Text("Loading…", dim=True)
    return Text(
        Text(f"⎇ {repo.branch}", bold=True, color="info"),
        repo.has_upstream and Text(f" ↑{repo.ahead}", color="success" if repo.ahead else "subtle"),
        repo.has_upstream and Text(f" ↓{repo.behind}", color="warning" if repo.behind else "subtle"),
        not repo.has_upstream and Text(" no upstream", dim=True),
        repo.added and Text(f" +{repo.added}", color="success"),
        repo.removed and Text(f" −{repo.removed}", color="error"),
    )


def draw(m, width: int, options=None):
    """The branch you are on and what can be done with it; the history, the switcher and the worktrees are the workspace's."""
    repo: Optional[Repo] = m.state.get("repo")
    return Box(
        standing(m),
        repo and repo.error and error_card(repo.error, copy=m.ui.copy, title="Git"),
        branches_section(m, options or {}, width, switcher=False),
        Button("⎇ Open Git workspace", lambda: m.ui.open_workspace("git"), dim=True),
    )
