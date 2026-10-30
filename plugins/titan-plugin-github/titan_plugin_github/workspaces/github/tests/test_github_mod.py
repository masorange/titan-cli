"""The github mod: its reading and drawing are plain functions over fake clients."""
from titan_plugin_github.readers import models
from types import SimpleNamespace

import pytest

from titan_cli.core.mods import AIAnswer, ModBus
from titan_cli.ui.components import AIResult, refresh_ai_chip
from titan_cli.ui.elements import Box, Button, Input
from titan_cli.core.result import ClientError, ClientSuccess
from titan_plugin_github.models.view import UIMergeQueueEntry


def test_draw_shows_every_section(mod, flatten, pr):
    bus = ModBus()
    m = bus.api("github")
    m.state.set("prs", models.Prs(repo="o/r", to_review=[pr(5)],
                               mine=[pr(2, review="changes requested", checks="failing", failed=2, conflicts=True)],
                               open_count=3))
    m.state.set("queue", models.Queue(configured=True, branch="master", total=1,
                                   entries=[UIMergeQueueEntry(1, 2, "PR 2", "ana", "AWAITING_CHECKS", "running checks", 300, "~5m", True)]))

    opts = {"diagnosis_jobs": 3, "review_workflow": "review-pr"}
    lines = flatten(mod.draw.draw(m, 44, opts))

    # Closed, a PR is its two lines: what it is, and where it stands.
    assert "▸ #5 PR 5" in lines
    assert not any("Approve" in line for line in lines)

    open_row(mod, m, 5, opts)
    lines = flatten(mod.draw.draw(m, 44, opts))
    pressed = labels(mod.draw.draw(m, 44, opts), flatten)
    assert "▾ #5 PR 5" in lines
    # In this order, one under the other, every label padded to one width.
    actions = ("Review", "✓ Approve", "✗ Request changes", "✎ Comment")
    assert [label for label in pressed if label in actions] == list(actions)
    assert len({len(line) for line in lines if line.strip() in actions}) == 1
    # The way to GitHub is one more action of the card, after the others.
    assert pressed.index("↗ Open on GitHub") == pressed.index("✎ Comment") + 1
    opened = []
    mod.draw.webbrowser.open = opened.append
    press(mod, m, "↗ Open on GitHub", opts)
    assert opened == ["https://github.com/o/r/pull/5"]
    assert "⇄ Pull requests o/r · 3 open  ⚠ 1 to review" in lines
    assert "▾ Needs your review (1)" in lines
    assert "@ana · ● awaiting review  ✓ checks" in lines
    assert "● changes requested  ✗ checks (2)  ⚠ conflicts" in lines
    assert "   ⇢ in merge queue #1 · ~5m" in lines
    assert "▾ Merge queue · master (1)" in lines


def test_review_runs_the_review_workflow_on_that_pr(mod, flatten, pr):
    runs = []
    bus = ModBus()
    bus.host = SimpleNamespace(repaint=lambda mod: None,
                               run_workflow=lambda mod, name, params: runs.append((mod, name, params)))
    m = bus.api("github")
    m.state.set("prs", models.Prs(to_review=[pr(5)]))

    open_row(mod, m, 5)
    press(mod, m, "Review")

    assert runs == [("github", "review-pr", {"review_pr_number": 5})]


def test_no_review_button_without_a_review_workflow(mod, flatten, pr):
    m = ModBus().api("github")
    m.state.set("prs", models.Prs(to_review=[pr(5)]))
    open_row(mod, m, 5, {"review_workflow": ""})
    lines = labels(mod.draw.draw(m, 44, {"review_workflow": ""}), flatten)
    assert "Review" not in lines
    assert "✓ Approve" in lines  # the GitHub actions do not need a workflow


def elements(element):
    yield element
    for child in (*getattr(element, "children", ()), *getattr(element, "parts", ())):
        yield from elements(child)


def buttons(element):
    return [e for e in elements(element) if isinstance(e, Button)]


def labels(element, flatten):
    """Every line a tree would show, without the padding that lines the buttons up."""
    return [line.strip() for line in flatten(element)]


def press(mod, m, label, opts=None):
    """Press the button with this label, as drawn now."""
    tree = mod.draw.draw(m, 44, opts or {"review_workflow": "review-pr"})
    next(b for b in buttons(tree) if b.label.strip() == label).on_press()


def open_row(mod, m, number, opts=None):
    """Press a PR's title line, which is its fold."""
    tree = mod.draw.draw(m, 44, opts or {"review_workflow": "review-pr"})
    next(b for b in buttons(tree) if b.label.startswith(("▸ #", "▾ #")) and f"#{number} " in b.label).on_press()


LOG = "\n".join(
    ["2026-10-06T10:00:00.0000000Z noise line"] * 400
    + ["2026-10-06T10:00:01.0000000Z > Task :app:testDebugUnitTest FAILED",
       "2026-10-06T10:00:01.0000000Z FooTest > bar FAILED at FooTest.kt:42"]
    + ["2026-10-06T10:00:02.0000000Z tail"] * 5
)


