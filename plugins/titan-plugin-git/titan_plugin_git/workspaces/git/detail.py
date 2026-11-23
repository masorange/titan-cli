"""The right column: the header of what is selected and its files as collapsible cards, drawn from `w.state` only."""
from pathlib import PurePosixPath
from typing import Optional

from titan_cli.ui.components import Option, choice_card, error_card
from titan_cli.ui.elements import Box, Button, Diff, Text
from titan_plugin_git.drawing import ref_color
from titan_plugin_git.readers import Repo

from .actions import Actions
from .reading import WIP, Files, card_key

STATES = {"A": "added", "M": "modified", "D": "deleted", "?": "new"}
STATE_COLORS = {"A": "success", "M": "warning", "D": "error", "?": "success"}


DIR_SHOWN = 30  # cells of a file's folder the card title keeps, so the state and the counts stay in view


def short_dir(path: str, limit: int = DIR_SHOWN) -> str:
    """The folder of `path`, cut from the start (`…/docs/business`) when it is longer than `limit`; "" at the root."""
    folder = str(PurePosixPath(path).parent)
    if folder == ".":
        return ""
    return folder if len(folder) <= limit else "…" + folder[-(limit - 1):]


def counts(additions: int, deletions: int) -> Text:
    return Text(Text(f"+{additions}", color="success"), " ", Text(f"-{deletions}", color="error"))


def stash_for(w, selection: str):
    """The stash a selection names, or None when it is a commit or the uncommitted changes."""
    branches = w.state.get("branches")
    return next((s for s in (branches.stashes if branches else []) if s.hash == selection), None)


def stash_menu(w, stash, actions: Actions, width: int) -> Box:
    """What can be done with the stash on screen: apply it, pop it or drop it for good (behind a second press)."""
    confirming = w.state.get("stash_drop_confirm") == stash.hash
    card = dict(width=width, state=w.state, key="stash_menu", close=False)
    return Box(
        not confirming and choice_card([
            Option("⤴ Apply, keep it", lambda: actions.stash("apply", stash)),
            Option("⤒ Pop: apply and remove", lambda: actions.stash("pop", stash)),
            Option("✗ Drop…", lambda: w.state.set("stash_drop_confirm", stash.hash)),
        ], title="Stash", **card),
        confirming and choice_card([
            Option("✓ Confirm drop", lambda: actions.stash("drop", stash), "error"),
            Option("Cancel", lambda: w.state.set("stash_drop_confirm", None)),
        ], title="Drops it for good. This cannot be undone.", border="warning", **card),
    )


