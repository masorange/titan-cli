"""
github workspace: a full screen for the repo's GitHub, opened from its dock tile.

The pull requests (search, review actions, merge, conflicts, check diagnosis), the merge queue
and the workflow runs, drawn from `w.state` only so it never waits on the network. Data comes from
the plugin's feed (`titan_plugin_github.readers.feed`), shared with the `github` mod that keeps
the summary in the side pane, and is read only while this screen is open: a closed workspace
costs GitHub nothing.
"""
from titan_cli.ui.components import refresh_ai_chip
from titan_plugin_github.readers import runs as runs_reader
from titan_plugin_github.readers.feed import feed_for

from . import draw
from .sections.prs import search, threads

TITLE = "GitHub"
# How often a timer asks the feed. Asking is free while the feed's answer is younger than the
# option's period, or while the screen is closed; this bounds how late a due read is.
TICK_SECONDS = 5


def register(w, on, options):
    started = []
    shown = options.setdefault("sections", {})
    for name in ("prs", "queue", "runs"):
        shown.setdefault(name, True)

    def feed(m):
        return feed_for(m.client("github"))

    def refresh_prs(m):
        after = feed(m).prs(options["prs_refresh_seconds"])
        if after is m.state.get("prs"):
            return
        m.state.set("prs", after)
        # Asked here, off the UI thread: finding out may take a round-trip.
        m.state.set("slack_on", m.client("slack") is not None)
        if after.error is None:
            rows = m.state.get("rows_open") or {}
            threads.reread_open(m, after.mine, lambda number: bool(rows.get(str(number))))

    def keep(m, key, snapshot):
        if snapshot is not m.state.get(key):
            m.state.set(key, snapshot)

    def refresh_others(m):
        keep(m, "others", feed(m).others(options["prs_refresh_seconds"]))

    def refresh_queue(m):
        keep(m, "queue", feed(m).queue(options["queue_shown"], options["queue_refresh_seconds"]))

    def refresh_runs(m):
        keep(m, "runs", feed(m).runs(None, runs_reader.limit_of(m, "runs"), options["runs_refresh_seconds"]))

    def refresh_queue_runs(m):
        # The merge queue's own runs, apart from the repo's: GitHub tells them by their event.
        keep(m, "queue_runs", feed(m).runs(
            "merge_group", runs_reader.limit_of(m, "queue_runs"), options["runs_refresh_seconds"]))

    def forced(read, topic):
        """`read`, but from GitHub and not from what the mod or the timers just read."""
        def again(m):
            feed(m).refresh(topic)
            read(m)
        return again

    def while_open(section, read):
        """A timer's read: only while the screen is open and the section is on."""
        def tick():
            if shown[section] and w.ui.is_open():
                read(w)
        return tick

    def refresh_all(m):
        feed(m).refresh()
        if shown["prs"]:
            m.run(lambda: refresh_others(m))
            refresh_prs(m)
        if shown["queue"]:
            refresh_queue(m)
            m.run(lambda: refresh_queue_runs(m))
        if shown["runs"]:
            refresh_runs(m)

    # What the view's own actions (a review, a merge) and an error card's Retry run again.
    w.state.set("refresh_prs", lambda: forced(refresh_prs, "prs")(w))
    w.state.set("refresh_others", lambda: forced(refresh_others, "others")(w))
    w.state.set("refresh_queue", lambda: forced(refresh_queue, "queue")(w))
    w.state.set("refresh_runs", lambda: forced(refresh_runs, ("runs", None))(w))
    w.state.set("refresh_queue_runs", lambda: forced(refresh_queue_runs, ("runs", "merge_group"))(w))

    def view(width):
        return draw.draw(w, width, options, shown)

    w.ui.view(view, title=TITLE)

    def start(w):
        started.append(True)
        w.ui.dock(TITLE, on_click=w.ui.open_workspace)
        w.clock.every(TICK_SECONDS, while_open("prs", refresh_prs))
        # Its own timer, so the slow read of everyone else's PRs runs beside yours, not before them.
        w.clock.every(TICK_SECONDS, while_open("prs", refresh_others))
        w.clock.every(TICK_SECONDS, while_open("queue", refresh_queue))
        w.clock.every(TICK_SECONDS, while_open("runs", refresh_runs))
        # Its own timer too: the queue's runs are a second read, and only while the queue is shown.
        w.clock.every(TICK_SECONDS, while_open("queue", refresh_queue_runs))
        w.run(lambda: refresh_ai_chip(w))
        if options.get("refresh_key"):
            w.keys.bind(options["refresh_key"], "Refresh status", lambda: w.run(lambda: refresh_all(w)))

    w.on_start(start)

    def focus(w, what):
        """Show what the mod's pane was pressed on: a PR or a run, its row open and its group unfolded."""
        if not isinstance(what, dict):
            return
        if what.get("pr"):
            number = what["pr"]
            prs = w.state.get("prs")
            mine = prs is not None and any(p.number == number for p in prs.mine)
            search.clear(w)
            w.state.set("mine_open" if mine else "review_open", True)
            w.state.update("rows_open", lambda rows: {**(rows or {}), str(number): True}, default={})
            if mine:
                threads.start(w, number)
        elif what.get("run"):
            w.state.set("runs_open", True)
            w.state.update("rows_open", lambda rows: {**(rows or {}), f"run:{what['run']}": True}, default={})

    w.on_open(focus)

    def read_on_open(w, what):
        # At once, not on the next tick: what the feed holds is shared, so this is often free.
        # Not through `while_open`: the screen is pushed right after this runs.
        for section, reads in (("prs", (refresh_prs, refresh_others)),
                               ("queue", (refresh_queue, refresh_queue_runs)),
                               ("runs", (refresh_runs,))):
            if shown[section]:
                for read in reads:
                    w.run(lambda read=read: read(w))

    w.on_open(read_on_open)

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
            # Closed, it has nothing to show: the mod rereads what it shows, and opening reads the rest.
            if not e.nested and started and w.ui.is_open():
                m.run(lambda: refresh_all(m))
