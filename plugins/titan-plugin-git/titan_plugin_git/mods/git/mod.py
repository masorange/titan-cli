"""
git: a side pane with the current branch and its upstream, the latest commits,
a switcher for the branches you worked on most recently, and the repository's
worktrees.

Pull requests, the merge queue and CI check diagnosis live in the `github`
mod shipped by titan-plugin-github, since they read the github plugin, not
this one. Data comes from the git plugin client on a background timer;
drawing reads only `m.state`, so it never waits on the network. See
docs/concepts/writing-mods.md.
"""
from pathlib import Path

from . import draw
from .sections.branches.branches import read_branches
from .sections.repo.repo import read_repo
from .sections.worktrees.worktrees import read_worktrees

PANE = "git"
TITLE = "Git"


def register(on, options):
    where = {}
    shown = options.setdefault("sections", {})
    for name in ("repo", "branches", "worktrees"):
        shown.setdefault(name, True)

    def refresh_repo(m):
        # "Show more" raises the count in state; the option is where it starts from.
        shown_commits = m.state.get("commit_limit") or options["recent_commits"]
        m.state.set("repo", read_repo(m.client("git"), where["root"], {**options, "recent_commits": shown_commits}))

    def refresh_branches(m):
        m.state.set("branches", read_branches(m.client("git"), options))

    def refresh_worktrees(m):
        m.state.set("worktrees", read_worktrees(m.client("git"), where["root"], options))

    def refresh_all(m):
        if shown["repo"]:
            refresh_repo(m)
        if shown["branches"]:
            refresh_branches(m)
        if shown["worktrees"]:
            refresh_worktrees(m)

    @on("app.start")
    def start(m, e, next):
        where["root"] = Path(e.project_root)
        m.ui.open(PANE, TITLE)
        # A switch or a worktree removal changes more than one card, and the press
        # that does it only has `m` to work with: this is how it reaches the refresh.
        m.state.set("refresh", lambda: refresh_all(m))
        m.state.set("refresh_repo", lambda: refresh_repo(m))
        m.clock.every(options["repo_refresh_seconds"], lambda: shown["repo"] and refresh_repo(m))
        m.clock.every(options["branches_refresh_seconds"], lambda: shown["branches"] and refresh_branches(m))
        m.clock.every(options["worktrees_refresh_seconds"], lambda: shown["worktrees"] and refresh_worktrees(m))
        if options.get("refresh_key"):
            m.keys.bind(options["refresh_key"], "Refresh status", lambda: m.run(lambda: refresh_all(m)))
        return next(e)

    @on("section.change")
    def section_changed(m, e, next):
        # A section just turned on has nothing to show until its first read.
        if e.enabled and "root" in where:
            refresh = {"repo": refresh_repo, "branches": refresh_branches, "worktrees": refresh_worktrees}[e.section]
            m.run(lambda: refresh(m))
        return next(e)

    # A commit, push, pull or checkout is what changes the tree, so refresh right after a
    # workflow ends instead of waiting for the next poll - however it ended: a
    # failed or aborted run may have committed or pushed before stopping. Goes
    # off the workflow's thread, so its end is never delayed.
    @on("workflow.run")
    def after_workflow(m, e, next):
        try:
            return next(e)
        finally:
            if not e.nested and "root" in where:
                m.run(lambda: refresh_all(m))

    @on("ui.render", match={"component": "Pane", "pane": PANE})
    def render(m, e, next):
        return draw.draw(m, e.width, options)
