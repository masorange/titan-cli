"""
Operations for explaining why a CI job failed.

Reading a failed job's log, cutting it to what an AI can take, asking for a
cause and checking the answer against the log. The AI call itself is the
caller's (a step's adapter, a mod's routing): these functions only build the
prompt and read the answer.
"""

import re
from typing import List, Optional, Sequence, Tuple

from titan_cli.core.result import ClientSuccess

from ..models.view import UIJobDiagnosis
from .ai_response_parsing_operations import extract_json_payload

LOG_EXCERPT_CHARS = 40_000
LOG_TAIL_LINES = 120

_FAILURE_LINE = re.compile(
    r"##\[error\]|\bFAILED\b|BUILD FAILED|What went wrong|^e: |\berror:|Exception|AssertionError|> Task .* FAILED|Traceback"
)
_TIMESTAMP = re.compile(r"^\d{4}-\d\d-\d\dT[\d:.]+Z ")

JOB_DIAGNOSIS_SYSTEM = """You read the log of one failed CI job and say why it failed.
Answer with one JSON object and nothing else: {"cause": string, "where": string, "quote": string}.
- cause: one sentence, the most likely reason the job failed, naming the task, test or rule.
- where: "path/File.ext:line" when the log names one, else "".
- quote: ONE line copied character for character from the log that shows the failure, without its timestamp.
Never infer a cause the log does not show. If the log does not make it clear, say so in cause."""


def extract_failure_excerpt(
    log: str, max_chars: int = LOG_EXCERPT_CHARS, tail_lines: int = LOG_TAIL_LINES
) -> str:
    """
    Cut a job log (Actions logs run to megabytes) to the lines that report a
    failure, with a few lines of context each, plus the log's tail; timestamps
    stripped, at most `max_chars` (the end kept).
    """
    lines = [_TIMESTAMP.sub("", line) for line in log.split("\n")]
    keep = set(range(max(0, len(lines) - tail_lines), len(lines)))
    for i, line in enumerate(lines):
        if _FAILURE_LINE.search(line):
            keep.update(range(max(0, i - 3), min(len(lines), i + 7)))
    text = "\n".join(lines[i] for i in sorted(keep))
    return text[-max_chars:]


def build_job_diagnosis_prompt(job_name: str, excerpt: str) -> Tuple[str, str]:
    """The (prompt, system) pair that asks an AI why `job_name` failed, given its log excerpt."""
    return f"Job: {job_name}\n\nLog excerpt:\n{excerpt}", JOB_DIAGNOSIS_SYSTEM


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_job_diagnosis(job_name: str, answer: str, excerpt: str) -> UIJobDiagnosis:
    """
    Read the AI's answer to `build_job_diagnosis_prompt`. Without a JSON object
    the answer's first line is the cause; a quote that is not in `excerpt` is
    flagged, since the AI made it up.
    """
    parsed = {}
    match extract_json_payload(answer, "object"):
        case ClientSuccess(data=data) if isinstance(data, dict):
            parsed = data
    quote = str(parsed.get("quote") or "").strip()
    first_line = answer.strip().split("\n")[0] if answer.strip() else ""
    return UIJobDiagnosis(
        job_name=job_name,
        cause=str(parsed.get("cause") or "").strip() or first_line or "No answer",
        where=str(parsed.get("where") or "").strip(),
        quote=quote,
        is_quote_in_log=bool(quote) and _squash(quote) in _squash(excerpt),
    )


def format_job_diagnoses(
    pr_number: int, pr_title: str, diagnoses: Sequence[UIJobDiagnosis], model: Optional[str] = None
) -> str:
    """The diagnoses of a PR's failed jobs as plain text, for a PR comment, a chat or an AI session."""
    lines: List[str] = [f"PR #{pr_number} {pr_title}", f"Diagnosed by {model or 'AI routing'}", ""]
    for d in diagnoses:
        lines.append(f"✗ {d.job_name}")
        lines.append(d.cause)
        if d.where:
            lines.append(f"at {d.where}")
        if d.quote:
            lines.append(f"> {d.quote}")
            if not d.is_quote_in_log:
                lines.append("(this line is not in the log: do not trust the cause)")
        lines.append("")
    return "\n".join(lines)
