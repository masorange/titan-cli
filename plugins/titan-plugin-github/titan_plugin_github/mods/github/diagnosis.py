"""Why a check of one of the user's PRs failed: its log, read by the AI the user routed this mod to.

Cutting the log, the prompt, reading the answer and the report are the github
plugin's (`ci_diagnosis_operations`); this file runs them over the PR's failed
checks with the mod's AI routing (`ask_ai` keeps the outcome in `m.state`, the jobs as its `value`).
"""
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Tuple

from titan_cli.ui.components import AIResult, ask_ai
from titan_cli.core.result import ClientError, ClientSuccess
from titan_plugin_github.models.view import UIFailedCheck, UIJobDiagnosis, UIPullRequest
from titan_plugin_github.operations import (
    build_job_diagnosis_prompt,
    extract_failure_excerpt,
    format_job_diagnoses,
    parse_job_diagnosis,
)

from .models import Prs


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


def pr_key(number: int) -> str:
    """Where a PR's diagnosis lives in state."""
    return f"pr:{number}"


def run_key(run_id: int) -> str:
    """Where a workflow run's diagnosis lives in state, apart from the PRs'."""
    return f"run:{run_id}"


def start_diagnosis(m, number: int, options) -> None:
    """Start the diagnosis of a PR's failed checks unless one is already running."""
    ask_ai(m, pr_key(number), lambda m: diagnose(m, number, options))


def start_run_diagnosis(m, run_id: int, options) -> None:
    """Start the diagnosis of a workflow run's failed jobs unless one is already running."""
    ask_ai(m, run_key(run_id), lambda m: diagnose_run(m, run_id, options))


def _diagnose(m, get_checks) -> AIResult:
    """Read the log of each failed check and explain it; `get_checks` runs inside `ask_ai`'s try."""
    github = m.client("github")
    if github is None:
        raise RuntimeError("github plugin not available")
    checks = get_checks(github)
    with ThreadPoolExecutor(max_workers=len(checks) or 1) as pool:
        results = list(pool.map(lambda c: diagnose_job(m, github, c), checks))
    answered = next((model for _, model in results if model), None)
    return AIResult("done", model=answered, value=tuple(job for job, _ in results))


def diagnose(m, number: int, options) -> AIResult:
    """Explain the failed checks of one of my PRs; runs on `ask_ai`'s background thread."""
    prs: Optional[Prs] = m.state.get("prs")
    pr = next((p for p in (prs.mine if prs else []) if p.number == number), None)
    if pr is None:
        raise RuntimeError(f"PR #{number} is not one of yours any more")
    return _diagnose(m, lambda github: pr.failed_checks[: options["diagnosis_jobs"]])


def diagnose_run(m, run_id: int, options) -> AIResult:
    """Explain the failed jobs of one workflow run; runs on `ask_ai`'s background thread."""

    def failed_jobs(github):
        match github.get_run_failed_jobs(run_id):
            case ClientSuccess(data=jobs):
                return jobs[: options["diagnosis_jobs"]]
            case ClientError(error_message=err):
                raise RuntimeError(err)

    return _diagnose(m, failed_jobs)


def diagnosis_text(pr: UIPullRequest, d: AIResult) -> str:
    """The diagnosis as plain text, to paste into a PR comment, a chat or an AI session."""
    if d.status == "error":
        return f"PR #{pr.number} {pr.title}\nCould not diagnose: {d.error}\n"
    return format_job_diagnoses(pr.number, pr.title, d.value, d.model)

