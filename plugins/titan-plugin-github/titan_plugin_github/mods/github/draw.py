"""The pane's element tree, drawn from `m.state` only: it never waits on the network."""
from typing import Optional

from titan_cli.core.mods import Box, Button, Input, Link, Text
from titan_plugin_github.models.view import UIMergeQueueEntry, UIPullRequest

from .diagnosis import Diagnosis, diagnosis_text, refresh_ai_label, start_diagnosis
from .models import Composer, Prs, Queue
from .sections.prs import actions, conflicts

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
        # Saying why it broke is half the job; this hands the logs (and the
        # diagnosis, when there is one) to an interactive session on the branch.
        not running and (options or {}).get("checks_workflow") and action_button(
            "⚒ Fix with AI",
            lambda: m.workflows.run(options["checks_workflow"], {
                "fix_pr_number": pr.number,
                "check_diagnosis": diagnosis_text(pr, d) if done else "",
            }),
            "error",
        ),
        indent=3,
    )


def composer_box(m, c: Composer) -> Box:
    """GitHub's own comment box: a field, then Accept (sends it) or Cancel (back to the buttons)."""
    return Box(
        Text(f"Comment on #{c.number}", dim=True),
        Input(
            c.text,
            placeholder="Write a comment…",
            on_change=lambda text: actions.write(m, text),
            on_submit=lambda text: actions.submit(m, text),
        ),
        Box(
            Button("Accept", lambda: actions.send(m), variant="success"),
            Button("Cancel", lambda: actions.close_composer(m), variant="default"),
            row=True,
        ),
        indent=3,
    )


# One under the other, every label padded to the widest: four buttons of one size,
# with one left and one right edge, instead of a ragged row that a narrow pane cuts.
ACTION_WIDTH = max(len(label) for label in ("Review", "✓ Approve", "✗ Request changes", "✎ Comment"))


def action_button(label: str, on_press, variant: str) -> Button:
    return Button(label.ljust(ACTION_WIDTH), on_press, variant=variant)


def review_actions(m, pr: UIPullRequest, options) -> Box:
    """What can be done about a review request: review it in a workflow, or answer GitHub right here."""
    in_flight = actions.running(m, pr.number)
    if in_flight:
        return Box(Text(f"… {actions.PROGRESS[in_flight]}", dim=True), indent=3)
    c = actions.composer(m)
    if c is not None and c.number == pr.number:
        return composer_box(m, c)
    workflow = (options or {}).get("review_workflow")
    return Box(
        # Review runs the workflow on this PR, skipping its PR picker.
        workflow and action_button("Review", lambda: m.workflows.run(workflow, {"review_pr_number": pr.number}), "default"),
        action_button("✓ Approve", lambda: actions.start(m, pr.number, "approve"), "success"),
        # Request changes goes out with no body, exactly as the review-pr workflow submits it.
        action_button("✗ Request changes", lambda: actions.start(m, pr.number, "request_changes"), "error"),
        action_button("✎ Comment", lambda: actions.open_composer(m, pr.number), "default"),
        indent=3,
    )


REVIEWER_TONE = {"changes_requested": "error", "approved": "success", "commented": "info", "pending": "subtle"}


def reviewer_line(m, pr: UIPullRequest, reviewer):
    """One reviewer; pressable to ask them again, which only means something once they have reviewed."""
    label = f"{reviewer.icon} @{reviewer.login}" + (f" · {reviewer.when}" if reviewer.when else "")
    if not reviewer.has_reviewed:
        return Text(label, color=REVIEWER_TONE[reviewer.state], dim=True)
    return Button(f"{label}  ⟳", lambda: actions.rerequest(m, pr.number, [reviewer.login]), dim=True)


def reviewers_fold(m, pr: UIPullRequest) -> Box:
    """Who is reviewing, counted in the title so the tally shows without opening it."""
    tally = " ".join(
        f"{icon}{sum(1 for r in pr.reviewers if r.state == state)}"
        for state, icon in (("changes_requested", "✗"), ("approved", "✓"), ("commented", "✎"), ("pending", "○"))
        if any(r.state == state for r in pr.reviewers)
    )
    return fold(
        m, f"reviewers_open:{pr.number}", f"Reviewers {tally}" if tally else "Reviewers · nobody asked yet", False,
        [reviewer_line(m, pr, r) for r in pr.reviewers],
    )


def size_text(pr: UIPullRequest) -> Text:
    """What the PR touches: added lines in green, removed in red, as a diff reads."""
    return Text(
        pr.additions and Text(f"+{pr.additions}", color="success"),
        pr.additions and pr.deletions and " ",
        pr.deletions and Text(f"−{pr.deletions}", color="error"),
        pr.files_changed and Text(f"{' · ' if pr.additions or pr.deletions else ''}{pr.files_changed} files", dim=True),
    )


