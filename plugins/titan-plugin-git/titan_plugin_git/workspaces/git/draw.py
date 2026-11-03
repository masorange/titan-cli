"""The workspace's element tree, drawn from `w.state` only: it never waits on the network."""
from dataclasses import dataclass
from typing import Callable, Optional

from titan_cli.ui.components import error_card
from titan_cli.ui.elements import Box, Button, Diff, Text, responsive_columns
from titan_plugin_git.drawing import commit_title, lane_glyphs
from titan_plugin_git.operations import graph_lanes
from titan_plugin_git.readers import Repo
from titan_plugin_git.sections.branches.draw import branches_section
from titan_plugin_git.sections.worktrees.draw import worktrees_section

from .reading import WIP, Files, card_key

COLLAPSE_BELOW = 120
DEFAULT_RATIO = (2, 3)
STATES = {"A": "added", "M": "modified", "D": "deleted", "?": "new"}
STATE_COLORS = {"A": "success", "M": "warning", "D": "error", "?": "success"}


@dataclass(frozen=True)
class Actions:
    """What a press does; the workspace wires them to state and reads."""

    select: Callable[[str], None]
    toggle: Callable[[str, str, object], None]
    more_commits: Callable[[], None]
    more_lines: Callable[[str, int], None]
    retry_history: Callable[[], None]
    retry_files: Callable[[str], None]
    retry_diff: Callable[[str, str, object], None]
    copy: Callable[[str, str], None]
    resize: Callable[[tuple], None]


def marker(selected: bool) -> Text:
    return Text("▶ " if selected else "  ", color="info", bold=True)


def counts(additions: int, deletions: int) -> Text:
    return Text(Text(f"+{additions}", color="success"), " ", Text(f"-{deletions}", color="error"))


def top_bar(w) -> Text:
    repo: Optional[Repo] = w.state.get("repo")
    if repo is None or repo.error:
        return Text("⎇ Git", bold=True, color="info")
    return Text(
        Text(f"⎇ {repo.branch}", bold=True, color="info"),
        repo.has_upstream and Text(f"  ↑{repo.ahead}", color="success" if repo.ahead else "subtle"),
        repo.has_upstream and Text(f" ↓{repo.behind}", color="warning" if repo.behind else "subtle"),
        not repo.has_upstream and Text("  no upstream", dim=True),
    )


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
        if repo.rows and lanes <= options["graph_max_lanes"]:
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
        # A full page means there may be more behind it; a short one is the whole history.
        elif len(repo.commits) >= (w.state.get("commit_limit") or options["commits_shown"]):
            rows.append(Button("＋ Show more", actions.more_commits, dim=True))
    is_open = w.state.get("history_open", True)
    return Box(
        Button(
            Text(Text("▾ " if is_open else "▸ ", color="info"), Text("History", bold=True, color="info")),
            lambda: w.state.set("history_open", not is_open),
        ),
        is_open and Box(*rows),
        border="info",
    )


def left(w, width: int, options, actions: Actions) -> Box:
    """The repository's branch and worktrees above its history: what the git mod's pane holds, in full."""
    return Box(
        branches_section(w, options, width),
        worktrees_section(w, options, width),
        history(w, options, actions),
        gap=1,
    )


def commit_header(w, selection: str, files: Optional[Files], actions: Actions) -> Box:
    totals = files is not None and files.status == "done" and Text(
        f"⎘ {len(files.all)}  ", counts(files.additions, files.deletions)
    )
    if selection == WIP:
        return Box(Text("Uncommitted changes", bold=True, color="warning"), totals)
    repo: Optional[Repo] = w.state.get("repo")
    commit = next((c for c in (repo.commits if repo else []) if c.hash == selection), None)
    if commit is None:
        return Box(Text(f"Commit {selection[:7]}", bold=True), totals)
    return Box(
        Text(commit.message_subject, bold=True, wrap=True),
        Text(f"{commit.author_short} · {commit.date} · {commit.short_hash}", dim=True),
        commit.refs and Text(Text(" ".join(commit.refs), color="accent", wrap=True)),
        totals,
        Button("⎘ Copy hash", lambda: actions.copy(commit.hash, "commit hash"), dim=True),
    )


