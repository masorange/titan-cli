"""Why a check of one of the user's PRs failed: its log, read by the AI the user routed this mod to.

Cutting the log, the prompt, reading the answer and the report are the github
plugin's (`ci_diagnosis_operations`); this file runs them over the PR's failed
checks with the mod's AI routing and keeps the result in `m.state`.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional, Tuple

from titan_cli.core.result import ClientError, ClientSuccess
from titan_plugin_github.models.view import UIFailedCheck, UIJobDiagnosis, UIPullRequest
from titan_plugin_github.operations import (
    build_job_diagnosis_prompt,
    extract_failure_excerpt,
    format_job_diagnoses,
    parse_job_diagnosis,
)

from .models import Prs


@dataclass(frozen=True)
class Diagnosis:
    status: str  # "running", "done" or "error"
    model: Optional[str] = None
    jobs: Tuple[UIJobDiagnosis, ...] = ()
    error: Optional[str] = None


def diagnose_job(m, github, check: UIFailedCheck) -> Tuple[UIJobDiagnosis, Optional[str]]:
    """The diagnosis of one failed job, and the model that answered."""
    if check.job_id is None:
        return UIJobDiagnosis(check.name, "Not a GitHub Actions job: its log is outside GitHub."), None
    match github.get_actions_job_log(check.job_id):
        case ClientSuccess(data=log):
            pass
        case ClientError(error_message=err):
            raise RuntimeError(err)
    excerpt = extract_failure_excerpt(log)
    prompt, system = build_job_diagnosis_prompt(check.name, excerpt)
    answer = m.ai.complete(prompt, system=system, max_tokens=600)
    if not answer.ok:
        raise RuntimeError(f"AI: {answer.error}")
    return parse_job_diagnosis(check.name, answer.text, excerpt), answer.model


def _claim(m, key: str, work) -> None:
    """Start `work` on a background thread unless the diagnosis under `key` is already running.

    The button's own "running" flag is from the last repaint, so two quick presses both
    saw it false. Claiming in state here closes that window.
    """
    claimed = []

    def claim(all_):
        all_ = all_ or {}
        current = all_.get(key)
        if current is not None and current.status == "running":
            return all_
        claimed.append(True)
        return {**all_, key: Diagnosis("running", model=m.state.get("ai_label"))}

    m.state.update("diagnoses", claim, default={})
    if claimed:
        m.run(work)


def start_diagnosis(m, number: int, options) -> None:
    """Start the diagnosis of a PR's failed checks unless one is already running."""
    _claim(m, str(number), lambda: diagnose(m, number, options))


def run_key(run_id: int) -> str:
    """Where a workflow run's diagnosis lives in state, apart from the PRs' (keyed by number)."""
    return f"run:{run_id}"


def start_run_diagnosis(m, run_id: int, options) -> None:
    """Start the diagnosis of a workflow run's failed jobs unless one is already running."""
    _claim(m, run_key(run_id), lambda: diagnose_run(m, run_id, options))


def _diagnose(m, key: str, get_checks) -> None:
    """Read the log of each failed check and explain it; `get_checks` runs inside the try."""

    def put(d: Diagnosis) -> None:
        m.state.update("diagnoses", lambda all_: {**(all_ or {}), key: d}, default={})

    put(Diagnosis("running", model=m.state.get("ai_label")))
    github = m.client("github")
    try:
        if github is None:
            raise RuntimeError("github plugin not available")
        checks = get_checks(github)
        with ThreadPoolExecutor(max_workers=len(checks) or 1) as pool:
            results = list(pool.map(lambda c: diagnose_job(m, github, c), checks))
        answered = next((model for _, model in results if model), None)
        put(Diagnosis("done", model=answered, jobs=tuple(job for job, _ in results)))
    except Exception as e:
        put(Diagnosis("error", error=str(e)))


def diagnose(m, number: int, options) -> None:
    """Explain the failed checks of one of my PRs; runs on a background thread."""
    prs: Optional[Prs] = m.state.get("prs")
    pr = next((p for p in (prs.mine if prs else []) if p.number == number), None)
    if pr is None:
        return
    _diagnose(m, str(number), lambda github: pr.failed_checks[: options["diagnosis_jobs"]])


def diagnose_run(m, run_id: int, options) -> None:
    """Explain the failed jobs of one workflow run; runs on a background thread."""

    def failed_jobs(github):
        match github.get_run_failed_jobs(run_id):
            case ClientSuccess(data=jobs):
                return jobs[: options["diagnosis_jobs"]]
            case ClientError(error_message=err):
                raise RuntimeError(err)

    _diagnose(m, run_key(run_id), failed_jobs)


def diagnosis_text(pr: UIPullRequest, d: Diagnosis) -> str:
    """The diagnosis as plain text, to paste into a PR comment, a chat or an AI session."""
    if d.status == "error":
        return f"PR #{pr.number} {pr.title}\nCould not diagnose: {d.error}\n"
    return format_job_diagnoses(pr.number, pr.title, d.jobs, d.model)


def refresh_ai_label(m) -> None:
    """Who answers a diagnosis now; resolving may probe, so it runs off the UI thread."""
    m.state.set("ai_label", m.ai.describe())