def conflicts_fold(m, pr: UIPullRequest, options) -> Box:
    """What clashes with the base branch, asked of git the first time it is opened."""
    key = f"conflicts_open:{pr.number}"
    is_open = bool(m.state.get(key))
    found = conflicts.of(m, pr.number)
    workflow = (options or {}).get("conflicts_workflow")

    def toggle():
        m.state.set(key, not is_open)
        # Asking git costs a fetch, so it waits until someone wants to know.
        if not is_open and found is None:
            conflicts.start(m, pr)

    counted = found is not None and found.status == "done" and found.files
    return Box(
        Button(f"{'▾' if is_open else '▸'} ⚠ Conflicts" + (f" ({len(found.files)})" if counted else ""),
               toggle, dim=True),
        is_open and Box(
            (found is None or found.status == "running") and Text("… asking git", dim=True),
            found is not None and found.status == "error" and Text(f"Could not tell: {found.error}", color="error", wrap=True),
            found is not None and found.status == "done" and not found.files
            and Text(f"Nothing clashes with {pr.base_ref} any more", color="success"),
            counted and [Text(path, color="error", dim=True) for path in found.files],
            workflow and action_button(
                "⚒ Resolve conflicts",
                lambda: m.workflows.run(workflow, {"conflict_pr_number": pr.number}),
                "error",
            ),
            indent=2,
        ),
    )


def my_pr_detail(m, pr: UIPullRequest, options) -> Box:
    """What is worth knowing about a PR of your own, and what can be done about it.

    Two lines carry four facts: what it lands on and how old it is, what it
    changes and when it was last touched ("↻"), each pair on one line with the
    time pushed to the right edge.
    """
    reviewed = [r.login for r in pr.reviewers if r.has_reviewed]
    in_flight = actions.running(m, pr.number)
    return Box(
        (pr.branch_info or pr.opened_age) and Box(
            Text(pr.branch_info or " ", dim=True),
            Text(pr.opened_age or " ", dim=True),
            row=True,
        ),
        (pr.additions or pr.deletions or pr.files_changed or pr.updated_age) and Box(
            size_text(pr),
            Text(pr.updated_age and f"↻ {pr.updated_age}" or " ", dim=True),
            row=True,
        ),
        pr.labels and Text(", ".join(pr.labels), color="info", dim=True),
        pr.has_conflicts and conflicts_fold(m, pr, options),
        pr.reviewers and reviewers_fold(m, pr),
        pr.assignees and fold(m, f"assignees_open:{pr.number}", f"Assignees ({len(pr.assignees)})", False,
                              [Text(f"@{login}", dim=True) for login in pr.assignees]),
        in_flight and Text(f"… {actions.PROGRESS[in_flight]}", dim=True),
        not in_flight and reviewed and action_button(
            f"⟳ Re-request review ({len(reviewed)})", lambda: actions.rerequest(m, pr.number), "default"),
        indent=3,
    )


def row_open(m, number: int) -> bool:
    """Whether this PR shows what can be done about it; closed until it is pressed."""
    return bool((m.state.get("rows_open") or {}).get(str(number)))


def toggle_row(m, number: int) -> None:
    key = str(number)
    m.state.update("rows_open", lambda all_: {**(all_ or {}), key: not bool((all_ or {}).get(key))}, default={})


def pr_row(pr: UIPullRequest, is_mine: bool, queued: dict, m=None, options=None) -> Box:
    entry = queued.get(pr.number)
    review = (
        Text("○ draft", dim=True)
        if pr.is_draft
        else Text(f"● {REVIEW_LABEL.get(pr.review_status_summary, 'awaiting review')}",
                  color=REVIEW_TONE.get(pr.review_status_summary, "warning"))
    )
    # An action in flight keeps its row open, however the row was last left.
    expanded = m is not None and (row_open(m, pr.number) or actions.running(m, pr.number) is not None)
    title = (
        Text(pr_link(pr.number, pr.url), " ", pr.title)
        if m is None
        else Button(f"{'▾' if expanded else '▸'} #{pr.number} {pr.title}", lambda: toggle_row(m, pr.number))
    )
    return Box(
        Text(" "),
        title,
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
        expanded and [
            # The number is the fold now, so the way to GitHub lives in here.
            pr.url and Box(Text(Link("↗ Open on GitHub", pr.url)), indent=3),
            is_mine and my_pr_detail(m, pr, options),
            # Fixing a red check is the author's job, so only my own PRs get a diagnosis.
            is_mine and pr.checks_state == "failing" and diagnosis_of(m, pr, options),
            not is_mine and review_actions(m, pr, options),
        ],
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
