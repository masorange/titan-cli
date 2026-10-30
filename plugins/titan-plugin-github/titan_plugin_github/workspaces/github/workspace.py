"""
github workspace: a full screen for the repo's GitHub, opened from its dock tile.

The pull requests (search, review actions, merge, conflicts, check diagnosis), the merge queue
and the workflow runs, drawn from `w.state` only so it never waits on the network. Data comes from
the github plugin client on background timers; the readers and snapshots are shared with the
`github` mod (`titan_plugin_github.readers`), which keeps the summary in the side pane.
"""
from titan_cli.ui.components import refresh_ai_chip
from titan_plugin_github.readers import prs as prs_reader, queue as queue_reader, runs as runs_reader

from . import draw
from .sections.prs import threads

TITLE = "GitHub"


def register(w, on, options):
    started = []
    shown = options.setdefault("sections", {})
    for name in ("prs", "queue", "runs"):
        shown.setdefault(name, True)

    def refresh_prs(m):
        after = prs_reader.read_prs(m.client("github"))
        m.state.set("prs", after)
        # Asked here, off the UI thread: finding out may take a round-trip.
        m.state.set("slack_on", m.client("slack") is not None)
        if after.error is None:
            rows = m.state.get("rows_open") or {}
            threads.reread_open(m, after.mine, lambda number: bool(rows.get(str(number))))

    def refresh_others(m):
        m.state.set("others", prs_reader.read_others(m.client("github")))

    def refresh_queue(m):
        m.state.set("queue", queue_reader.read_queue(m.client("github"), options["queue_shown"]))

    def refresh_runs(m):
        m.state.set("runs", runs_reader.read_runs(m.client("github"), None, runs_reader.limit_of(m, "runs")))

    def refresh_queue_runs(m):
        # The merge queue's own runs, apart from the repo's: GitHub tells them by their event.
        m.state.set("queue_runs", runs_reader.read_runs(
            m.client("github"), "merge_group", runs_reader.limit_of(m, "queue_runs")))

    def refresh_all(m):
        if shown["prs"]:
            m.run(lambda: refresh_others(m))
            refresh_prs(m)
        if shown["queue"]:
            refresh_queue(m)
            m.run(lambda: refresh_queue_runs(m))
        if shown["runs"]:
            refresh_runs(m)

    # What the view's own actions (a review, a merge) and an error card's Retry run again.
    w.state.set("refresh_prs", lambda: refresh_prs(w))
    w.state.set("refresh_others", lambda: refresh_others(w))
    w.state.set("refresh_queue", lambda: refresh_queue(w))
    w.state.set("refresh_runs", lambda: refresh_runs(w))
    w.state.set("refresh_queue_runs", lambda: refresh_queue_runs(w))

    def view(width):
        return draw.draw(w, width, options, shown)

    w.ui.view(view, title=TITLE)

    def start(w):
        started.append(True)
        w.ui.dock(TITLE, on_click=w.ui.open_workspace)
        w.clock.every(options["prs_refresh_seconds"], lambda: shown["prs"] and refresh_prs(w))
        # Its own timer, so the slow read of everyone else's PRs runs beside yours, not before them.
        w.clock.every(options["prs_refresh_seconds"], lambda: shown["prs"] and refresh_others(w))
        w.clock.every(options["queue_refresh_seconds"], lambda: shown["queue"] and refresh_queue(w))
        w.clock.every(options["runs_refresh_seconds"], lambda: shown["runs"] and refresh_runs(w))
        # Its own timer too: the queue's runs are a second read, and only while the queue is shown.
        w.clock.every(options["runs_refresh_seconds"], lambda: shown["queue"] and refresh_queue_runs(w))
        w.run(lambda: refresh_ai_chip(w))
        if options.get("refresh_key"):
            w.keys.bind(options["refresh_key"], "Refresh status", lambda: w.run(lambda: refresh_all(w)))

    w.on_start(start)

    @on("section.change")
    def section_changed(m, e, next):
        # A section just turned on has nothing to show until its first read.
        if e.enabled and started:
            refresh = {"prs": refresh_prs, "queue": refresh_queue, "runs": refresh_runs}[e.section]
            m.run(lambda: refresh(m))
            if e.section == "queue":
                m.run(lambda: refresh_queue_runs(m))
            if e.section == "prs":
                m.run(lambda: refresh_others(m))
        return next(e)

    # Workflows are what change GitHub (a review, a new PR, a merge), so refresh right after one
    # ends instead of waiting for the next poll - however it ended: a failed or aborted run may
    # have pushed or commented before stopping. Goes off the workflow's thread, so its end is
    # never delayed.
    @on("workflow.run")
    def after_workflow(m, e, next):
        try:
            return next(e)
        finally:
            if not e.nested and started:
                m.run(lambda: refresh_all(m))