class DiagnosisHost:
    """Runs m.run inline and answers m.ai from a script, recording what it was asked."""

    def __init__(self, github, answer):
        self.github, self.answer, self.prompts, self.badges = github, answer, [], []

    def badge(self, mod, pane, text, severity): self.badges.append((pane, text))
    def toast(self, mod, text, severity): pass
    def open_pane(self, mod, pane, title): pass
    def repaint(self, mod): pass
    def every(self, mod, seconds, fn, immediately): pass
    def client(self, name): return self.github if name == "github" else None
    def run(self, mod, fn): fn()

    def ai(self, mod, prompt, system, max_tokens, model, timeout):
        self.prompts.append((prompt, model))
        return self.answer

    def ai_describe(self, mod): return "MasOrange LLM · qwen3-coder"


def test_diagnose_reads_each_failed_job_and_asks_the_routed_model(mod, tmp_path, monkeypatch, flatten, pr):
    monkeypatch.setattr("titan_cli.core.mods.store.STORE_DIR", tmp_path)
    logs = []
    github = SimpleNamespace(get_actions_job_log=lambda job_id: logs.append(job_id) or ClientSuccess(data=LOG))
    host = DiagnosisHost(github, AIAnswer(text='{"cause": "FooTest.bar fails", "quote": "FooTest > bar FAILED at FooTest.kt:42"}', model="m1"))
    bus = ModBus()
    bus.host = host
    m = bus.api("github")
    m.state.set("prs", models.Prs(mine=[pr(2, checks="failing", failed=4)]))

    mod.diagnosis.start_diagnosis(m, 2, {"diagnosis_jobs": 3})

    d = m.state.get("ai:pr:2")
    assert d.status == "done" and len(d.value) == 3
    assert sorted(logs) == [0, 1, 2]  # three jobs at most, by the job id in each check's URL
    assert {model for _, model in host.prompts} == {None}  # the mod never forces a model: AI routing decides
    refresh_ai_chip(m)
    open_row(mod, m, 2, {"diagnosis_jobs": 3})
    lines = flatten(mod.draw.draw(m, 44, {"diagnosis_jobs": 3}))
    assert "✦ Diagnose again (last: m1)" in lines
    assert "FooTest.bar fails" in lines
    assert "…and 1 more failed checks" in lines


def test_diagnosis_failure_is_shown_not_raised(mod, tmp_path, monkeypatch, pr):
    monkeypatch.setattr("titan_cli.core.mods.store.STORE_DIR", tmp_path)
    github = SimpleNamespace(get_actions_job_log=lambda job_id: ClientSuccess(data=LOG))
    bus = ModBus()
    bus.host = DiagnosisHost(github, AIAnswer(error="AI is turned off for this task."))
    m = bus.api("github")
    m.state.set("prs", models.Prs(mine=[pr(2, checks="failing", failed=1)]))

    mod.diagnosis.start_diagnosis(m, 2, {"diagnosis_jobs": 3})

    assert m.state.get("ai:pr:2").error == "AI: AI is turned off for this task."


def test_copy_puts_the_diagnosis_or_the_error_on_the_clipboard(mod, tmp_path, monkeypatch, flatten, pr):
    monkeypatch.setattr("titan_cli.core.mods.store.STORE_DIR", tmp_path)
    copied = []

    class CopyHost(DiagnosisHost):
        def copy(self, mod, text, what):
            copied.append((what, text))

    github = SimpleNamespace(get_actions_job_log=lambda job_id: ClientSuccess(data=LOG))
    bus = ModBus()
    bus.host = CopyHost(github, AIAnswer(text='{"cause": "FooTest.bar fails", "where": "FooTest.kt:42", "quote": "nope"}', model="m1"))
    m = bus.api("github")
    pr2 = pr(2, checks="failing", failed=1)
    m.state.set("prs", models.Prs(mine=[pr2]))

    assert not any("⧉" in line for line in flatten(mod.draw.diagnosis_of(m, pr2, {})))  # nothing to copy yet
    mod.diagnosis.start_diagnosis(m, 2, {"diagnosis_jobs": 3})
    copy = next(b for b in mod.draw.diagnosis_of(m, pr2, {}).children if isinstance(b, Button) and b.label.startswith("⧉"))
    copy.on_press()

    what, text = copied[0]
    assert (copy.label, what) == ("⧉ Copy diagnosis", "#2 diagnosis")
    assert text.splitlines()[:6] == ["PR #2 PR 2", "Diagnosed by m1", "", "✗ job0", "FooTest.bar fails", "at FooTest.kt:42"]
    assert "(this line is not in the log: do not trust the cause)" in text

    m.state.set("ai:pr:2", AIResult("error", error="AI: quota exhausted"))
    card = next(c for c in mod.draw.diagnosis_of(m, pr2, {}).children if isinstance(c, Box) and "⧉ Copy #2 error" in flatten(c))
    next(b for b in card.children[-1].children if isinstance(b, Button)).on_press()
    assert copied[-1] == ("#2 error", "PR #2 PR 2\nCould not diagnose: AI: quota exhausted\n")


