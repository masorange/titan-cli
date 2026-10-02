"""Operations for the free-form review session: its prompt, its answer, and its paths."""

import json
from typing import Any, Callable, Optional

from titan_cli.core.result import ClientError, ClientResult, ClientSuccess

from ..models.review_models import Finding
from .ai_response_parsing_operations import extract_json_payload


def build_free_review_prompt(
    pr_number: int,
    title: str,
    head: str,
    base: str,
    worktree: str,
    *,
    use_subagents: bool = False,
) -> str:
    """The prompt a user would give a CLI to review a PR, plus where Titan put the material.

    Deliberately no procedure. Every procedure Titan imposed (a focus to choose, a note per
    file, a coverage ledger) turned "find the serious problems" into "fill the form": a
    session handed 95 files claimed all of them and opened 31. A free-form review of the
    same PR, told only to review it, found more. The session is a reviewer; Titan hands it
    what `gh pr view --comments` and `gh pr diff` would and gets out of the way.

    Tests are not run: a PR has CI for that, and the review would pay to repeat it.

    The worktree is named by its absolute path: opencode started its session in the main
    repository (its first reads of `.titan-review/pr.md` failed and its `git status` ran
    against another checkout), and a relative "this directory" is only as good as the
    CLI's idea of where it is.
    """
    from .review_material_operations import BASE_DIR, DIFFS_DIR, PR_FILE, WHOLE_DIFF_FILE

    # Only for a CLI that can spawn them: asking one that cannot costs a failed tool call
    # and leaves the session reviewing a large PR alone anyway.
    subagent_hint = " If the PR is large, split the work across subagents." if use_subagents else ""
    return (
        f"Review pull request #{pr_number} \"{title}\" ({head} → {base}).\n\n"
        f"`{worktree}` is a checkout of the PR head. Work only inside it, with paths under "
        "it: the repository this was started from holds a different version of the code. "
        "What you would otherwise fetch is already there:\n"
        f"- `{PR_FILE}`: the PR description and the review comments already made on it, "
        "open and resolved. Do not raise again what a comment already raises.\n"
        f"- `{WHOLE_DIFF_FILE}`: the whole diff. `{DIFFS_DIR}/<path>.diff` is each file's, "
        "with every line marked [ADDED], [CONTEXT] or [DELETED] and numbered as in the new "
        "file.\n"
        f"- `{BASE_DIR}/<path>`: each changed file as it was before the PR.\n"
        "`.titan-review/` is not part of the PR; do not review it.\n\n"
        "Review it as a senior engineer would review this PR, using anything in the "
        f"repository you need.{subagent_hint} Do not run tests or builds: CI runs them.\n\n"
        "Report only problems a reviewer would raise on the PR: defects, regressions, risks "
        "and violations of how this repository does things, each one you have verified in "
        "the code. Severity: `blocking` must not merge, `important` should be fixed, `nit` "
        "is minor. A PR with nothing to report gets an empty list.\n\n"
        "In the findings, `path` is relative to the repository root, never the absolute "
        "path of the checkout.\n\n"
        "When you are done, answer with this JSON and nothing else:\n"
        f"{json.dumps(_FINDINGS_SHAPE, indent=2)}\n"
    )


_FINDINGS_SHAPE = {
    "findings": [
        {
            "path": "<file path, relative to the repository root>",
            "line": "<line number in the PR's version of the file, or null>",
            "severity": "<blocking|important|nit>",
            "title": "<short title>",
            "body": "<the review comment to post: the problem, why it matters, the fix>",
            "snippet": "<the exact text of that line, or null>",
        }
    ]
}


REVIEW_DISALLOWED_TOOLS = (
    "Edit",
    "Write",
    "NotebookEdit",
    "WebFetch",
    "WebSearch",
    "ScheduleWakeup",
    "Bash(git * --output*)",
    "Bash(git * --ext-diff*)",
    "Bash(git * --textconv*)",
    "Bash(git * --open-files-in-pager*)",
)
"""Tools removed from the review session: it reads, it does not change or fetch anything.

The `Bash(git ...)` rules close the flags that make an allowed read-only git command write
files (`--output`) or run an external program (`--ext-diff`, `--textconv`); the session reads
untrusted PR content, so a prompt-injected diff must not be able to use them.

Subagents (`Agent`) are allowed: they are how a free-form review gives a large PR depth in
separate contexts, the one thing a single session cannot do.

`ScheduleWakeup` is denied: both Opus runs on #273 called it ("wait for subagents") inside a
`--print` session, which has no later turn to wake.
"""

REVIEW_ALLOWED_TOOLS = (
    "Bash(git log:*)",
    "Bash(git show:*)",
    "Bash(git diff:*)",
    "Bash(git blame:*)",
)
"""The only shell the session gets: read-only git, for history and blame.

`git grep` is left out (`-O<cmd>` runs an arbitrary command); the Grep tool covers searching.

Any other command is denied in a headless session (verified 2026-10-01: `git log` ran,
`touch` was denied), which also keeps it from running tests or builds.
"""

REVIEW_EFFORT = "high"

REVIEW_TIMEOUT_SECONDS = 1800
"""The session's time ceiling. A free-form review of a 95-file PR took ~15 minutes."""

