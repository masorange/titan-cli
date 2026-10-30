"""The pane's element tree, drawn from `m.state` only: it never waits on the network.

The pane answers "what needs me now?": the reviews asked of you, your PRs that have something to
act on, the CI runs that failed. Pressing one opens the workspace on it; the rest of GitHub is there.
"""
from titan_cli.ui.components import error_card
from titan_cli.ui.elements import Box, Button, Text

# Rows a section lists before "…and N more": the pane is narrow, the workspace has the rest.
SHOWN = 3


def open_on(m, **focus):
    return lambda: m.ui.open_workspace("github", focus=focus)


def mine_status(pr, queued: dict):
    """What one of your PRs is waiting on, when it is something you can act on; None when it just waits for a review."""
    entry = queued.get(pr.number)
    if entry is not None:
        return Text(f"⇢ in merge queue #{entry.position}" + (f" · {entry.eta_label}" if entry.eta_label else ""), color="info")
    if pr.checks_state == "failing":
        return Text("✗ checks failing", color="error")
    if pr.review_status_summary == "changes requested":
        return Text("✗ changes requested", color="error")
    if pr.has_conflicts:
        return Text("⚠ conflicts", color="warning")
    if not pr.is_draft and pr.review_status_summary == "approved" and pr.checks_state == "passing":
        return Text("✓ ready to merge", color="success")
    return None


def pr_line(m, pr, status):
    """A PR as two lines, the first pressable: its title, then why it is here."""
    return Box(
        Button(Text(Text(f"#{pr.number} ", bold=True), pr.title), open_on(m, pr=pr.number)),
        Text("   ", status),
        indent=0,
    )


def group(title: str, tone: str, rows: list, total: int) -> Box:
    return Box(
        Text(f"{title} ({total})", bold=True, color=tone),
        rows,
        total > len(rows) and Text(f"…and {total - len(rows)} more", dim=True),
    )


def totals(prs, queue, failing: int) -> Text:
    parts = [f"{prs.open_count} open", f"{len(prs.to_review)} to review", f"{len(prs.mine)} yours"]
    if queue is not None and queue.error is None and queue.configured:
        parts.append(f"queue {queue.total}")
    if failing is not None:
        parts.append(f"{failing} failing")
    return Text(" · ".join(parts), dim=True)


def draw(m) -> Box:
    prs, queue, runs = m.state.get("prs"), m.state.get("queue"), m.state.get("runs")
    if prs is None:
        return Text("Loading…", dim=True)
    if prs.error:
        return error_card(f"Could not read PRs: {prs.error}", copy=m.ui.copy, what="error")

    queued = {e.pr_number: e for e in (queue.entries if queue is not None and queue.error is None else [])}
    failed = [r for r in (runs.runs if runs is not None and runs.error is None else []) if r.state == "failure"]
    acting = [(p, s) for p in prs.mine if (s := mine_status(p, queued)) is not None]

    sections = []
    if prs.to_review:
        sections.append(group("Review requested", "warning", [
            pr_line(m, p, Text(
                f"@{p.author_name}", p.opened_age and f" · {p.opened_age}",
                p.has_conflicts and Text(" · ⚠ conflicts", color="warning"), dim=True))
            for p in prs.to_review[:SHOWN]
        ], len(prs.to_review)))
    if acting:
        sections.append(group("Your PRs", "info", [pr_line(m, p, s) for p, s in acting[:SHOWN]], len(acting)))
    if failed:
        sections.append(group("CI failing", "error", [
            Button(Text(Text("✗ ", color="error"), r.title, r.age and Text(f" · {r.age}", dim=True)), open_on(m, run=r.id))
            for r in failed[:SHOWN]
        ], len(failed)))
    return Box(
        Text(Text("GitHub", bold=True, color="primary"), prs.repo and Text(f"  {prs.repo}", dim=True)),
        totals(prs, queue, len(failed) if runs is not None and runs.error is None else None),
        *(sections or [Text("✓ All clear: nothing needs you", color="success")]),
        Button("Open GitHub workspace", lambda: m.ui.open_workspace("github"), variant="default"),
        gap=1,
    )