def _state(mod, pr):
    m = ModBus().api("github")
    m.state.set("prs", models.Prs(repo="o/r", to_review=[pr(5)], open_count=1))
    m.state.set("queue", models.Queue(configured=True, branch="master", total=0, entries=[]))
    return m


def test_a_switched_off_section_is_not_drawn(mod, flatten, pr):
    m = _state(mod, pr)
    opts = {"review_workflow": "review-pr"}

    lines = flatten(mod.draw.draw(m, 44, opts, {"prs": True, "queue": False}))
    assert "▸ #5 PR 5" in lines and not any("Merge queue" in line for line in lines)

    lines = flatten(mod.draw.draw(m, 44, opts, {"prs": False, "queue": True}))
    assert "▸ #5 PR 5" not in lines
    assert "⇉ Merge queue" in lines and any(line.startswith(("▸ Merge queue", "▾ Merge queue")) for line in lines)


def test_all_sections_off_says_so(mod, flatten, pr):
    lines = flatten(mod.draw.draw(_state(mod, pr), 44, {}, {"prs": False, "queue": False}))

    assert lines == ["Every section is switched off (Mods screen)."]


def test_a_failed_queue_read_is_drawn_not_hidden(mod, flatten):
    m = ModBus().api("github")
    m.state.set("queue", models.Queue(error="GraphQL failed"))

    lines = flatten(mod.draw.draw(m, 44, {"diagnosis_jobs": 3}))

    assert "▾ Merge queue · unavailable" in lines or "▸ Merge queue · unavailable" in lines
    assert "GraphQL failed" in lines


def test_a_second_diagnosis_press_before_the_repaint_starts_nothing(mod, pr):
    runs = []
    bus = ModBus()
    bus.host = SimpleNamespace(repaint=lambda mod: None)
    m = bus.api("github")
    m.run = lambda fn: runs.append(fn)

    mod.diagnosis.start_diagnosis(m, 2, {"diagnosis_jobs": 3})
    mod.diagnosis.start_diagnosis(m, 2, {"diagnosis_jobs": 3})

    assert len(runs) == 1
    assert m.state.get("ai:pr:2").status == "running"


def _acting(mod, pr, github, toasts):
    """A pane showing one review request, over a github client that records what it is asked."""
    bus = ModBus()
    bus.host = SimpleNamespace(
        repaint=lambda mod: None,
        run=lambda mod, fn: fn(),  # the background thread, run here and now
        client=lambda name: github,
        toast=lambda mod, text, severity: toasts.append((text, severity)),
    )
    m = bus.api("github")
    m.state.set("prs", models.Prs(to_review=[pr(5)]))
    open_row(mod, m, 5)  # the buttons are under the PR's fold
    return m


def test_approve_submits_an_approval_and_rereads_the_prs(mod, pr):
    submitted, toasts, reread = [], [], []
    github = SimpleNamespace(
        submit_review=lambda number, review_id, event, body: submitted.append((number, review_id, event, body))
        or ClientSuccess(data=None),
    )
    m = _acting(mod, pr, github, toasts)
    m.state.set("refresh_prs", lambda: reread.append(True))

    press(mod, m, "✓ Approve")

    assert submitted == [(5, None, "APPROVE", "")]
    assert toasts == [("Approved #5", "information")]
    assert reread == [True]  # the row's review state is stale until the lists are read again
    assert mod.draw.actions.running(m, 5) is None


def test_comment_opens_a_field_and_accept_posts_it_as_a_general_comment(mod, flatten, pr):
    posted, toasts = [], []
    github = SimpleNamespace(
        add_issue_comment=lambda number, body: posted.append((number, body)) or ClientSuccess(data=None),
    )
    m = _acting(mod, pr, github, toasts)

    press(mod, m, "✎ Comment")
    assert "Comment on #5" in flatten(mod.draw.draw(m, 44, {"review_workflow": "review-pr"}))

    # The pane also has the search box: the comment field is the one that asks for a comment.
    field = next(e for e in elements(mod.draw.draw(m, 44, {"review_workflow": "review-pr"}))
                 if isinstance(e, Input) and e.placeholder == "Write a comment…")
    field.on_change("looks good to me")
    press(mod, m, "Accept")

    assert posted == [(5, "looks good to me")]
    assert toasts == [("Commented on #5", "information")]
    assert mod.draw.actions.composer(m) is None  # the field closes once it is sent


def test_cancel_closes_the_field_and_sends_nothing(mod, flatten, pr):
    posted, toasts = [], []
    github = SimpleNamespace(add_issue_comment=lambda number, body: posted.append((number, body)))
    m = _acting(mod, pr, github, toasts)

    press(mod, m, "✎ Comment")
    press(mod, m, "Cancel")

    assert posted == [] and toasts == []
    assert "✎ Comment" in labels(mod.draw.draw(m, 44, {"review_workflow": "review-pr"}), flatten)


