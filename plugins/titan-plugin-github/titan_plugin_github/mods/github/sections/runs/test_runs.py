"""Reading workflow runs and drawing them: the same list for the repo and for the merge queue."""
from types import SimpleNamespace

from titan_cli.core.mods import AIAnswer, ModBus
from titan_cli.core.result import ClientError, ClientSuccess
from titan_plugin_github.models.view import UIFailedCheck, UIWorkflowRun


def run(run_id, state="failure", **kw):
    return UIWorkflowRun(id=run_id, title=f"run {run_id}", workflow="build", event="pull_request", state=state,
                         state_label={"failure": "failed", "success": "passed", "running": "in progress"}[state],
                         branch="feat/x", url=f"https://github.com/o/r/actions/runs/{run_id}", number=run_id, **kw)


def test_read_runs_asks_for_the_limit_and_the_event(mod):
    asked = []
    github = SimpleNamespace(list_workflow_runs=lambda trigger, limit: asked.append((trigger, limit)) or ClientSuccess(data=[run(1)]))

    read = mod.sections.runs.runs.read_runs(github, "merge_group", 20)

    assert asked == [("merge_group", 20)] and read.limit == 20 and read.error is None


def test_a_failed_runs_read_keeps_the_limit_and_says_why(mod):
    github = SimpleNamespace(list_workflow_runs=lambda trigger, limit: ClientError(error_message="HTTP 403"))

    read = mod.sections.runs.runs.read_runs(github, None, 30)

    assert read.error == "HTTP 403" and read.limit == 30 and read.runs == []


def test_show_more_is_offered_only_while_a_full_page_came_back(mod):
    runs = mod.sections.runs.runs
    full = mod.models.Runs(runs=[run(i) for i in range(10)], limit=10)

    assert runs.has_more(full)
    assert not runs.has_more(mod.models.Runs(runs=[run(1)], limit=10))
    assert not runs.has_more(mod.models.Runs(runs=[run(i) for i in range(100)], limit=100))


def test_show_more_raises_the_limit_by_a_page_and_reads_again(mod):
    m = ModBus().api("github")
    m.state.set("runs", mod.models.Runs(runs=[run(1)], limit=10))
    reread = []
    m.state.set("refresh_runs", lambda: reread.append(True))
    m.run = lambda fn: fn()

    mod.sections.runs.runs.show_more(m, "runs")

    assert m.state.get("runs").limit == 20 and reread == [True]


def test_a_failed_run_offers_diagnosis_and_both_reruns(mod, flatten):
    m = ModBus().api("github")
    row = mod.draw.run_row(m, run(1), {"diagnosis_jobs": 3})
    mod.draw.toggle_row(m, "run:1")

    lines = flatten(mod.draw.run_row(m, run(1), {"diagnosis_jobs": 3}))

    text = "\n".join(lines)
    assert "Diagnose failure" in text and "Re-run failed jobs" in text and "Re-run all jobs" in text
    assert row is not None


def test_a_running_run_cannot_be_rerun_yet(mod, flatten):
    m = ModBus().api("github")
    mod.draw.toggle_row(m, "run:2")

    lines = flatten(mod.draw.run_row(m, run(2, "running"), {"diagnosis_jobs": 3}))

    assert not any("Re-run" in line for line in lines)
    assert "Running: it can be re-run once it ends" in lines


def test_a_passed_run_can_only_be_rerun_whole(mod, flatten):
    m = ModBus().api("github")
    mod.draw.toggle_row(m, "run:3")

    lines = flatten(mod.draw.run_row(m, run(3, "success"), {"diagnosis_jobs": 3}))

    text = "\n".join(lines)
    assert "Re-run all jobs" in text and "Re-run failed jobs" not in text
    assert "Diagnose failure" not in text