def commit_header(w, selection: str, files: Optional[Files], actions: Actions, width: int = 60) -> Box:
    totals = files is not None and files.status == "done" and Text(
        f"⎘ {len(files.all)}  ", counts(files.additions, files.deletions)
    )
    if selection == WIP:
        return Box(Text("Uncommitted changes", bold=True, color="warning"), totals)
    stash = stash_for(w, selection)
    if stash is not None:
        return Box(
            Text(f"Stash {stash.ref}", bold=True, color="warning"),
            Text(stash.message, bold=True, wrap=True),
            Text(" · ".join(p for p in (stash.branch, stash.formatted_date) if p), dim=True),
            totals,
            stash_menu(w, stash, actions, width),
        )
    repo: Optional[Repo] = w.state.get("repo")
    commit = next((c for c in (repo.commits if repo else []) if c.hash == selection), None)
    if commit is None:
        return Box(Text(f"Commit {selection[:7]}", bold=True), totals)
    return Box(
        Text(commit.message_subject, bold=True, wrap=True),
        Text(f"{commit.author_short} · {commit.date} · {commit.short_hash}", dim=True),
        commit.refs and Text(*[Text(f"{ref} ", color=ref_color(commit, ref)) for ref in commit.refs], wrap=True),
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


def file_actions(w, key: str, selection: str, side: str, f, actions: Actions, width: int) -> Box:
    """What can be done with one file: copy its path and, on the uncommitted changes, stage, unstage or discard it (behind a second press)."""
    card = dict(width=width, state=w.state, key=f"file_actions:{key}", close=False)
    if w.state.get("discard_confirm") == key:
        return choice_card([
            Option("✓ Confirm discard", lambda: actions.index("discard", [f.path]), "error"),
            Option("Cancel", lambda: w.state.set("discard_confirm", None)),
        ], title=f"Throws away the changes of {f.path}. This cannot be undone.", border="warning", **card)
    on_wip = selection == WIP
    return choice_card([
        Option("⎘ Copy path", lambda: actions.copy(f.path, "path")),
        on_wip and side == "staged" and Option("− Unstage", lambda: actions.index("unstage", [f.path])),
        on_wip and side == "unstaged" and Option("+ Stage", lambda: actions.index("stage", [f.path])),
        on_wip and side == "unstaged" and Option("✗ Discard…", lambda: w.state.set("discard_confirm", key)),
    ], **card)


def file_card(w, selection: str, side: str, f, options, actions: Actions, width: int = 60) -> Box:
    key = card_key(selection, side, f.path)
    is_open = key in (w.state.get("open") or {})
    head = Button(
        Text(
            Text("▾ " if is_open else "▸ ", color="info"),
            Text(PurePosixPath(f.path).name, bold=True),
            short_dir(f.path) and Text(f"  {short_dir(f.path)}", dim=True),
            "  ",
            Text(STATES.get(f.status, f.status), color=STATE_COLORS.get(f.status, "subtle")),
            "  ",
            Text("binary", dim=True) if f.is_binary else counts(f.additions, f.deletions),
        ),
        lambda: actions.toggle(selection, side, f),
    )
    return Box(
        head,
        # The title is the file's name, so a deep path never hides it; unfolded, the whole path is under it.
        is_open and Text(f.path, dim=True, wrap=True),
        is_open and file_actions(w, key, selection, side, f, actions, width - 4),
        is_open and diff_body(w, key, selection, side, f, options, actions),
        border="subtle",
    )


def group(w, selection: str, g, files: Files, options, actions: Actions, width: int = 60) -> Box:
    """Staged or Unstaged: a fold on its title when the screen has more than one group to tell apart."""
    if len(files.groups) <= 1 and selection != WIP:
        return Box(*[file_card(w, selection, g.side, f, options, actions, width) for f in g.files])
    key = f"{selection}|{g.side}"
    is_open = key not in (w.state.get("closed_groups") or {})

    def toggle():
        w.state.update("closed_groups", lambda closed: {**(closed or {}), key: True} if is_open else {k: v for k, v in (closed or {}).items() if k != key}, default={})

    paths = [f.path for f in g.files]
    bulk = {"staged": ("− Unstage all", "unstage"), "unstaged": ("+ Stage all", "stage")}.get(g.side)
    return Box(
        Box(
            Button(Text(Text("▾ " if is_open else "▸ ", color="info"), Text(f"{g.title} ({len(g.files)})", bold=True)), toggle),
            selection == WIP and bulk and Button(bulk[0], lambda: actions.index(bulk[1], paths), dim=True),
            row=True,
        ),
        *([file_card(w, selection, g.side, f, options, actions, width) for f in g.files] if is_open else []),
    )


def detail(w, options, actions: Actions, width: int = 60) -> Box:
    selection = w.state.get("selected") or WIP
    files: Optional[Files] = (w.state.get("files") or {}).get(selection)
    header = commit_header(w, selection, files, actions, width)
    if files is None or files.status == "loading":
        return Box(header, Text("Loading…", dim=True), gap=1)
    if files.status == "error":
        return Box(header, error_card(
            files.error, copy=actions.copy, title="Files",
            actions=[Button("Retry", lambda: actions.retry_files(selection))],
        ), gap=1)
    if not files.groups:
        return Box(header, Text("Working tree clean" if selection == WIP else "No files changed", dim=True), gap=1)
    groups = [group(w, selection, g, files, options, actions, width) for g in files.groups]
    return Box(header, *groups, gap=1)