def test_request_changes_submits_with_no_body(mod, flatten, pr):
    submitted, toasts = [], []
    github = SimpleNamespace(
        submit_review=lambda number, review_id, event, body: submitted.append((number, review_id, event, body))
        or ClientSuccess(data=None),
    )
    m = _acting(mod, pr, github, toasts)

    # One press is enough: no field, as the review-pr workflow submits it too.
    press(mod, m, "✗ Request changes")

    assert submitted == [(5, None, "REQUEST_CHANGES", "")]
    assert toasts == [("Changes requested on #5", "information")]
    assert mod.draw.actions.composer(m) is None


def test_an_empty_comment_sends_nothing(mod, pr):
    posted, toasts = [], []
    github = SimpleNamespace(add_issue_comment=lambda number, body: posted.append((number, body)))
    m = _acting(mod, pr, github, toasts)

    press(mod, m, "✎ Comment")
    press(mod, m, "Accept")

    assert posted == [] and toasts == [("Write something first", "warning")]


def test_a_failed_action_says_so_and_frees_the_pr(mod, pr):
    toasts = []
    github = SimpleNamespace(submit_review=lambda *a: ClientError(error_message="403 Forbidden"))
    m = _acting(mod, pr, github, toasts)

    press(mod, m, "✓ Approve")

    assert toasts == [("Could not approve #5: 403 Forbidden", "error")]
    assert mod.draw.actions.running(m, 5) is None  # pressing again is allowed


def reviewers(*specs):
    """UIReviewers as the github plugin maps them, from (login, state) pairs."""
    from titan_plugin_github.models.view import UIReviewer

    icons = {"approved": "✓", "changes_requested": "✗", "commented": "✎", "pending": "○"}
    return [UIReviewer(login=login, state=state, icon=icons[state], when="" if state == "pending" else "2d ago")
            for login, state in specs]


def test_my_pr_shows_who_is_reviewing_it_under_its_own_fold(mod, flatten, pr):
    m = ModBus().api("github")
    mine = pr(2, reviewers=reviewers(("ana", "approved"), ("bob", "changes_requested"), ("cat", "pending")),
              assignees=["ana"], labels=["bug", "App"])
    m.state.set("prs", models.Prs(mine=[mine]))
    opts = {"diagnosis_jobs": 3, "review_workflow": "review-pr"}

    open_row(mod, m, 2, opts)
    lines = labels(mod.draw.draw(m, 44, opts), flatten)

    # Two lines, four facts: what it lands on and its last touch, what it changes and its age.
    assert "feat/2 → develop ↻ 2h ago" in lines
    assert "+10 −2 · 3 files 5d ago" in lines
    assert "bug, App" in lines
    # The tally is in the fold's own title, so it shows without opening it.
    assert "▸ Reviewers ✗1 ✓1 ○1" in lines
    assert "▸ Assignees (1)" in lines
    assert "⟳ Re-request review (2)" in lines  # only the two who already reviewed
    assert not any("@ana · 2d ago" in line for line in lines)  # the names are behind the fold

    press(mod, m, "▸ Reviewers ✗1 ✓1 ○1", opts)
    lines = labels(mod.draw.draw(m, 44, opts), flatten)
    # In the order the plugin's mapper hands them over; the pane does not reorder.
    assert ["✓ @ana · 2d ago  ⟳", "✗ @bob · 2d ago  ⟳", "○ @cat"] == [
        line for line in lines if line.startswith(("✗ @", "✓ @", "○ @"))]


def test_re_request_asks_everyone_who_reviewed_or_just_one(mod, flatten, pr):
    asked, toasts = [], []
    github = SimpleNamespace(
        request_pr_review=lambda number, logins: asked.append((number, logins)) or ClientSuccess(data=None))
    bus = ModBus()
    bus.host = SimpleNamespace(repaint=lambda mod: None, run=lambda mod, fn: fn(),
                               client=lambda name: github,
                               toast=lambda mod, text, severity: toasts.append((text, severity)))
    m = bus.api("github")
    m.state.set("prs", models.Prs(mine=[pr(2, reviewers=reviewers(("ana", "approved"), ("cat", "pending")))]))
    opts = {"diagnosis_jobs": 3}
    open_row(mod, m, 2, opts)

    press(mod, m, "⟳ Re-request review (1)", opts)
    assert asked == [(2, None)]  # None = everyone who already reviewed
    assert toasts == [("Review requested again on #2", "information")]

    press(mod, m, "▸ Reviewers ✓1 ○1", opts)
    press(mod, m, "✓ @ana · 2d ago  ⟳", opts)
    assert asked[-1] == (2, ["ana"])
    assert toasts[-1] == ("Review requested again on #2 from @ana", "information")


def test_a_reviewer_still_pending_cannot_be_asked_again(mod, flatten, pr):
    m = ModBus().api("github")
    m.state.set("prs", models.Prs(mine=[pr(2, reviewers=reviewers(("cat", "pending")))]))
    opts = {"diagnosis_jobs": 3}
    open_row(mod, m, 2, opts)
    press(mod, m, "▸ Reviewers ○1", opts)

    tree = mod.draw.draw(m, 44, opts)
    # Nothing to repeat: the line is text, and there is no button to ask them all again either.
    assert not any("@cat" in b.label for b in buttons(tree))
    assert not any("Re-request" in b.label for b in buttons(tree))