def test_a_queue_run_is_told_by_its_pr(mod, flatten):
    m = ModBus().api("github")
    queued = run(4, is_merge_queue=True, pr_number=3783)

    lines = flatten(mod.draw.run_row(m, queued, {}))

    assert any("PR #3783" in line for line in lines)


def test_the_queue_lists_its_own_runs_under_a_fold(mod, flatten):
    m = ModBus().api("github")
    queue = mod.models.Queue(configured=True, branch="develop", total=0)
    m.state.set("queue_open", True)
    m.state.set("queue_runs_open", True)

    lines = flatten(mod.draw.queue_fold(m, queue, mod.models.Runs(runs=[run(5)], limit=10), {}))

    assert "▾ Queue runs (1)" in lines
    assert any(line.strip() == "▸ run 5" for line in lines)


def test_diagnosing_a_run_reads_its_failed_jobs_and_keeps_the_result_under_the_runs_key(mod, flatten):
    logs = []
    github = SimpleNamespace(
        get_run_failed_jobs=lambda run_id: ClientSuccess(data=[UIFailedCheck("unit", "u", job_id=11, run_id=run_id)]),
        get_actions_job_log=lambda job_id: logs.append(job_id) or ClientSuccess(data="FooTest > bar FAILED at FooTest.kt:42"),
    )
    host = SimpleNamespace(
        client=lambda name: github, run=lambda mod_, fn: fn(), repaint=lambda mod_: None,
        ai=lambda mod_, prompt, system, max_tokens, model, timeout: AIAnswer(
            text='{"cause": "bar fails", "quote": "FooTest > bar FAILED at FooTest.kt:42"}', model="m1"),
        ai_describe=lambda mod_: "m1",
    )
    bus = ModBus()
    bus.host = host
    m = bus.api("github")

    mod.diagnosis.start_run_diagnosis(m, 9, {"diagnosis_jobs": 3})

    d = m.state.get("diagnoses")[mod.diagnosis.run_key(9)]
    assert d.status == "done" and d.jobs[0].cause == "bar fails" and logs == [11]

    m.state.set("diagnoses", {mod.diagnosis.run_key(run(9).id): d})
    card = flatten(mod.draw.run_diagnosis_of(m, run(9)))
    assert "✗ unit" in card and "bar fails" in card and "⧉ Copy diagnosis" in card


def test_a_failed_diagnosis_is_the_shared_error_card_with_a_copy_button(mod, flatten):
    m = ModBus().api("github")
    m.state.set("diagnoses", {mod.diagnosis.run_key(1): mod.diagnosis.Diagnosis("error", error="AI is off")})

    lines = flatten(mod.draw.run_diagnosis_of(m, run(1)))

    assert "Could not diagnose: AI is off" in lines and "⧉ Copy error" in lines


def test_the_run_actions_no_longer_carry_a_copy_button(mod, flatten):
    m = ModBus().api("github")
    m.state.set("diagnoses", {mod.diagnosis.run_key(1): mod.diagnosis.Diagnosis("done")})
    mod.draw.toggle_row(m, "run:1")

    text = "\n".join(flatten(mod.draw.run_row(m, run(1), {})))

    assert "Diagnose again" in text and text.count("Copy") == 0


def test_the_workflow_runs_section_starts_closed_and_opens_with_every_run_listed(mod, flatten):
    m = ModBus().api("github")
    m.state.set("runs", mod.models.Runs(runs=[run(i, "success") for i in range(1, 11)], limit=10))
    shown = {"prs": False, "queue": False, "runs": True}

    closed = flatten(mod.draw.draw(m, 44, {}, shown))
    assert "▸ ▶ Workflow runs (10)" in closed and not any("run 1" in line for line in closed)

    m.state.set("runs_open", True)
    opened = flatten(mod.draw.draw(m, 44, {}, shown))
    assert "▾ ▶ Workflow runs (10)" in opened
    assert sum(1 for line in opened if line.strip().endswith(tuple(f"run {i}" for i in range(1, 11)))) == 10
