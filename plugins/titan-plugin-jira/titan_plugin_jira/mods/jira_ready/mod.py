"""
jira_ready: a side pane answering "what needs me in Jira?": the unfinished issues assigned to you,
latest touched first. Pressing one opens the `jira` workspace on it, where the whole of Jira is
(search, filters, comments, AI summary, move, fix version, plan, take).

The read is shared with the workspace (`titan_plugin_jira.readers`); this file only polls and
draws. Reads run on a background thread; drawing reads only `m.state`, so it never waits on the
network.
"""
from titan_cli.ui.components import error_card
from titan_cli.ui.elements import Box, Button, Text
from titan_plugin_jira.readers import issues as reader
from titan_plugin_jira.readers.models import Ready

PANE = "jira-ready"
TITLE = "Jira"
# Rows listed before "…and N more": the pane is narrow, the workspace has the rest.
SHOWN = 5


def read(jira, options) -> Ready:
    """The issues assigned to the user in the configured projects (or every one they can see)."""
    return reader.read_mine(jira, reader.default_projects(jira, options), options["shown"])


def issue_row(m, issue) -> Button:
    """One pressable line per issue: its status colour, key and summary; it opens the workspace on it."""
    return Button(Text(Text(f"{issue.status_icon} {issue.key} ", bold=True), issue.summary),
                  lambda: m.ui.open_workspace("jira", focus={"issue": issue.key}))


def draw(m, options) -> Box:
    ready = m.state.get("ready")
    open_workspace = Button("Open Jira workspace", lambda: m.ui.open_workspace("jira"), variant="default")
    if ready is None:
        return Box(Text("Loading…", dim=True), open_workspace, gap=1)
    if ready.error:
        retry = Button("↻ Retry", lambda: m.run(lambda: m.state.set("ready", read(m.client("jira"), options))))
        return Box(error_card(f"Could not read Jira: {ready.error}", copy=m.ui.copy, what="error", actions=[retry]),
                   open_workspace, gap=1)
    shown = [issue_row(m, i) for i in ready.issues[:SHOWN]]
    total = f"{len(ready.issues)}{'+' if ready.more else ''}"
    return Box(
        Text(Text("Assigned to you", bold=True, color="primary"), Text(f"  {ready.project}" if ready.project else "", dim=True)),
        Text(f"{total} unfinished", dim=True),
        *(shown or [Text("✓ Nothing assigned to you", color="success")]),
        len(ready.issues) > SHOWN and Text(f"…and {len(ready.issues) - SHOWN} more", dim=True),
        open_workspace,
        gap=1,
    )


def register(on, options):
    def refresh(m):
        m.state.set("ready", read(m.client("jira"), options))

    @on("app.start")
    def start(m, e, next):
        m.ui.open(PANE, TITLE)
        m.clock.every(options["refresh_seconds"], lambda: refresh(m))
        return next(e)

    @on("ui.render", match={"component": "Pane", "pane": PANE})
    def render(m, e, next):
        return draw(m, options)
