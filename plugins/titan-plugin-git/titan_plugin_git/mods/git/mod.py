"""
git: a side pane with the current branch, its upstream and the latest commits.

Pull requests, the merge queue and CI check diagnosis live in the `github`
mod shipped by titan-plugin-github, since they read the github plugin, not
this one. Data comes from the git plugin client on a background timer;
drawing reads only `m.state`, so it never waits on the network. See
docs/concepts/writing-mods.md.
"""
from pathlib import Path

from . import draw
from .sections.repo.repo import read_repo

PANE = "git"
TITLE = "Git"


def register(on, options):
    where = {}

    def refresh_repo(m):
        m.state.set("repo", read_repo(m.client("git"), where["root"], options))

    @on("app.start")
    def start(m, e, next):
        where["root"] = Path(e.project_root)
        m.ui.open(PANE, TITLE)
        m.clock.every(options["repo_refresh_seconds"], lambda: refresh_repo(m))
        if options.get("refresh_key"):
            m.keys.bind(options["refresh_key"], "Refresh status", lambda: m.run(lambda: refresh_repo(m)))
        return next(e)

    # A commit, push or pull is what changes the tree, so refresh right after a
    # workflow ends instead of waiting for the next poll - however it ended: a
    # failed or aborted run may have committed or pushed before stopping. Goes
    # off the workflow's thread, so its end is never delayed.
    @on("workflow.run")
    def after_workflow(m, e, next):
        try:
            return next(e)
        finally:
            if not e.nested and "root" in where:
                m.run(lambda: refresh_repo(m))

    @on("ui.render", match={"component": "Pane", "pane": PANE})
    def render(m, e, next):
        return draw.draw(m, e.width, options)
