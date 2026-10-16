"""The pane's element tree, drawn from `m.state` only: it never waits on the network."""
from typing import Optional

from titan_cli.core.mods import Box, Button, Link, Text
from titan_plugin_github.models.view import UIMergeQueueEntry, UIPullRequest

from .diagnosis import Diagnosis, diagnosis_text, refresh_ai_label, start_diagnosis
from .models import Prs, Queue

QUEUE_TONE = {"QUEUED": "subtle", "AWAITING_CHECKS": "warning", "MERGEABLE": "success", "UNMERGEABLE": "error", "LOCKED": "error"}
# A PR with no review decision yet is waiting for one, as GitHub's own lists put it.
REVIEW_LABEL = {"approved": "approved", "changes requested": "changes requested"}
REVIEW_TONE = {"approved": "success", "changes requested": "error"}
CHECKS_LABEL = {"passing": "✓ checks", "failing": "✗ checks", "running": "… checks"}
CHECKS_TONE = {"passing": "success", "failing": "error", "running": "warning"}


def pr_link(number: int, url: str, bold_color: str = "info"):
    """The PR's number, opening it on GitHub when its page is known."""
    if url:
        return Link(f"#{number}", url)
    return Text(f"#{number}", bold=True, color=bold_color)


def section(title, color: str, *body):
    return Box(title if isinstance(title, Text) else Text(title, bold=True, color=color), *body, border=color)


def diagnosis_of(m, pr: UIPullRequest, options) -> Box:
    d: Optional[Diagnosis] = (m.state.get("diagnoses") or {}).get(str(pr.number))
    running = d is not None and d.status == "running"
    if running:
        label = f"… diagnosing with {d.model or 'AI routing'}"
    elif d is not None and d.status == "done":
        label = f"✦ Diagnose again (last: {d.model or 'AI routing'})"
    else:
        label = "✦ Diagnose failure"

    def press():
        start_diagnosis(m, pr.number, options)

    done = d is not None and d.status == "done"
    urls = {c.name: c.url for c in pr.failed_checks}
    return Box(
        Button(label, press, dim=not running),
        d is not None and d.status == "error" and Text(f"Could not diagnose: {d.error}", color="error"),
        done and [
            Box(
                Text(" "),
                Text("✗ ", Link(j.job_name, urls[j.job_name]) if urls.get(j.job_name) else j.job_name, color="error"),
                Text(j.cause, wrap=True),
                j.where and Text(f"  at {j.where}", color="info"),
                j.quote and Text(f"“{j.quote}”", dim=True, wrap=True),
                j.quote and not j.is_quote_in_log and Text("  ⚠ this line is not in the log: do not trust the cause", color="warning"),
            )
            for j in d.jobs
        ],
        done and len(pr.failed_checks) > len(d.jobs) and Text(f"…and {len(pr.failed_checks) - len(d.jobs)} more failed checks", dim=True),
        d is not None and not running and Button(
            "⧉ Copy " + ("error" if d.status == "error" else "diagnosis"),
            lambda: m.ui.copy(diagnosis_text(pr, d), f"#{pr.number} " + ("error" if d.status == "error" else "diagnosis")),
            dim=True,
        ),
        indent=3,
    )


def review_button(m, pr: UIPullRequest, workflow: str) -> Button:
    """Runs the review workflow on this PR, skipping its PR picker."""
    return Button(f"Review #{pr.number}", lambda: m.workflows.run(workflow, {"review_pr_number": pr.number}), variant="primary")


def pr_row(pr: UIPullRequest, is_mine: bool, queued: dict, m=None, options=None) -> Box:
    entry = queued.get(pr.number)
    review = (
        Text("○ draft", dim=True)
        if pr.is_draft
        else Text(f"● {REVIEW_LABEL.get(pr.review_status_summary, 'awaiting review')}",
                  color=REVIEW_TONE.get(pr.review_status_summary, "warning"))
    )
    return Box(
        Text(" "),
        Text(pr_link(pr.number, pr.url), " ", pr.title),
        Text(
            not is_mine and Text(f"@{pr.author_name} · ", dim=True),
            review,
            pr.checks_state in CHECKS_LABEL and Text(
                f"  {CHECKS_LABEL[pr.checks_state]}" + (f" ({len(pr.failed_checks)})" if pr.failed_checks else ""),
                color=CHECKS_TONE[pr.checks_state],
            ),
            pr.has_conflicts and Text("  ⚠ conflicts", color="error"),
        ),
        entry and Text(f"   ⇢ in merge queue #{entry.position}" + (f" · {entry.eta_label}" if entry.eta_label else ""), color="info"),
        # Fixing a red check is the author's job, so only my own PRs get a diagnosis.
        is_mine and pr.checks_state == "failing" and m is not None and diagnosis_of(m, pr, options),
        not is_mine and m is not None and (options or {}).get("review_workflow")
        and Box(review_button(m, pr, options["review_workflow"]), indent=3),
    )


