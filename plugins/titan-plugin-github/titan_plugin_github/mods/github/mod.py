"""
github: a side pane with the repo's GitHub at a glance - what waits for your review, your PRs,
the merge queue and failing CI runs - and a button that opens the github workspace, where the
pull requests, the queue and the runs are worked on.

Data comes from the plugin's feed (`readers.feed`), shared with the workspace: GitHub is read once
per period however many views show the same thing. The rail badge and the toasts show with the
panel folded, so the PRs and the queue are always followed; the runs only while the pane shows.
Drawing reads only `m.state`, so it never waits on the network.
See docs/concepts/writing-mods.md.
"""
from pathlib import Path

from titan_plugin_github.readers.feed import feed_for
from titan_plugin_github.readers.prs import new_review_requests
from titan_plugin_github.readers.queue import left_queue

from . import draw

PANE = "github"
TITLE = "GitHub"
SUMMARY_RUNS = 10
# How often a timer asks the feed. Asking is free while the feed's answer is younger than the
# option's period; this only bounds how late a read is once it is due, or once the pane opens.
TICK_SECONDS = 5


def register(on, options):
    where = {}

    def feed(m):
        return feed_for(m.client("github"))

    def refresh_prs(m):
        before = m.state.get("prs")
        after = feed(m).prs(options["prs_refresh_seconds"])
        if after is before:
            return
        m.state.set("prs", after)
        waiting = len(after.to_review) if after.error is None else 0
        m.ui.badge(PANE, str(waiting) if waiting else None, severity="warning")
        arrived = new_review_requests(before, after)
        if arrived:
            m.ui.toast("Review requested: " + ", ".join(f"#{n}" for n in arrived))

    def refresh_queue(m):
        before = m.state.get("queue")
        after = feed(m).queue(options["queue_shown"], options["queue_refresh_seconds"])
        if after is before:
            return
        m.state.set("queue", after)
        left = left_queue(before, after)
        if left:
            m.ui.toast("Left the merge queue: " + ", ".join(f"#{n}" for n in left))

    def refresh_runs(m, even_hidden=False):
        # Only drawn in the pane: nobody sees them with the panel folded or on another pane.
        if not (even_hidden or m.ui.pane_shown(PANE)):
            return
        after = feed(m).runs(None, SUMMARY_RUNS, options["runs_refresh_seconds"])
        if after is not m.state.get("runs"):
            m.state.set("runs", after)

    def refresh_all(m):
        feed(m).refresh()
        refresh_prs(m)
        refresh_queue(m)
        refresh_runs(m, even_hidden=True)

    @on("app.start")
    def start(m, e, next):
        where["root"] = Path(e.project_root)
        m.ui.open(PANE, TITLE)
        m.clock.every(TICK_SECONDS, lambda: refresh_prs(m))
        m.clock.every(TICK_SECONDS, lambda: refresh_queue(m))
        m.clock.every(TICK_SECONDS, lambda: refresh_runs(m))
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