def test_conflicts_are_asked_of_git_when_the_fold_is_opened(mod, flatten, pr):
    asked, fetched = [], []
    git = SimpleNamespace(
        fetch=lambda remote, branch: fetched.append((remote, branch)),
        list_merge_conflicts=lambda base, head: asked.append((base, head)) or ClientSuccess(
            data=["app/Home.kt", "gradle/libs.versions.toml"]),
    )
    bus = ModBus()
    bus.host = SimpleNamespace(repaint=lambda mod: None, run=lambda mod, fn: fn(),
                               client=lambda name: git if name == "git" else None)
    m = bus.api("github")
    mine = pr(2, conflicts=True)
    mine.base_ref, mine.head_ref = "develop", "feat/2"
    m.state.set("prs", models.Prs(mine=[mine]))
    opts = {"diagnosis_jobs": 3, "conflicts_workflow": "resolve-pr-conflicts"}

    open_row(mod, m, 2, opts)
    # Closed, git has not been asked: the fetch it needs is not worth a poll.
    assert "▸ ⚠ Conflicts" in labels(mod.draw.draw(m, 44, opts), flatten)
    assert asked == []

    press(mod, m, "▸ ⚠ Conflicts", opts)
    lines = labels(mod.draw.draw(m, 44, opts), flatten)

    assert fetched == [("origin", "develop"), ("origin", "feat/2")]
    assert asked == [("origin/develop", "origin/feat/2")]
    assert "▾ ⚠ Conflicts (2)" in lines
    assert "app/Home.kt" in lines and "gradle/libs.versions.toml" in lines
    assert "⚒ Resolve conflicts" in lines


def test_resolve_conflicts_runs_the_workflow_on_that_pr(mod, flatten, pr):
    runs = []
    git = SimpleNamespace(fetch=lambda remote, branch: None,
                          list_merge_conflicts=lambda base, head: ClientSuccess(data=["a.kt"]))
    bus = ModBus()
    bus.host = SimpleNamespace(repaint=lambda mod: None, run=lambda mod, fn: fn(),
                               client=lambda name: git if name == "git" else None,
                               run_workflow=lambda mod, name, params: runs.append((name, params)))
    m = bus.api("github")
    mine = pr(2, conflicts=True)
    mine.base_ref, mine.head_ref = "develop", "feat/2"
    m.state.set("prs", models.Prs(mine=[mine]))
    opts = {"diagnosis_jobs": 3, "conflicts_workflow": "resolve-pr-conflicts"}

    open_row(mod, m, 2, opts)
    press(mod, m, "▸ ⚠ Conflicts", opts)
    press(mod, m, "⚒ Resolve conflicts", opts)

    assert runs == [("resolve-pr-conflicts", {"conflict_pr_number": 2})]


def test_without_the_git_plugin_the_fold_says_so(mod, flatten, pr):
    bus = ModBus()
    bus.host = SimpleNamespace(repaint=lambda mod: None, run=lambda mod, fn: fn(),
                               client=lambda name: None)
    m = bus.api("github")
    mine = pr(2, conflicts=True)
    mine.base_ref, mine.head_ref = "develop", "feat/2"
    m.state.set("prs", models.Prs(mine=[mine]))
    opts = {"diagnosis_jobs": 3, "conflicts_workflow": "resolve-pr-conflicts"}

    open_row(mod, m, 2, opts)
    press(mod, m, "▸ ⚠ Conflicts", opts)

    assert "Could not tell: the git plugin is not enabled" in labels(mod.draw.draw(m, 44, opts), flatten)


def test_fix_with_ai_hands_the_diagnosis_to_the_workflow(mod, tmp_path, monkeypatch, flatten, pr):
    monkeypatch.setattr("titan_cli.core.mods.store.STORE_DIR", tmp_path)
    runs = []
    github = SimpleNamespace(get_actions_job_log=lambda job_id: ClientSuccess(data=LOG))

    class RunHost(DiagnosisHost):
        def run_workflow(self, mod, name, params):
            runs.append((name, params))

    bus = ModBus()
    bus.host = RunHost(github, AIAnswer(text='{"cause": "FooTest.bar fails", "quote": "nope"}', model="m1"))
    m = bus.api("github")
    mine = pr(2, checks="failing", failed=1)
    m.state.set("prs", models.Prs(mine=[mine]))
    opts = {"diagnosis_jobs": 3, "checks_workflow": "fix-pr-checks"}

    open_row(mod, m, 2, opts)
    # Before any diagnosis the button is already there: the workflow reads the logs itself.
    press(mod, m, "✦ Fix with AI", opts)
    assert runs == [("fix-pr-checks", {"fix_pr_number": 2, "check_diagnosis": ""})]

    mod.diagnosis.start_diagnosis(m, 2, opts)
    press(mod, m, "✦ Fix with AI", opts)

    name, params = runs[-1]
    assert name == "fix-pr-checks" and params["fix_pr_number"] == 2
    assert "FooTest.bar fails" in params["check_diagnosis"]  # what the pane found travels with it


