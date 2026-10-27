"""
github: a side pane with review requests (each with a button that reviews
it), your PRs, the merge queue and CI check diagnosis.

The branch/commits section lives in the `git` mod shipped by
titan-plugin-git, since it reads the git plugin, not this one. Data comes
from the github plugin client on background timers; drawing reads only
`m.state`, so it never waits on the network. See docs/concepts/writing-mods.md.
"""
from pathlib import Path

from .diagnosis import refresh_ai_label
from . import draw
from .sections.prs.prs import new_review_requests, read_others, read_prs
from .sections.queue.queue import left_queue, read_queue

PANE = "github"
TITLE = "GitHub"


def register(on, options):
    where = {}
    shown = options.setdefault("sections", {})
    for name in ("prs", "queue"):
        shown.setdefault(name, True)

    def refresh_prs(m):
        before = m.state.get("prs")
        after = read_prs(m.client("github"))
        m.state.set("prs", after)
        # Asked here, off the UI thread: finding out may take a round-trip.
        m.state.set("slack_on", m.client("slack") is not None)
        waiting = len(after.to_review) if after.error is None else 0
        m.ui.badge(PANE, str(waiting) if waiting else None, severity="warning")
        arrived = new_review_requests(before, after)
        if arrived:
            m.ui.toast("Review requested: " + ", ".join(f"#{n}" for n in arrived))

    def refresh_others(m):
        m.state.set("others", read_others(m.client("github")))

    def refresh_queue(m):
        before = m.state.get("queue")
        after = read_queue(m.client("github"), options["queue_shown"])
        m.state.set("queue", after)
        left = left_queue(before, after)
        if left:
            m.ui.toast("Left the merge queue: " + ", ".join(f"#{n}" for n in left))

    @on("app.start")
    def start(m, e, next):
        where["root"] = Path(e.project_root)
        # How the pane's own review actions (approve, request changes, comment)
        # get the lists read again once GitHub has taken them.
        m.state.set("refresh_prs", lambda: refresh_prs(m))
        # What an error card's Retry runs again.
        m.state.set("refresh_others", lambda: refresh_others(m))
        m.state.set("refresh_queue", lambda: refresh_queue(m))
        m.ui.open(PANE, TITLE)
        m.clock.every(options["prs_refresh_seconds"], lambda: shown["prs"] and refresh_prs(m))
        # Its own timer, so the slow read of everyone else's PRs runs beside yours, not before them.
        m.clock.every(options["prs_refresh_seconds"], lambda: shown["prs"] and refresh_others(m))
        m.clock.every(options["queue_refresh_seconds"], lambda: shown["queue"] and refresh_queue(m))
        m.run(lambda: refresh_ai_label(m))
        if options.get("refresh_key"):
            m.keys.bind(options["refresh_key"], "Refresh status", lambda: m.run(lambda: refresh_all(m)))
        return next(e)

    def refresh_all(m):
        if shown["prs"]:
            m.run(lambda: refresh_others(m))
            refresh_prs(m)
        if shown["queue"]:
            refresh_queue(m)

    @on("section.change")
    def section_changed(m, e, next):
        # A section just turned on has nothing to show until its first read.
        if e.enabled and "root" in where:
            refresh = {"prs": refresh_prs, "queue": refresh_queue}[e.section]
            m.run(lambda: refresh(m))
            if e.section == "prs":
                m.run(lambda: refresh_others(m))
        return next(e)

    # Workflows are what change GitHub (a review, a new PR, a merge), so
    # refresh right after one ends instead of waiting for the next poll -
    # however it ended: a failed or aborted run may have pushed or commented
    # before stopping. Goes off the workflow's thread, so its end is never
    # delayed.
    @on("workflow.run")
    def after_workflow(m, e, next):
        try:
            return next(e)
        finally:
            if not e.nested and "root" in where:
                m.run(lambda: refresh_all(m))

    @on("ui.render", match={"component": "Pane", "pane": PANE})
    def render(m, e, next):
        return draw.draw(m, e.width, options, shown)
