"""
github: a side pane with the repo's GitHub at a glance - what waits for your review, your PRs,
the merge queue and failing CI runs - and a button that opens the github workspace, where the
pull requests, the queue and the runs are worked on.

Data comes from the github plugin client on background timers (the readers are shared with the
workspace); drawing reads only `m.state`, so it never waits on the network.
See docs/concepts/writing-mods.md.
"""
from pathlib import Path

from titan_plugin_github.readers.prs import new_review_requests, read_prs
from titan_plugin_github.readers.queue import left_queue, read_queue
from titan_plugin_github.readers.runs import read_runs

from . import draw

PANE = "github"
TITLE = "GitHub"
SUMMARY_RUNS = 10


def register(on, options):
    where = {}

    def refresh_prs(m):
        before = m.state.get("prs")
        after = read_prs(m.client("github"))
        m.state.set("prs", after)
        waiting = len(after.to_review) if after.error is None else 0
        m.ui.badge(PANE, str(waiting) if waiting else None, severity="warning")
        arrived = new_review_requests(before, after)
        if arrived:
            m.ui.toast("Review requested: " + ", ".join(f"#{n}" for n in arrived))

    def refresh_queue(m):
        before = m.state.get("queue")
        after = read_queue(m.client("github"), options["queue_shown"])
        m.state.set("queue", after)
        left = left_queue(before, after)
        if left:
            m.ui.toast("Left the merge queue: " + ", ".join(f"#{n}" for n in left))

    def refresh_runs(m):
        m.state.set("runs", read_runs(m.client("github"), None, SUMMARY_RUNS))

    def refresh_all(m):
        refresh_prs(m)
        refresh_queue(m)
        refresh_runs(m)

    @on("app.start")
    def start(m, e, next):
        where["root"] = Path(e.project_root)
        m.ui.open(PANE, TITLE)
        m.clock.every(options["prs_refresh_seconds"], lambda: refresh_prs(m))
        m.clock.every(options["queue_refresh_seconds"], lambda: refresh_queue(m))
        m.clock.every(options["runs_refresh_seconds"], lambda: refresh_runs(m))
        if options.get("refresh_key"):
            m.keys.bind(options["refresh_key"], "Refresh status", lambda: m.run(lambda: refresh_all(m)))
        return next(e)

    # Workflows are what change GitHub, so refresh right after one ends instead of waiting for
    # the next poll - however it ended. Goes off the workflow's thread, so its end is never delayed.
    @on("workflow.run")
    def after_workflow(m, e, next):
        try:
            return next(e)
        finally:
            if not e.nested and "root" in where:
                m.run(lambda: refresh_all(m))

    @on("ui.render", match={"component": "Pane", "pane": PANE})
    def render(m, e, next):
        return draw.draw(m)