def test_no_fix_button_without_a_workflow(mod, flatten, pr):
    m = ModBus().api("github")
    m.state.set("prs", models.Prs(mine=[pr(2, checks="failing", failed=1)]))
    opts = {"diagnosis_jobs": 3, "checks_workflow": ""}

    open_row(mod, m, 2, opts)

    assert "✦ Fix with AI" not in labels(mod.draw.draw(m, 44, opts), flatten)


def test_other_prs_load_apart_and_drop_the_ones_already_listed(mod, flatten, pr):
    m = ModBus().api("github")
    m.state.set("prs", models.Prs(to_review=[pr(5)], mine=[pr(2)], open_count=7))
    opts = {"review_workflow": "review-pr"}

    # Your PRs are drawn while the other read is still out.
    lines = labels(mod.draw.draw(m, 44, opts), flatten)
    assert "▸ Other PRs · loading…" in lines
    assert "▸ #2 PR 2" in lines

    m.state.set("others", models.Others(prs=[pr(2), pr(5), pr(8), pr(9)]))
    lines = labels(mod.draw.draw(m, 44, opts), flatten)
    assert "▸ Other PRs (2)" in lines and "▸ #8 PR 8" not in lines

    press(mod, m, "▸ Other PRs (2)", opts)
    lines = labels(mod.draw.draw(m, 44, opts), flatten)
    assert "▸ #8 PR 8" in lines and "▸ #9 PR 9" in lines
    assert "…and 3 more on GitHub" in lines  # 7 open, 4 listed


def test_a_failed_read_of_the_other_prs_does_not_touch_yours(mod, flatten, pr):
    m = ModBus().api("github")
    m.state.set("prs", models.Prs(mine=[pr(2)], open_count=1))
    m.state.set("others", models.Others(error="i/o timeout"))
    opts = {"review_workflow": "review-pr"}

    assert "▸ Other PRs · unavailable" in labels(mod.draw.draw(m, 44, opts), flatten)
    press(mod, m, "▸ Other PRs · unavailable", opts)
    lines = labels(mod.draw.draw(m, 44, opts), flatten)
    assert "Could not read the other PRs: i/o timeout" in lines
    assert "▸ #2 PR 2" in lines


def test_merge_blockers_say_why_and_no_button_shows(mod, pr):
    blockers = mod.sections.prs.merge.blockers
    assert blockers(pr(1, review="approved")) == []
    assert blockers(pr(1, review="approved", checks="none")) == []
    assert blockers(pr(1, draft=True, conflicts=True, checks="failing")) == [
        "still a draft", "has conflicts", "not approved", "checks failing"]
    assert blockers(pr(1, review="changes requested", checks="running")) == ["changes requested", "checks running"]


def test_my_pr_that_cannot_merge_says_why(mod, flatten, pr):
    m = ModBus().api("github")
    m.state.set("prs", models.Prs(mine=[pr(2, checks="failing")]))
    open_row(mod, m, 2)

    tree = mod.draw.draw(m, 44, {})
    assert "Not ready to merge: not approved, checks failing" in labels(tree, flatten)
    assert not any("merge" in b.label.lower() and "⇉" in b.label for b in buttons(tree))


def _mergeable(mod, pr, github, toasts, queue=None):
    m = _acting(mod, pr, github, toasts)
    m.state.set("prs", models.Prs(mine=[pr(2, review="approved")]))
    if queue is not None:
        m.state.set("queue", queue)
    open_row(mod, m, 2)
    return m


def test_merge_asks_twice_then_squashes_and_rereads(mod, pr):
    merged, toasts, reread = [], [], []
    github = SimpleNamespace(
        merge_pr=lambda number: merged.append(number) or ClientSuccess(
            data=SimpleNamespace(merged=True, queued=False, message="merged")),
    )
    m = _mergeable(mod, pr, github, toasts)
    m.state.set("refresh_prs", lambda: reread.append(True))

    press(mod, m, "⇉ Squash & merge")
    assert merged == []  # the first press only asks
    press(mod, m, "✗ Cancel")
    assert merged == [] and mod.draw.actions.merge_pending(m) is None

    press(mod, m, "⇉ Squash & merge")
    press(mod, m, "✓ Confirm")

    assert merged == [2]
    assert toasts == [("Merged #2", "information")]
    assert reread == [True]


def test_merge_button_joins_the_queue_when_the_branch_has_one(mod, flatten, pr):
    toasts = []
    github = SimpleNamespace(
        merge_pr=lambda number: ClientSuccess(data=SimpleNamespace(merged=False, queued=True, message="Added to the merge queue")),
    )
    queue = models.Queue(configured=True, branch="develop", total=0)
    m = _mergeable(mod, pr, github, toasts, queue)

    press(mod, m, "⇉ Add to queue")
    assert "Sure? This will join the merge queue." in labels(mod.draw.draw(m, 44, {}), flatten)
    press(mod, m, "✓ Confirm")

    assert toasts == [("#2: Added to the merge queue", "information")]


