"""The example dev_status mod: its reading and drawing are plain functions over fake clients."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from titan_cli.core.mods import AIAnswer, AIChoice, Box, Button, ModBus, Text
from titan_cli.core.result import ClientError, ClientSuccess

MOD = Path(__file__).resolve().parents[3] / "examples" / "mods" / "dev_status" / "mod.py"


@pytest.fixture(scope="module")
def dev():
    spec = importlib.util.spec_from_file_location("dev_status_under_test", MOD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def flatten(element):
    """Every string a tree would show, in order."""
    if isinstance(element, str):
        return [element]
    if isinstance(element, Text):
        return ["".join("".join(flatten(p)) for p in element.parts)]
    if isinstance(element, Button):
        return [element.label]
    if isinstance(element, Box):
        return [line for child in element.children for line in flatten(child)]
    return []


def write_harness(root, features):
    base = root / "harness"
    (base / "dom").mkdir(parents=True)
    (base / "feature-list.json").write_text(json.dumps({
        "currentFocus": "task-dom",
        "tasks": [
            {"id": "task-dom", "name": "Domain", "path": "dom", "status": "active"},
            {"id": "task-other", "name": "Other", "path": "other", "status": "active"},
            {"id": "task-old", "name": "Old", "path": "old", "status": "closed"},
        ],
    }))
    (base / "dom" / "feature-list.json").write_text(json.dumps({"features": [
        {"id": fid, "name": fid.upper(), "status": status} for fid, status in features
    ]}))


def test_split_pr_takes_the_squash_suffix(dev):
    assert dev.split_pr("fix: thing (#275)") == ("fix: thing", 275)
    assert dev.split_pr("fix: (#1) in the middle") == ("fix: (#1) in the middle", None)


def test_read_harness_counts_the_focused_domain(dev, tmp_path):
    write_harness(tmp_path, [("a", "done"), ("b", "in-progress"), ("c", "planned"), ("d", "superseded")])

    hs = dev.read_harness(tmp_path, "harness")

    assert (hs.name, hs.status, hs.done, hs.total) == ("Domain", "active", 1, 3)
    assert [f.id for f in hs.in_progress] == ["b"]
    assert [f.id for f in hs.up_next] == ["c"]
    assert hs.other_active == ["Other"]


def test_read_harness_without_one_is_none(dev, tmp_path):
    assert dev.read_harness(tmp_path, "harness") is None


def test_untracked_lines_reads_the_listed_files(dev, tmp_path):
    (tmp_path / "a.py").write_text("1\n2\n3\n")
    (tmp_path / "new").mkdir()
    (tmp_path / "new" / "b.py").write_text("x\ny")
    assert dev.untracked_lines(tmp_path, ["a.py", "new/b.py", "gone.py"]) == 5


def test_read_repo_combines_status_numstat_untracked_and_log(dev, tmp_path):
    (tmp_path / "new.txt").write_text("a\nb\n")
    git = SimpleNamespace(
        get_status=lambda: ClientSuccess(data=SimpleNamespace(branch="feat/x", has_upstream=True, ahead=2, behind=1, untracked_files=["ignored-dir/"])),
        get_uncommitted_numstat=lambda: ClientSuccess(data=[SimpleNamespace(additions=5, deletions=3)]),
        get_untracked_files=lambda: ClientSuccess(data=["new.txt"]),
        get_commits=lambda root, limit: ClientSuccess(data=[
            SimpleNamespace(short_hash="abc1234", message_subject="feat: y (#9)", formatted_date="2026-10-06"),
        ]),
    )

    repo = dev.read_repo(git, tmp_path, {"harness_dir": "harness", "recent_commits": 10})

    assert (repo.branch, repo.ahead, repo.behind, repo.added, repo.removed) == ("feat/x", 2, 1, 7, 3)
    assert repo.commits == [dev.Commit("abc1234", "feat: y", 9, "2026-10-06")]


def test_read_repo_without_git_says_so(dev, tmp_path):
    assert dev.read_repo(None, tmp_path, {"harness_dir": "harness"}).error == "git plugin not available"


def pr(number, review="review required", checks="passing", failed=0, draft=False, conflicts=False):
    return SimpleNamespace(
        number=number, title=f"PR {number}", author_name="ana", is_draft=draft, review_status_summary=review,
        checks_state=checks, has_conflicts=conflicts,
        failed_checks=[SimpleNamespace(name=f"job{i}", url=f"https://github.com/o/r/actions/runs/1/job/{i}") for i in range(failed)],
    )


def test_read_prs_and_the_error_path(dev):
    github = SimpleNamespace(
        list_pending_review_prs=lambda: ClientSuccess(data=[pr(1)]),
        list_my_prs=lambda: ClientSuccess(data=[pr(2), pr(3)]),
        list_all_prs=lambda max_results: ClientSuccess(data=[pr(1), pr(2), pr(3), pr(4)]),
    )
    prs = dev.read_prs(github, "o/r")
    assert ([p.number for p in prs.to_review], [p.number for p in prs.mine], prs.open_count, prs.repo) == ([1], [2, 3], 4, "o/r")

    github.list_my_prs = lambda: ClientError(error_message="gh: not logged in")
    assert dev.read_prs(github).error == "gh: not logged in"


def test_toasts_only_announce_changes_after_a_good_poll(dev):
    first = dev.Prs(to_review=[dev._pr(pr(1))])
    second = dev.Prs(to_review=[dev._pr(pr(1)), dev._pr(pr(5))])
    assert dev.new_review_requests(None, first) == []
    assert dev.new_review_requests(first, second) == [5]
    assert dev.new_review_requests(dev.Prs(error="down"), second) == []

    def entry(number, mine):
        return dev.QueueEntry(1, number, "t", "a", "queued", "QUEUED", "", mine)

    before = dev.Queue(configured=True, entries=[entry(7, True), entry(8, False)])
    after = dev.Queue(configured=True, entries=[])
    assert dev.left_queue(before, after) == [7]
    assert dev.left_queue(before, dev.Queue(error="down")) == []


def test_draw_shows_every_section(dev, tmp_path):
    bus = ModBus()
    bus.on_for("dev_status")
    m = bus._apis["dev_status"]
    write_harness(tmp_path, [("a", "done"), ("b", "in-progress")])
    m.state.set("repo", dev.Repo(branch="feat/x", has_upstream=True, ahead=1, added=4, commits=[dev.Commit("abc", "feat: y", 9, "today")],
                                 harness=dev.read_harness(tmp_path, "harness")))
    m.state.set("prs", dev.Prs(repo="o/r", to_review=[dev._pr(pr(5))],
                               mine=[dev._pr(pr(2, review="changes requested", checks="failing", failed=2, conflicts=True))],
                               open_count=3))
    m.state.set("queue", dev.Queue(configured=True, branch="master", total=1,
                                   entries=[dev.QueueEntry(1, 2, "PR 2", "ana", "running checks", "AWAITING_CHECKS", "~5m", True)]))

    lines = flatten(dev.draw(m, 44))

    assert lines[0] == "⎇ feat/x ↑1 ↓0 +4"
    assert "▸ #9 feat: y" in lines
    assert "◆ Domain active" in lines
    assert "▸ In progress (1)" in lines  # in progress starts closed, as in the Claude Code mod
    assert "⇄ Pull requests o/r · 3 open" in lines
    assert "▾ Needs your review (1)" in lines
    assert "@ana · ● awaiting review  ✓ checks" in lines
    assert "● changes requested  ✗ checks (2)  ⚠ conflicts" in lines
    assert "   ⇢ in merge queue #1 · ~5m" in lines
    assert "▾ Merge queue · master (1)" in lines


def test_a_branch_without_upstream_says_so(dev):
    bus = ModBus()
    bus.on_for("dev_status")
    m = bus._apis["dev_status"]
    m.state.set("repo", dev.Repo(branch="feat/x"))
    assert flatten(dev.draw(m, 44))[0] == "⎇ feat/x no upstream"


def test_pressing_a_group_flips_its_state(dev):
    bus = ModBus()
    bus.on_for("dev_status")
    m = bus._apis["dev_status"]
    features = [dev.Feature("a", "A", "planned")]

    closed = dev.group(m, "up_next_open", "Up next", features, False)
    assert flatten(closed) == ["▸ Up next (1)"]

    closed.children[0].on_press()
    assert flatten(dev.group(m, "up_next_open", "Up next", features, False)) == ["▾ Up next (1)", "○ a A"]


LOG = "\n".join(
    ["2026-10-06T10:00:00.0000000Z noise line"] * 400
    + ["2026-10-06T10:00:01.0000000Z > Task :app:testDebugUnitTest FAILED",
       "2026-10-06T10:00:01.0000000Z FooTest > bar FAILED at FooTest.kt:42"]
    + ["2026-10-06T10:00:02.0000000Z tail"] * 5
)


def test_excerpt_keeps_failures_and_the_tail_without_timestamps(dev):
    excerpt = dev.excerpt_of(LOG)
    assert "> Task :app:testDebugUnitTest FAILED" in excerpt
    assert "2026-10-06T" not in excerpt
    assert excerpt.count("noise line") < 400


def test_a_quote_that_is_not_in_the_log_is_flagged(dev):
    excerpt = dev.excerpt_of(LOG)
    real = dev.parse_diagnosis("test", '{"cause": "FooTest.bar fails", "where": "FooTest.kt:42", "quote": "FooTest > bar FAILED at FooTest.kt:42"}', excerpt)
    made_up = dev.parse_diagnosis("test", 'Sure! {"cause": "x", "quote": "NullPointerException in Bar"}', excerpt)
    prose = dev.parse_diagnosis("test", "The build failed because of a test.", excerpt)
    assert (real.where, real.is_quote_in_log) == ("FooTest.kt:42", True)
    assert made_up.is_quote_in_log is False
    assert prose.cause == "The build failed because of a test."


class DiagnosisHost:
    """Runs m.run inline and answers m.ai from a script, recording what it was asked."""

    def __init__(self, github, answer):
        self.github, self.answer, self.prompts = github, answer, []

    def status(self, mod, text): pass
    def toast(self, mod, text, severity): pass
    def open_pane(self, mod, pane, title): pass
    def repaint(self, mod): pass
    def every(self, mod, seconds, fn, immediately): pass
    def client(self, name): return self.github if name == "github" else None
    def run(self, mod, fn): fn()

    def ai(self, mod, prompt, system, max_tokens, model, timeout):
        self.prompts.append((prompt, model))
        return self.answer

    pinned = None
    choices = [AIChoice("remote:llm", "MasOrange LLM · qwen3-coder"), AIChoice("cli:claude", "Claude CLI · sonnet")]

    def ai_choices(self, mod): return self.choices
    def ai_pinned(self, mod): return self.pinned
    def ai_pin(self, mod, key): self.pinned = key
    def ai_describe(self, mod): return {None: "MasOrange LLM · qwen3-coder", "remote:llm": "MasOrange LLM · qwen3-coder", "cli:claude": "Claude CLI · sonnet"}[self.pinned]


def test_diagnose_reads_each_failed_job_and_asks_the_routed_model(dev, tmp_path, monkeypatch):
    monkeypatch.setattr("titan_cli.core.mods.store.STORE_DIR", tmp_path)
    logs = []
    github = SimpleNamespace(get_actions_job_log=lambda job_id: logs.append(job_id) or ClientSuccess(data=LOG))
    host = DiagnosisHost(github, AIAnswer(text='{"cause": "FooTest.bar fails", "quote": "FooTest > bar FAILED at FooTest.kt:42"}', model="m1"))
    bus = ModBus()
    bus.host = host
    bus.on_for("dev_status")
    m = bus._apis["dev_status"]
    m.state.set("prs", dev.Prs(mine=[dev._pr(pr(2, checks="failing", failed=4))]))

    dev.diagnose(m, 2, {"diagnosis_jobs": 3})

    d = m.state.get("diagnoses")["2"]
    assert d.status == "done"
    assert sorted(logs) == [0, 1, 2]  # three jobs at most, by the job id in each check's URL
    assert {model for _, model in host.prompts} == {None}  # the mod never forces a model: AI routing decides
    dev.refresh_ai_label(m)
    lines = flatten(dev.draw(m, 44, {"diagnosis_jobs": 3}))
    assert "✦ Diagnose again (last: m1)" in lines
    assert "FooTest.bar fails" in lines
    assert "…and 1 more failed checks" in lines
    assert "  ⟳ MasOrange LLM · qwen3-coder" in lines
    assert "    Titan's AI default · Enter/click to change" in lines


def test_diagnosis_failure_is_shown_not_raised(dev, tmp_path, monkeypatch):
    monkeypatch.setattr("titan_cli.core.mods.store.STORE_DIR", tmp_path)
    github = SimpleNamespace(get_actions_job_log=lambda job_id: ClientSuccess(data=LOG))
    bus = ModBus()
    bus.host = DiagnosisHost(github, AIAnswer(error="AI is turned off for this task."))
    bus.on_for("dev_status")
    m = bus._apis["dev_status"]
    m.state.set("prs", dev.Prs(mine=[dev._pr(pr(2, checks="failing", failed=1))]))

    dev.diagnose(m, 2, {"diagnosis_jobs": 3})

    assert m.state.get("diagnoses")["2"].error == "AI: AI is turned off for this task."


def test_ai_picker_cycles_default_then_each_real_choice_as_a_task_pin(dev):
    host = DiagnosisHost(None, AIAnswer())
    bus = ModBus()
    bus.host = host
    bus.on_for("dev_status")
    m = bus._apis["dev_status"]
    dev.refresh_ai_label(m)

    seen = []
    for _ in range(3):
        picker = dev.model_picker(m, {})
        _, button, how = picker.children
        seen.append((button.label, flatten(how)[0].split(" · ")[0].strip()))
        button.on_press()  # m.run is inline here, so the label is refreshed before the next look

    assert seen == [
        ("  ⟳ MasOrange LLM · qwen3-coder", "Titan's AI default"),
        ("  ⟳ MasOrange LLM · qwen3-coder", "pinned for this panel"),
        ("  ⟳ Claude CLI · sonnet", "pinned for this panel"),
    ]
    assert host.pinned is None  # third press wrapped around to AI routing's default
