"""The pane's element tree, drawn from `m.state` only: it never waits on the network."""
import webbrowser
from typing import Optional

from titan_cli.core.mods import Box, Button, Input, Link, Option, Text, choice_card, error_card, fix_with_ai_button
from titan_plugin_github.models.view import UIMergeQueueEntry, UIPullRequest, UIWorkflowRun
from titan_plugin_github.operations import format_diagnoses_report

from .diagnosis import Diagnosis, diagnosis_text, run_key, start_diagnosis, start_run_diagnosis
from .models import Composer, Others, Prs, Queue, Runs, Search
from .sections.prs import actions, conflicts, merge, search, threads
from .sections.runs import actions as run_actions, runs as runs_reader

QUEUE_CHECKS = {"passing": ("✓ checks", "success"), "failing": ("✗ checks failing", "error")}
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


def error_box(m, text: str, what: str = "error", retry: Optional[str] = None) -> Box:
    """An error that can be copied whole, in the shared error card; `retry` names the read to run again."""
    reread = m.state.get(f"refresh_{retry}") if retry else None
    retrying = bool(retry and m.state.get(f"retrying:{retry}"))

    def press():
        m.state.set(f"retrying:{retry}", True)

        def again():
            try:
                reread()
            finally:
                m.state.set(f"retrying:{retry}", False)

        m.run(again)

    actions = [Button("… retrying" if retrying else "⟳ Retry", (lambda: None) if retrying else press, dim=retrying)] if reread else []
    return error_card(text, copy=m.ui.copy, what=what, actions=actions)


# What the pane's own frame takes off the width a PR row is drawn in: the section's
# border and padding (4), the group's fold (2) and the row's indent (3).
ROW_INSET = 9


def diagnose_label(d: Optional[Diagnosis]):
    """Whether a diagnosis is running, and what its button says."""
    running = d is not None and d.status == "running"
    if running:
        return True, f"… diagnosing with {d.model or 'AI routing'}"
    if d is not None and d.status == "done":
        return False, f"✦ Diagnose again (last: {d.model or 'AI routing'})"
    return False, "✦ Diagnose failure"


def diagnosed_jobs(d: Diagnosis, urls: dict):
    """What the AI found for each failed job: cause, where, and the log line it rests on."""
    return [
        Box(
            Text(" "),
            Text("✗ ", Link(j.job_name, urls[j.job_name]) if urls.get(j.job_name) else j.job_name, color="error"),
            Text(j.cause, wrap=True),
            j.where and Text(f"  at {j.where}", color="info"),
            j.quote and Text(f"“{j.quote}”", dim=True, wrap=True),
            j.quote and not j.is_quote_in_log and Text("  ⚠ this line is not in the log: do not trust the cause", color="warning"),
        )
        for j in d.jobs
    ]