REVIEW_MAX_BUDGET_USD = 6.0
"""The session's cost ceiling, where the CLI enforces one. Above the $5.33 the free-form
reference review of the largest measured PR cost; reaching it ends the session with no
answer, so it is a safety net and not a target."""


def free_review_json_schema() -> dict[str, Any]:
    """JSON Schema for `--json-schema`: the findings list and nothing else.

    Wrapped in an object because the structured-output tool requires a top-level object.
    """
    return {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "line": {"type": ["integer", "null"]},
                        "severity": {"type": "string", "enum": ["blocking", "important", "nit"]},
                        "title": {"type": "string"},
                        "body": {"type": "string"},
                        "snippet": {"type": ["string", "null"]},
                    },
                    "required": ["path", "severity", "title", "body"],
                },
            },
        },
        "required": ["findings"],
    }


def parse_findings_response(stdout: str, *, structured: bool) -> ClientResult[list]:
    """Parse the review session's answer into its list of raw findings.

    When `structured` is True (the adapter enforced the schema), stdout is the envelope
    `{"findings": [...]}`. Otherwise stdout is free text: the envelope is taken when it is
    there, and a bare JSON array -- what a model that ignores the shape, or the reformat
    retry, returns -- is still accepted.
    """
    if not structured:
        match extract_json_payload(stdout, kind="object"):
            case ClientSuccess(data=payload) if isinstance(payload, dict) and isinstance(
                payload.get("findings"), list
            ):
                return ClientSuccess(data=payload["findings"])
        return extract_json_payload(stdout, kind="array")
    match extract_json_payload(stdout, kind="object"):
        case ClientSuccess(data=payload) if isinstance(payload, dict) and "findings" in payload:
            return ClientSuccess(data=payload["findings"])
        case ClientSuccess():
            return ClientError(
                error_message="Structured response missing 'findings' field",
                error_code="MISSING_FINDINGS_FIELD",
                log_level="warning",
            )
        case error:
            return error


def to_finding_payload(raw: Any) -> Any:
    """Map one finding of the session's shape onto the fields `Finding` validates.

    The session writes one `body`, the comment to post; it is both the reason and the
    comment. `snippet` doubles as the evidence the anchoring layer searches for. Anything
    that is not a dict is returned untouched for normalization to reject and count.
    """
    if not isinstance(raw, dict):
        return raw
    body = raw.get("body") or raw.get("suggested_comment") or raw.get("why") or ""
    snippet = raw.get("snippet") or None
    return {
        "severity": raw.get("severity"),
        "category": raw.get("category") or "review",
        "path": raw.get("path") or "",
        "line": raw.get("line") if isinstance(raw.get("line"), int) else None,
        "title": raw.get("title") or "",
        "why": body,
        "evidence": raw.get("evidence") or snippet or "",
        "snippet": snippet,
        "suggested_comment": body,
    }


def normalize_finding_path(path: str) -> str:
    """Canonicalise a path for comparison without being clever about it.

    Only the two differences a model plausibly introduces on its own: Windows
    separators and a "./" prefix. Case is preserved, because paths are case-sensitive
    where this runs and folding it would let two real files collide.
    """
    normalized = (path or "").strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def partition_findings_by_path(
    raw_findings: list,
    pr_paths: set[str],
    is_repo_file: Optional[Callable[[str], bool]] = None,
) -> tuple[list, list[dict]]:
    """Keep the findings about a file that exists; reject the ones about a path that does not.

    A file of the PR is kept, rewritten to the PR's spelling when it differs only by
    separator or "./" prefix. A file outside the PR is kept when it exists in the reviewed
    tree (`is_repo_file`): what a review finds there is the damage a PR does beyond its own
    diff -- on ragnarok PR #3688 the one blocking defect was in a file the PR never touched.
    It cannot anchor inline, so it publishes in the review body. A finding with no path is
    kept: a general observation is not misattributed to anything.

    Returns `(kept, rejected)`, where each rejected entry is `{"path", "title"}`.
    """
    canonical = {normalize_finding_path(path): path for path in pr_paths}
    kept: list = []
    rejected: list[dict] = []
    for finding in raw_findings or []:
        path = _finding_path(finding)
        if not path:
            kept.append(finding)
            continue
        normalized = normalize_finding_path(path)
        if normalized in canonical:
            kept.append(_with_path(finding, canonical[normalized]))
        elif is_repo_file is not None and is_repo_file(normalized):
            kept.append(_with_path(finding, normalized))
        else:
            rejected.append({"path": path, "title": _finding_title(finding)})
    return kept, rejected


def _finding_path(finding: Any) -> str:
    """Read the path off a raw finding, which is a dict before normalization."""
    value = finding.get("path") if isinstance(finding, dict) else getattr(finding, "path", None)
    return value.strip() if isinstance(value, str) else ""


def _finding_title(finding: Any) -> str:
    value = finding.get("title") if isinstance(finding, dict) else getattr(finding, "title", None)
    return _short_title(value) if isinstance(value, str) else ""


def _with_path(finding: Any, path: str) -> Any:
    """Return the finding carrying the given spelling of its path."""
    if isinstance(finding, dict) and finding.get("path") != path:
        return {**finding, "path": path}
    return finding


def build_default_findings() -> list[Finding]:
    return []


def _short_title(title: str, limit: int = 90) -> str:
    return title if len(title) <= limit else title[: limit - 3] + "..."
