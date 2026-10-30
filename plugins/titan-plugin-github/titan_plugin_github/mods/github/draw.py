"""The pane's element tree, drawn from `m.state` only: it never waits on the network."""
from titan_cli.ui.elements import Box, Button, Text


def line(label: str, value, tone: str = "info"):
    return Text(Text(f"{label} ", dim=True), Text(str(value), bold=True, color=tone))


def draw(m) -> Box:
    prs, queue, runs = m.state.get("prs"), m.state.get("queue"), m.state.get("runs")
    rows = []
    if prs is None:
        rows.append(Text("Loading…", dim=True))
    elif prs.error:
        rows.append(Text(f"Could not read PRs: {prs.error}", color="error", wrap=True))
    else:
        rows.append(line("To review", len(prs.to_review), "warning" if prs.to_review else "info"))
        rows.append(line("Your PRs", len(prs.mine)))
        rows.append(line("Open on the repo", prs.open_count))
    if queue is not None and queue.error is None and queue.configured:
        rows.append(line(f"Merge queue ({queue.branch})", queue.total))
    if runs is not None and runs.error is None:
        failing = sum(1 for r in runs.runs if r.state == "failure")
        rows.append(line("Failing runs (latest)", failing, "error" if failing else "info"))
    return Box(
        *rows,
        Button("Open GitHub workspace", lambda: m.ui.open_workspace("github")),
        gap=1,
    )