def diagnosis_of(m, pr: UIPullRequest, options, width: int = 40) -> Box:
    d: Optional[Diagnosis] = (m.state.get("diagnoses") or {}).get(str(pr.number))
    running, label = diagnose_label(d)

    def press():
        start_diagnosis(m, pr.number, options)

    done = d is not None and d.status == "done"
    urls = {c.name: c.url for c in pr.failed_checks}
    run_ids = sorted({c.run_id for c in pr.failed_checks if c.run_id})
    return Box(
        Button(label, press, dim=not running),
        d is not None and d.status == "error" and Text(f"Could not diagnose: {d.error}", color="error"),
        done and diagnosed_jobs(d, urls),
        done and len(pr.failed_checks) > len(d.jobs) and Text(f"…and {len(pr.failed_checks) - len(d.jobs)} more failed checks", dim=True),
        d is not None and not running and Button(
            "⧉ Copy " + ("error" if d.status == "error" else "diagnosis"),
            lambda: m.ui.copy(diagnosis_text(pr, d), f"#{pr.number} " + ("error" if d.status == "error" else "diagnosis")),
            dim=True,
        ),
        not running and choice_card(
            [
                # A cancelled runner or a flaky test needs no fix, only another go.
                run_ids and Option("⟳ Re-run failed jobs", lambda: actions.rerun(m, pr.number, run_ids)),
                # Saying why it broke is half the job; this hands the logs (and the
                # diagnosis, when there is one) to an interactive session on the branch.
                (options or {}).get("checks_workflow") and Option(
                    "✦ Fix with AI",
                    lambda: m.workflows.run(options["checks_workflow"], {
                        "fix_pr_number": pr.number,
                        "check_diagnosis": diagnosis_text(pr, d) if done else "",
                    }),
                    "error",
                ),
            ],
            width=width - ROW_INSET,
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


def action_button(label: str, on_press, variant: str, width: int = ACTION_WIDTH) -> Button:
    return Button(label.ljust(width), on_press, variant=variant)


def open_on_github(pr: UIPullRequest) -> Optional[Option]:
    """The way to the PR's page, as one more action of its card."""
    if not pr.url.startswith(("https://", "http://")):
        return None
    return Option("↗ Open on GitHub", lambda: webbrowser.open(pr.url))


def review_actions(m, pr: UIPullRequest, options, width: int = 40) -> Box:
    """What can be done about a review request: review it in a workflow, or answer GitHub right here."""
    in_flight = actions.running(m, pr.number)
    if in_flight:
        return Box(Text(f"… {actions.PROGRESS[in_flight]}", dim=True), indent=3)
    c = actions.composer(m)
    if c is not None and c.number == pr.number:
        return composer_box(m, c)
    workflow = (options or {}).get("review_workflow")
    return Box(
        choice_card(
            [
                # Review runs the workflow on this PR, skipping its PR picker.
                workflow and Option("Review", lambda: m.workflows.run(workflow, {"review_pr_number": pr.number})),
                Option("✓ Approve", lambda: actions.start(m, pr.number, "approve"), "success"),
                # Request changes goes out with no body, exactly as the review-pr workflow submits it.
                Option("✗ Request changes", lambda: actions.start(m, pr.number, "request_changes"), "error"),
                Option("✎ Comment", lambda: actions.open_composer(m, pr.number)),
                open_on_github(pr),
            ],
            width=width - ROW_INSET,
            title="Actions",
        ),
        indent=3,
    )


REVIEWER_TONE = {"changes_requested": "error", "approved": "success", "commented": "info", "pending": "primary"}


def reviewer_line(m, pr: UIPullRequest, reviewer):
    """One reviewer; pressable to ask them again, which only means something once they have reviewed."""
    label = f"{reviewer.icon} @{reviewer.login}" + (f" · {reviewer.when}" if reviewer.when else "")
    if not reviewer.has_reviewed:
        return Text(label, color=REVIEWER_TONE[reviewer.state])
    return Button(f"{label}  ⟳", lambda: actions.rerequest(m, pr.number, [reviewer.login]))


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


def notify_text(options, pr: UIPullRequest) -> str:
    """The channel message for a PR, from the `notify_message` option."""
    template = (options or {}).get("notify_message") or "Merging [#{number} {title}]({url})"
    return template.format(number=pr.number, title=pr.title, url=pr.url, author=pr.author_name, branch=pr.head_ref)


def merge_confirmation(m, pr: UIPullRequest, queue: Optional[Queue], width: int):
    """Merging cannot be undone, so the first press asks and this card is the second."""
    what = "join the merge queue" if merge.uses_queue(pr, queue) else "squash and merge"
    return choice_card(
        [
            Option("✓ Confirm", lambda: actions.merge(m, pr.number), "success"),
            Option("✗ Cancel", lambda: actions.cancel_merge(m)),
        ],
        width=width - ROW_INSET,
        title=f"Sure? This will {what}.",
        border="warning",
    )


def my_pr_detail(m, pr: UIPullRequest, options, queue: Optional[Queue] = None, queued: bool = False,
                 width: int = 40) -> Box:
    """What is worth knowing about a PR of your own, and what can be done about it.

    Top to bottom: the facts (what it lands on and how old it is, what it
    changes and when it was last touched "↻", each pair on one line with the
    time pushed to the right edge), the folds (conflicts,
    reviewers, assignees), and last the things to press, set apart by a gap.
    """
    reviewed = [r.login for r in pr.reviewers if r.has_reviewed]
    in_flight = actions.running(m, pr.number)
    notify = bool(m.state.get("slack_on") and (options or {}).get("notify_workflow"))
    # A PR already in the queue has had its merge asked for; one in flight is busy.
    reasons = [] if queued or in_flight else merge.blockers(pr, threads.unresolved(m, pr.number))
    confirming = not queued and not in_flight and not reasons and actions.merge_pending(m) == pr.number
    hint = (
        f"… {actions.PROGRESS[in_flight]}" if in_flight else
        "⇢ waiting in the merge queue" if queued else
        "Not ready to merge: " + ", ".join(reasons) if reasons else ""
    )
    return Box(
        (pr.branch_info or pr.updated_age) and Box(
            Text(pr.branch_info or " ", dim=True),
            Text(pr.updated_age and f"↻ {pr.updated_age}" or " ", dim=True),
            row=True,
        ),
        (pr.additions or pr.deletions or pr.files_changed or pr.opened_age) and Box(
            size_text(pr),
            Text(pr.opened_age or " ", dim=True),
            row=True,
        ),
        pr.has_conflicts and conflicts_fold(m, pr, options),
        pr.reviewers and reviewers_fold(m, pr),
        pr.assignees and fold(m, f"assignees_open:{pr.number}", f"Assignees ({len(pr.assignees)})", False,
                              [Text(f"@{login}", dim=True) for login in pr.assignees]),
        Text(" "),
        confirming and merge_confirmation(m, pr, queue, width),
        choice_card(
            [
                not queued and not in_flight and not reasons and not confirming and Option(
                    merge.label(pr, queue), lambda: actions.ask_merge(m, pr.number), "success"),
                notify and not reasons and Option(
                    "✉ Notify channel", lambda: m.workflows.run(options["notify_workflow"], {
                        "slack_message_markdown": notify_text(options, pr)})),
                not in_flight and reviewed and Option(
                    f"⟳ Re-request review ({len(reviewed)})", lambda: actions.rerequest(m, pr.number)),
                open_on_github(pr),
            ],
            width=width - ROW_INSET,
            title="Actions",
            hint=hint,
        ),
        indent=3,
    )


def row_open(m, number: int) -> bool:
    """Whether this PR shows what can be done about it; closed until it is pressed."""
    return bool((m.state.get("rows_open") or {}).get(str(number)))


def toggle_row(m, number: int) -> None:
    key = str(number)
    m.state.update("rows_open", lambda all_: {**(all_ or {}), key: not bool((all_ or {}).get(key))}, default={})


def open_pr_row(m, pr: UIPullRequest, is_mine: bool, was_open: bool) -> None:
    """Open or close a PR's row; opening one of yours asks GitHub what blocks its merge."""
    toggle_row(m, pr.number)
    if is_mine and not was_open:
        threads.start(m, pr.number)


def search_box(m) -> Box:
    """GitHub's search box for the PR list: type the query, Enter searches, ✕ goes back to the groups."""
    found: Optional[Search] = search.current(m)
    return Box(
        Input(
            search.typed(m),
            placeholder="Search PRs: is:pr author:… label:… review:…",
            on_change=lambda text: search.write(m, text),
            on_submit=lambda text: search.start(m, text),
        ),
        found is not None and Button("✕ Clear search", lambda: search.clear(m), dim=True),
    )


def search_results(m, found: Search, queued: dict, options, queue, width: int = 40) -> Box:
    """What a search found, as the same rows the groups use; a search never reaches the other lists."""
    if found.status == "running":
        return Text(f"… searching “{found.query}”", dim=True)
    if found.status == "error":
        return error_card(f"Search failed: {found.error}", copy=m.ui.copy, what="error",
                          actions=[Button("⟳ Retry", lambda: search.start(m, found.query))])
    mine = {p.number for p in (m.state.get("prs").mine if m.state.get("prs") else [])}
    return Box(
        Text(f"{len(found.prs)} result{'s' if len(found.prs) != 1 else ''} for “{found.query}”", dim=True),
        not found.prs and Text("No PR matches. Filters: " + search.EXAMPLES, dim=True, wrap=True),
        [pr_row(p, p.number in mine, queued, m, options, queue, width) for p in found.prs],
    )


def pr_row(pr: UIPullRequest, is_mine: bool, queued: dict, m=None, options=None, queue: Optional[Queue] = None,
           width: int = 40) -> Box:
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
        else Button(f"{'▾' if expanded else '▸'} #{pr.number} {pr.title}", lambda: open_pr_row(m, pr, is_mine, expanded))
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
        # Under the status line, for every PR: labels say what a PR is before it is opened.
        pr.labels and Text(", ".join(pr.labels), color="info", dim=True),
        entry and Text(f"   ⇢ in merge queue #{entry.position}" + (f" · {entry.eta_label}" if entry.eta_label else ""), color="info"),
        expanded and [
            is_mine and my_pr_detail(m, pr, options, queue, entry is not None, width),
            # Fixing a red check is the author's job, so only my own PRs get a diagnosis.
            is_mine and pr.checks_state == "failing" and diagnosis_of(m, pr, options, width),
            not is_mine and review_actions(m, pr, options, width),
        ],
    )


def fold(m, key: str, label: str, default_open: bool, *body):
    """A pressable title that shows its body only while open; remembers what the person chose."""
    chosen = m.state.get(key)
    is_open = default_open if chosen is None else chosen
    return Box(
        Button(f"{'▾' if is_open else '▸'} {label}", lambda: m.state.set(key, not is_open), dim=True),
        is_open and Box(*body, indent=2),
    )


RUN_ICON = {"running": ("●", "warning"), "success": ("✓", "success"), "failure": ("✗", "error"),
            "cancelled": ("⊘", "subtle"), "other": ("○", "subtle")}


def run_diagnosis_of(m, run: UIWorkflowRun) -> Box:
    """What the AI found for a failed run, once asked, in the shared error card; asking is in the run's Actions."""
    d: Optional[Diagnosis] = (m.state.get("diagnoses") or {}).get(run_key(run.id))
    if d is None or d.status == "running":
        return Box()
    if d.status == "error":
        return error_card(f"Could not diagnose: {d.error}", copy=m.ui.copy, what="error")
    heading = f"Run #{run.number} {run.title}" + (f" (PR #{run.pr_number})" if run.pr_number else "")
    reports = {j.job_name: format_diagnoses_report(heading, [j], d.model) for j in d.jobs}
    return Box(
        *[
            error_card(
                j.cause,
                copy=m.ui.copy,
                title=f"✗ {j.job_name}",
                details=[
                    *([f"at {j.where}"] if j.where else []),
                    *([f"“{j.quote}”"] if j.quote else []),
                    *(["⚠ this line is not in the log: do not trust the cause"] if j.quote and not j.is_quote_in_log else []),
                ],
                copy_text=reports[j.job_name],
                what="diagnosis",
                # The same report that is copied, handed to the user's AI CLI.
                actions=[fix_with_ai_button(m, reports[j.job_name])],
            )
            for j in d.jobs
        ],
        gap=1,
    )


def run_actions_card(m, run: UIWorkflowRun, options, width: int):
    """What can be done about a run: diagnose it, run it again (GitHub only takes a finished one) or open it."""
    in_flight = run_actions.running(m, run.id)
    if in_flight:
        return Text(f"… {run_actions.PROGRESS[in_flight]}", dim=True)
    label = f"#{run.number} {run.title}"
    finished = run.state != "running"
    d: Optional[Diagnosis] = (m.state.get("diagnoses") or {}).get(run_key(run.id))
    _, diagnose_text = diagnose_label(d)
    return choice_card(
        [
            run.state == "failure" and Option(diagnose_text, lambda: start_run_diagnosis(m, run.id, options)),
            run.state in ("failure", "cancelled") and Option(
                "⟳ Re-run failed jobs", lambda: run_actions.start(m, run.id, "rerun_failed", label)),
            finished and Option("⟳ Re-run all jobs", lambda: run_actions.start(m, run.id, "rerun_all", label)),
            Option("↗ Open on GitHub", lambda: webbrowser.open(run.url)) if run.url.startswith(("https://", "http://")) else None,
        ],
        width=width - ROW_INSET,
        title="Actions",
        hint="" if finished else "Running: it can be re-run once it ends",
    )


def run_row(m, run: UIWorkflowRun, options, width: int = 40) -> Box:
    """One workflow run: its state and what started it, and open, what to do about it."""
    key = f"run:{run.id}"
    expanded = row_open(m, key) or run_actions.running(m, run.id) is not None
    icon, tone = RUN_ICON[run.state]
    # A merge-queue run is told by its PR; any other by what triggered it and on which branch.
    where = f"PR #{run.pr_number}" if run.pr_number else f"{run.event} · {run.branch}" if run.branch else run.event
    return Box(
        Text(" "),
        Button(f"{'▾' if expanded else '▸'} {run.title}", lambda: toggle_row(m, key)),
        Text(
            Text(f"{icon} {run.state_label}", color=tone),
            Text(f" · {where}", dim=True),
            run.age and Text(f" · {run.age}", dim=True),
            run.duration and Text(f" · {run.duration}", dim=True),
        ),
        expanded and Box(
            run.state == "failure" and run_diagnosis_of(m, run),
            Text(" "),
            run_actions_card(m, run, options, width),
            indent=3,
        ),
    )


def runs_list(m, key: str, read: Optional[Runs], options, width: int = 40, empty: str = "No runs yet"):
    """The body of a list of runs: the rows, a way to read older ones, or why there are none.

    `key` is the state key the list is read into (and `refresh_<key>` its reread), so the
    repo's latest runs and the merge queue's share this and differ only in the read behind them.
    """
    if read is None:
        return Text("Loading…", dim=True)
    if read.error:
        return error_box(m, f"Could not read the runs: {read.error}", "runs error", retry=key)
    return Box(
        not read.runs and Text(empty, dim=True),
        [run_row(m, r, options, width) for r in read.runs],
        runs_reader.has_more(read) and Box(
            Text(" "),
            Button(f"▾ Show {runs_reader.PAGE} more", lambda: runs_reader.show_more(m, key), dim=True),
        ),
    )


def runs_fold(m, key: str, label: str, read: Optional[Runs], options, width: int = 40, empty: str = "No runs yet",
              default_open: Optional[bool] = None):
    """`runs_list` under a fold that keeps itself open or closed.

    Without `default_open` it starts closed until one of the latest runs is failing.
    """
    if default_open is None:
        default_open = read is not None and not read.error and any(r.state == "failure" for r in read.runs[:3])
    counted = read is not None and not read.error
    return fold(m, f"{key}_open", f"{label} ({len(read.runs)})" if counted else label,
                default_open, runs_list(m, key, read, options, width, empty))


def queue_row(e: UIMergeQueueEntry) -> Box:
    return Box(
        Text(" "),
        Text(Text(f"{e.position}. ", dim=True), pr_link(e.pr_number, e.url, "accent" if e.is_mine else "info"), f" {e.title}"),
        Text("   ", Text(f"@{e.author} · ", dim=True), Text(f"● {e.state_label}", color=QUEUE_TONE.get(e.state, "subtle")),
             e.checks_state in QUEUE_CHECKS and Text(f" · {QUEUE_CHECKS[e.checks_state][0]}", color=QUEUE_CHECKS[e.checks_state][1]),
             e.eta_label and Text(f" · {e.eta_label}", bold=True),
             e.queued_age and Text(f" · queued {e.queued_age}", dim=True)),
    )


def queue_fold(m, queue: Queue, runs: Optional[Runs] = None, options=None, width: int = 40):
    return fold(
        m, "queue_open",
        "Merge queue · unavailable" if queue.error else
        f"Merge queue · {queue.branch} ({queue.total})" + (f" · {queue.merge_method}" if queue.merge_method else "")
        + (f" · next {queue.next_eta}" if queue.next_eta and queue.entries else ""),
        bool(queue.entries or queue.error),
        queue.error and error_box(m, queue.error, "merge queue error", retry="queue"),
        not queue.error and queue.total == 0 and Text("Queue empty", dim=True),
        [queue_row(e) for e in queue.entries],
        queue.total > len(queue.entries) and Text(f"…and {queue.total - len(queue.entries)} more", dim=True),
        # What the queue has already run, passed or not: only its own runs (event merge_group).
        not queue.error and Text(" "),
        not queue.error and runs_fold(m, "queue_runs", "Queue runs", runs, options, width, "The queue has not run anything yet"),
    )


def others_fold(m, prs: Prs, read: Optional[Others], queued: dict, options, width: int = 40):
    """Everyone else's open PRs, read apart from yours: loading while that read is out."""
    if read is None:
        return fold(m, "others_open", "Other PRs · loading…", False)
    if read.error:
        return fold(m, "others_open", "Other PRs · unavailable", False,
                    error_box(m, f"Could not read the other PRs: {read.error}", retry="others"))
    known = {p.number for p in prs.to_review} | {p.number for p in prs.mine}
    others = [p for p in read.prs if p.number not in known]
    unlisted = prs.open_count - len(others) - len(known)
    return fold(m, "others_open", f"Other PRs ({len(others)})", False,
                not others and Text("Nothing else open", dim=True),
                [pr_row(p, False, queued, m, options, width=width) for p in others],
                unlisted > 0 and Text(f"…and {unlisted} more on GitHub", dim=True))


def draw(m, width: int, options=None, shown=None):
    options = options or {"diagnosis_jobs": 3}
    shown = shown or {"prs": True, "queue": True, "runs": True}
    if not any(shown.values()):
        return Text("Every section is switched off (Mods screen).", dim=True)
    prs: Optional[Prs] = m.state.get("prs") if shown["prs"] else None
    queue: Optional[Queue] = m.state.get("queue") if shown["queue"] else None
    runs: Optional[Runs] = m.state.get("runs") if shown.get("runs") else None
    if prs is None and queue is None and runs is None:
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
            parts.append(section(title, tone, error_box(m, f"Could not read PRs: {prs.error}", retry="prs")))
        else:
            found = search.current(m)
            parts.append(section(title, tone, Box(
                search_box(m),
                found is not None and search_results(m, found, queued, options, queue, width),
                # Empty groups start closed; each one keeps what the person last chose.
                found is None and fold(m, "review_open", f"Needs your review ({len(prs.to_review)})", bool(prs.to_review),
                     not prs.to_review and Text("Nothing pending", dim=True),
                     [pr_row(p, False, queued, m, options, width=width) for p in prs.to_review]),
                found is None and fold(m, "mine_open", f"Your PRs ({len(prs.mine)})", bool(prs.mine),
                     not prs.mine and Text("No open PRs", dim=True),
                     [pr_row(p, True, queued, m, options, queue, width) for p in prs.mine]),
                found is None and others_fold(m, prs, m.state.get("others"), queued, options, width),
                gap=1,
            )))
    if queue is not None and (queue.configured or queue.error):
        parts.append(section(Text("⇉ Merge queue", bold=True, color="info"), "info",
                             queue_fold(m, queue, m.state.get("queue_runs"), options, width)))
    if shown.get("runs"):
        # Closed until pressed: the fold's own line is the section's title.
        parts.append(Box(runs_fold(m, "runs", "▶ Workflow runs", runs, options, width, "No workflow runs",
                                   default_open=False), border="info"))
    return Box(*parts)