def model_picker(m, options):
    """
    Who answers a diagnosis, and the way to change it: Titan's own per-task picker
    (remote or CLI, then which one and its model) for the task "mods.github".
    """
    pinned = m.state.get("ai_pinned")
    how = "pinned for this panel" if pinned else "Titan's AI default"
    return Box(
        Text("✦ Diagnosis AI", dim=True),
        Button(
            f"  ⟳ {m.state.get('ai_label') or '…'}",
            lambda: m.ai.configure("PR check diagnosis", on_done=lambda: m.run(lambda: refresh_ai_label(m))),
        ),
        Text(f"    {how} · Enter/click to change", dim=True),
    )


def fold(m, key: str, label: str, default_open: bool, *body):
    """A pressable title that shows its body only while open; remembers what the person chose."""
    chosen = m.state.get(key)
    is_open = default_open if chosen is None else chosen
    return Box(
        Button(f"{'▾' if is_open else '▸'} {label}", lambda: m.state.set(key, not is_open), dim=True),
        is_open and Box(*body, indent=2),
    )


def queue_row(e: UIMergeQueueEntry) -> Box:
    return Box(
        Text(" "),
        Text(Text(f"{e.position}. ", dim=True), pr_link(e.pr_number, e.url, "accent" if e.is_mine else "info"), f" {e.title}"),
        Text("   ", Text(f"@{e.author} · ", dim=True), Text(f"● {e.state_label}", color=QUEUE_TONE.get(e.state, "subtle")),
             e.eta_label and Text(f" · {e.eta_label}", bold=True)),
    )


def queue_fold(m, queue: Queue):
    return fold(
        m, "queue_open",
        "Merge queue · unavailable" if queue.error else
        f"Merge queue · {queue.branch} ({queue.total})" + (f" · {queue.merge_method}" if queue.merge_method else ""),
        bool(queue.entries or queue.error),
        queue.error and Text(queue.error, color="error"),
        not queue.error and queue.total == 0 and Text("Queue empty", dim=True),
        [queue_row(e) for e in queue.entries],
        queue.total > len(queue.entries) and Text(f"…and {queue.total - len(queue.entries)} more", dim=True),
    )


def draw(m, width: int, options=None, shown=None):
    options = options or {"diagnosis_jobs": 3}
    shown = shown or {"prs": True, "queue": True}
    if not any(shown.values()):
        return Text("Every section is switched off (Mods screen).", dim=True)
    prs: Optional[Prs] = m.state.get("prs") if shown["prs"] else None
    queue: Optional[Queue] = m.state.get("queue") if shown["queue"] else None
    if prs is None and queue is None:
        return Text("Loading…", dim=True)

    parts = []
    queued = {e.pr_number: e for e in (queue.entries if queue else [])}
    if shown["prs"] and prs is None:
        # Framed like the section it is about to become, instead of a bare line
        # with no border while queue above/below it already has one.
        parts.append(section(Text("⇄ Pull requests", bold=True, color="info"), "info", Text("Loading…", dim=True)))
    elif prs is not None:
        tone = "error" if prs.error else "warning" if prs.to_review else "info"
        title = Text(
            Text("⇄ Pull requests", bold=True, color=tone),
            not prs.error and Text(f" {prs.repo + ' · ' if prs.repo else ''}{prs.open_count} open", dim=True),
            not prs.error and prs.to_review and Text(f"  ⚠ {len(prs.to_review)} to review", bold=True, color="warning"),
        )
        if prs.error:
            parts.append(section(title, tone, Text(f"Could not read PRs: {prs.error}", dim=True)))
        else:
            parts.append(section(title, tone, Box(
                # Empty groups start closed; each one keeps what the person last chose.
                fold(m, "review_open", f"Needs your review ({len(prs.to_review)})", bool(prs.to_review),
                     not prs.to_review and Text("Nothing pending", dim=True),
                     [pr_row(p, False, queued, m, options) for p in prs.to_review]),
                fold(m, "mine_open", f"Your PRs ({len(prs.mine)})", bool(prs.mine),
                     not prs.mine and Text("No open PRs", dim=True),
                     [pr_row(p, True, queued, m, options) for p in prs.mine]),
                model_picker(m, options),
                gap=1,
            )))
    if queue is not None and (queue.configured or queue.error):
        parts.append(section(Text("⇉ Merge queue", bold=True, color="info"), "info", queue_fold(m, queue)))
    return Box(*parts)