def test_a_queue_of_another_branch_does_not_change_the_label(mod, pr):
    queue = models.Queue(configured=True, branch="master")
    assert mod.sections.prs.merge.label(pr(2), queue) == "⇉ Squash & merge"
    assert mod.sections.prs.merge.label(pr(2), None) == "⇉ Squash & merge"


def test_a_refused_merge_says_why(mod, pr):
    toasts = []
    github = SimpleNamespace(
        merge_pr=lambda number: ClientSuccess(data=SimpleNamespace(merged=False, queued=False, message="not mergeable")),
    )
    m = _mergeable(mod, pr, github, toasts)

    press(mod, m, "⇉ Squash & merge")
    press(mod, m, "✓ Confirm")

    assert toasts == [("Could not merge #2: not mergeable", "error")]
    assert mod.draw.actions.running(m, 2) is None


def test_a_failed_pr_read_can_be_copied_whole(mod, flatten):
    copied = []
    bus = ModBus()
    bus.host = SimpleNamespace(repaint=lambda mod: None, copy=lambda mod, text, what: copied.append((text, what)))
    m = bus.api("github")
    m.state.set("prs", models.Prs(error='GitHub API error: Post "https://api.github.com/graphql": EOF'))

    tree = mod.draw.draw(m, 44, {})
    next(b for b in buttons(tree) if b.label == "⧉ Copy error").on_press()

    assert copied == [('Could not read PRs: GitHub API error: Post "https://api.github.com/graphql": EOF', "error")]


def _my_pr_pane(mod, pr, slack_on, runs):
    bus = ModBus()
    # Opening a row reads its conversations in the background: no client here, so that read fails quietly.
    bus.host = SimpleNamespace(repaint=lambda mod: None, run=lambda mod, fn: fn(), client=lambda name: None,
                               run_workflow=lambda mod, name, params: runs.append((name, params)))
    m = bus.api("github")
    m.state.set("prs", models.Prs(mine=[pr(2, review="approved")]))
    m.state.set("slack_on", slack_on)
    open_row(mod, m, 2)
    return m


NOTIFY = {"notify_workflow": "plugin:slack/post-message", "notify_message": "Merging [#{number} {title}]({url})"}


def test_notify_channel_runs_the_slack_workflow_with_the_prs_message(mod, pr):
    runs = []
    m = _my_pr_pane(mod, pr, True, runs)

    press(mod, m, "✉ Notify channel", NOTIFY)

    assert runs == [("plugin:slack/post-message",
                     {"slack_message_markdown": "Merging [#2 PR 2](https://github.com/o/r/pull/2)"})]


def test_no_notify_button_without_slack_or_without_a_workflow(mod, flatten, pr):
    m = _my_pr_pane(mod, pr, False, [])
    assert "✉ Notify channel" not in labels(mod.draw.draw(m, 44, NOTIFY), flatten)

    m = _my_pr_pane(mod, pr, True, [])
    assert "✉ Notify channel" not in labels(mod.draw.draw(m, 44, {**NOTIFY, "notify_workflow": ""}), flatten)


def test_no_notify_button_while_the_pr_cannot_be_merged(mod, flatten, pr):
    m = _my_pr_pane(mod, pr, True, [])
    m.state.set("prs", models.Prs(mine=[pr(2, review="review required")]))

    assert "✉ Notify channel" not in labels(mod.draw.draw(m, 44, NOTIFY), flatten)


def test_my_pr_actions_are_one_group_of_one_width(mod, flatten, pr):
    m = _my_pr_pane(mod, pr, True, [])
    m.state.set("prs", models.Prs(mine=[pr(2, review="approved", reviewers=reviewers(("ana", "approved")))]))

    lines = flatten(mod.draw.draw(m, 44, NOTIFY))

    group = [line for line in lines if line.strip() in ("⇉ Squash & merge", "✉ Notify channel", "⟳ Re-request review (1)")]
    assert len(group) == 3 and len({len(line) for line in group}) == 1
    assert [line.strip() for line in lines].index("Actions") < [line.strip() for line in lines].index("⇉ Squash & merge")


def test_a_failed_pr_read_can_be_retried(mod, flatten):
    reread, ran = [], []
    bus = ModBus()
    bus.host = SimpleNamespace(repaint=lambda mod: None, run=lambda mod, fn: (ran.append(True), fn()))
    m = bus.api("github")
    m.state.set("prs", models.Prs(error="i/o timeout"))
    m.state.set("refresh_prs", lambda: reread.append(True))

    press(mod, m, "⟳ Retry", {})

    assert reread == [True] and ran == [True]
    assert not m.state.get("retrying:prs")  # free to press again once the read ends


def test_no_retry_button_before_the_mod_has_started(mod, flatten):
    m = ModBus().api("github")
    m.state.set("prs", models.Prs(error="i/o timeout"))
    assert "⟳ Retry" not in labels(mod.draw.draw(m, 44, {}), flatten)