def diff_body(w, key: str, selection: str, side: str, f, options, actions: Actions) -> Box:
    state = (w.state.get("diffs") or {}).get(key)
    if state is None or state.status == "loading":
        return Text("Loading…", dim=True)
    if state.status == "error":
        return error_card(
            state.error, copy=actions.copy, title=f"Diff of {f.path}",
            actions=[Button("Retry", lambda: actions.retry_diff(selection, side, f))],
        )
    limit = (w.state.get("limits") or {}).get(key) or options["diff_lines"]
    total = sum(len(h.lines) for h in state.diff.hunks)
    return Box(
        Diff(state.diff, max_lines=limit),
        total > limit and Button(f"＋ Show more lines ({total - limit} left)", lambda: actions.more_lines(key, limit), dim=True),
    )


def file_card(w, selection: str, side: str, f, options, actions: Actions) -> Box:
    key = card_key(selection, side, f.path)
    is_open = key in (w.state.get("open") or {})
    head = Button(
        Text(
            Text("▾ " if is_open else "▸ ", color="info"),
            Text(f.path, bold=True),
            "  ",
            Text(STATES.get(f.status, f.status), color=STATE_COLORS.get(f.status, "subtle")),
            "  ",
            Text("binary", dim=True) if f.is_binary else counts(f.additions, f.deletions),
        ),
        lambda: actions.toggle(selection, side, f),
    )
    return Box(
        head,
        is_open and Button("⎘ Copy path", lambda: actions.copy(f.path, "path"), dim=True),
        is_open and diff_body(w, key, selection, side, f, options, actions),
        border="subtle",
    )


def group(w, selection: str, g, files: Files, options, actions: Actions) -> Box:
    """Staged or Unstaged: a fold on its title when the screen has more than one group to tell apart."""
    if len(files.groups) <= 1 and selection != WIP:
        return Box(*[file_card(w, selection, g.side, f, options, actions) for f in g.files])
    key = f"{selection}|{g.side}"
    is_open = key not in (w.state.get("closed_groups") or {})

    def toggle():
        w.state.update("closed_groups", lambda closed: {**(closed or {}), key: True} if is_open else {k: v for k, v in (closed or {}).items() if k != key}, default={})

    return Box(
        Button(Text(Text("▾ " if is_open else "▸ ", color="info"), Text(f"{g.title} ({len(g.files)})", bold=True)), toggle),
        *([file_card(w, selection, g.side, f, options, actions) for f in g.files] if is_open else []),
    )


def detail(w, options, actions: Actions) -> Box:
    selection = w.state.get("selected") or WIP
    files: Optional[Files] = (w.state.get("files") or {}).get(selection)
    header = commit_header(w, selection, files, actions)
    if files is None or files.status == "loading":
        return Box(header, Text("Loading…", dim=True), gap=1)
    if files.status == "error":
        return Box(header, error_card(
            files.error, copy=actions.copy, title="Files",
            actions=[Button("Retry", lambda: actions.retry_files(selection))],
        ), gap=1)
    if not files.groups:
        return Box(header, Text("Working tree clean" if selection == WIP else "No files changed", dim=True), gap=1)
    groups = [group(w, selection, g, files, options, actions) for g in files.groups]
    return Box(header, *groups, gap=1)


def draw(w, width: int, options, actions: Actions) -> Box:
    return Box(
        top_bar(w),
        responsive_columns(
            width,
            [lambda cw: left(w, cw, options, actions), lambda _: detail(w, options, actions)],
            ratio=tuple(w.state.get("columns") or DEFAULT_RATIO),
            collapse_below=COLLAPSE_BELOW,
            on_resize=actions.resize,
        ),
        gap=1,
    )
