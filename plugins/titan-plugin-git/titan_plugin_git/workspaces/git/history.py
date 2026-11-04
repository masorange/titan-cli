"""The History tab: the uncommitted changes on top and the commit graph under them, like gitk."""
from typing import Optional

from titan_cli.ui.components import error_card
from titan_cli.ui.elements import Box, Button, Text
from titan_plugin_git.drawing import commit_title, lane_glyphs
from titan_plugin_git.operations import graph_lanes
from titan_plugin_git.readers import Repo

from .actions import Actions
from .reading import WIP, Files


def marker(selected: bool) -> Text:
    return Text("▶ " if selected else "  ", color="info", bold=True)


def history(w, options, actions: Actions) -> Box:
    selected = w.state.get("selected") or WIP
    repo: Optional[Repo] = w.state.get("repo")
    wip: Optional[Files] = (w.state.get("files") or {}).get(WIP)
    changed = len(wip.all) if wip is not None and wip.status == "done" else None

    rows = [Button(
        Text(marker(selected == WIP), Text("● ", color="warning"), Text("Uncommitted changes", bold=True),
             changed is not None and Text(f"  {changed}", dim=True)),
        lambda: actions.select(WIP),
    )]
    if repo is None:
        rows.append(Text("Loading…", dim=True))
    elif repo.error:
        rows.append(error_card(
            repo.error, copy=actions.copy, title="History", actions=[Button("Retry", actions.retry_history)],
        ))
    else:
        lanes = graph_lanes(repo.rows)
        if repo.rows:
            for row in repo.rows:
                if row.is_link:
                    rows.append(Text("  ", lane_glyphs(row, lanes)))
                else:
                    c = row.commit
                    rows.append(Button(
                        Text(marker(selected == c.hash), lane_glyphs(row, lanes), " ", commit_title(c)),
                        lambda sha=c.hash: actions.select(sha),
                    ))
        else:
            rows += [
                Button(Text(marker(selected == c.hash), commit_title(c)), lambda sha=c.hash: actions.select(sha))
                for c in repo.commits
            ]
        if not repo.commits:
            rows.append(Text("No commits", dim=True))
        limit = w.state.get("commit_limit") or options["commits_shown"]
        # A full page means there may be more behind it; a short one is the whole history.
        more = repo.commits and len(repo.commits) >= limit
        less = limit > options["commits_shown"]
        rows.append(Box(
            more and Button("＋ Show more", actions.more_commits, dim=True),
            less and Button("－ Show less", actions.fewer_commits, dim=True),
            row=True, pack=True,
        ))
    return Box(Text("HISTORY", bold=True, color="info"), *rows, border="subtle")