def test_a_pr_with_open_conversations_says_so_and_offers_no_merge(mod, flatten, pr):
    m = ModBus().api("github")
    m.state.set("prs", models.Prs(mine=[pr(2, review="ready for review")]))
    m.state.set("threads", {"2": models.Threads("done", unresolved=2)})
    open_row(mod, m, 2, {})

    lines = labels(mod.draw.draw(m, 44, {}), flatten)

    assert "Not ready to merge: 2 unresolved conversations" in lines
    assert not any("Squash" in line or "queue" in line.lower() and "Add" in line for line in lines)


def test_opening_one_of_my_rows_asks_github_for_its_conversations(mod, pr):
    m = ModBus().api("github")
    asked = []
    m.run = lambda fn: None
    m.state.set("prs", models.Prs(mine=[pr(2)], to_review=[pr(5)]))

    mod.draw.open_pr_row(m, pr(2), True, False)
    mod.draw.open_pr_row(m, pr(5), False, False)

    assert (m.state.get("threads") or {}).keys() == {"2"}
    assert asked == []


OPTIONS = {"prs_refresh_seconds": 120, "queue_refresh_seconds": 60, "runs_refresh_seconds": 30, "refresh_key": "", "queue_shown": 8}


def _workspace(mod, **host_fns):
    """The workspace registered on a bus of its own kind, with a host that records what it is asked."""
    bus = ModBus(prefix="workspace.", store_dir="workspaces")
    calls = SimpleNamespace(runs=[], ticks=[], keys={})
    host = SimpleNamespace(
        dock=lambda *a: None, repaint=lambda mod: None, toast=lambda *a: None,
        every=lambda mod, seconds, fn, immediately: calls.ticks.append(fn),
        run=lambda mod, fn: calls.runs.append(fn), client=lambda name: None,
        bind_key=lambda mod, key, description, fn: calls.keys.setdefault(key, (description, fn)) and None,
    )
    for name, fn in host_fns.items():
        setattr(host, name, fn)
    bus.host = host
    return bus, calls


def _register(mod, bus, **options):
    mod.register(bus.api("github"), bus.on_for("github"), {**OPTIONS, **options})


def test_the_refresh_key_is_bound_at_start_and_refreshes_every_section(mod):
    bus, calls = _workspace(mod)
    _register(mod, bus, refresh_key="f6")
    assert calls.keys == {}  # nothing before Titan's interface is up

    bus.start()
    assert list(calls.keys) == ["f6"] and calls.keys["f6"][0] == "Refresh status"

    calls.runs.clear()
    calls.keys["f6"][1]()
    assert len(calls.runs) == 1  # the refresh goes off the UI thread
    calls.runs[0]()
    state = bus.api("github").state
    assert state.get("prs") is not None and state.get("queue") is not None


def test_a_finished_or_aborted_workflow_refreshes_everything_off_its_thread(mod):
    from titan_cli.core.mods import WorkflowRun

    bus, calls = _workspace(mod)
    _register(mod, bus)
    state = bus.api("github").state

    bus.dispatch("workflow.run", WorkflowRun("review-pr", "plugin", nested=False), lambda e: None)
    assert calls.runs == []  # nothing to refresh before the workspace has started

    bus.start()
    calls.runs.clear()
    bus.dispatch("workflow.run", WorkflowRun("review-pr", "plugin", nested=True), lambda e: None)
    assert calls.runs == [] and state.get("prs") is None  # a nested workflow is part of its parent

    bus.dispatch("workflow.run", WorkflowRun("review-pr", "plugin", nested=False), lambda e: None)
    assert state.get("prs") is None  # not on the workflow's thread
    calls.runs[-1]()
    assert state.get("prs") is not None and state.get("queue") is not None

    calls.runs.clear()

    def aborted(e):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        bus.dispatch("workflow.run", WorkflowRun("review-pr", "plugin", nested=False), aborted)
    assert len(calls.runs) == 1  # an aborted run refreshes too


def test_a_section_turned_on_while_running_refreshes_at_once_and_off_ones_do_not_poll(mod):
    bus, calls = _workspace(mod)
    sections = {"prs": False, "queue": True}
    _register(mod, bus, sections=sections)
    bus.start()
    state = bus.api("github").state

    for tick in calls.ticks:
        tick()
    assert state.get("prs") is None and state.get("queue") is not None

    bus.sections["github"] = sections
    calls.runs.clear()
    bus.set_section("github", "prs", True)
    assert len(calls.runs) == 2  # your PRs and, apart, everyone else's
    for run in calls.runs:
        run()
    assert state.get("prs") is not None and state.get("others") is not None


def test_the_dock_tile_and_the_refresh_timers_wait_for_start(mod):
    docked = []
    bus, calls = _workspace(mod, dock=lambda mod, slot: docked.append((mod, slot.label)))
    _register(mod, bus)
    assert docked == [] and calls.ticks == []

    bus.start()
    assert docked == [("workspace.github", "GitHub")] and len(calls.ticks) == 5
