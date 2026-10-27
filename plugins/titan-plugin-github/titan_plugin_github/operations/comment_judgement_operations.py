"""The judging session: its prompt, its answer, and the files it leaves for the fix.

One headless session reads the PR once and decides about EVERY pending comment, instead of a
session per comment that sees eleven lines of diff. That is what makes a cross-file answer
possible at all: on PR #276 a fix changed `submit_review_actions` for one workflow and broke
the other caller, because the session answering that comment could not see anything else.

Its answer is not acted on. Titan shows each verdict to the user, who accepts, edits or
rejects it, and only then does an interactive session make the change - the part of this
workflow that already works. The verdict travels to that session as a FILE: no adapter can
resume a session, so what the judge worked out survives only if it is written down.
"""

import json
import re
from typing import Any, Iterable, Optional

from titan_cli.core.result import ClientError, ClientResult, ClientSuccess

from ..models.review_enums import CommentVerdictType
from ..models.review_models import CommentVerdict
from ..models.view import UICommentThread
from .ai_response_parsing_operations import extract_json_payload

VERDICTS_DIR = "verdicts"

JUDGEMENT_TIMEOUT_SECONDS = 1200
"""Time ceiling for the judging session. It reads the PR once for every comment at once."""

JUDGEMENT_MAX_BUDGET_USD = 4.0
"""Cost ceiling where the CLI enforces one. Reaching it ends the session with no answer, so
it is a safety net and not a target: the measured free-form review of the largest PR in the
benchmark cost $5.33, and judging comments is a smaller job than reviewing a PR."""

JUDGEMENT_EFFORT = "high"


def render_comments_file(threads: Iterable[UICommentThread]) -> str:
    """The pending comments as one document, each with the id the answer must use.

    Every thread in full, replies included: a comment is often already answered further down
    its own thread, and a judge that cannot see the replies calls that "apply".
    """
    blocks: list[str] = ["# Pending review comments", ""]
    for thread in threads:
        main = thread.main_comment
        if not main:
            continue
        where = f"{main.path}:{main.line}" if main.path and main.line else (main.path or "PR")
        kind = "general comment" if thread.is_general_comment else "review comment"
        state = " (outdated: the code it points at has changed)" if thread.is_outdated else ""
        blocks.append(f"## comment_id {main.id} — {kind} on {where}{state}")
        blocks.append("")
        for comment in [main, *(thread.replies or [])]:
            blocks.append(f"@{comment.author_login}:")
            blocks.append((comment.body or "").strip())
            blocks.append("")
    if len(blocks) == 2:
        blocks.append("(none)")
    return "\n".join(blocks) + "\n"


def build_judgement_prompt(
    pr_number: int,
    title: str,
    head: str,
    base: str,
    repo_root: str,
    material_dir: str,
    comment_count: int,
    *,
    use_subagents: bool = False,
) -> str:
    """What the judging session is asked, with no procedure beyond the question itself.

    The lesson the review pipeline paid for twice (`review_coverage` D-033): every procedure
    Titan imposed turned "find the real problems" into "fill the form". So this prompt says
    what to decide and what the answer must look like, and leaves the reading to the CLI.

    The repository is named by its absolute path because a CLI that starts elsewhere reads
    another checkout. The material sits INSIDE it, in `.titan-review/`, because a restricted
    session cannot read outside its working directory; being untracked and excluded from
    `git status`, it is not swept into the next commit. Preparing it removes any existing
    `.titan-review` in the user's real checkout (`prepare_material_dir`).
    """
    from .review_material_operations import BASE_DIR, DIFFS_DIR, MATERIAL_DIR, PR_FILE, WHOLE_DIFF_FILE

    def rel(path: str) -> str:
        """The name a session reads, relative to `material_dir`.

        The constants are relative to a repository root, because the review writes them
        inside its worktree. `material_dir` already IS that directory here, so using them
        unchanged sent the session to `<material_dir>/.titan-review/pr.md` - a path that
        does not exist, and nothing said so.
        """
        prefix = f"{MATERIAL_DIR}/"
        return path[len(prefix):] if path.startswith(prefix) else path

    subagent_hint = (
        " On a PR with many comments you may split the reading across subagents; run them in "
        "the foreground and answer only once every one has reported, since this session gets "
        "no later turn."
        if use_subagents
        else ""
    )
    return (
        f"You are the author of pull request #{pr_number} \"{title}\" ({head} → {base}), "
        f"deciding what to do with the {comment_count} review comment(s) still pending on it.\n\n"
        f"`{repo_root}` is the repository, checked out at the PR head. Read it as you need. "
        f"Everything else is in `{material_dir}`:\n"
        f"- `comments.md`: the pending comments, each with its `comment_id`. These are what "
        "you are judging.\n"
        f"- `{rel(PR_FILE)}`: the PR description and every comment already on it, replies "
        "included.\n"
        f"- `{rel(WHOLE_DIFF_FILE)}`: the whole diff. `{rel(DIFFS_DIR)}/<path>.diff` is each "
        "file's, with every line marked [ADDED], [CONTEXT] or [DELETED].\n"
        f"- `{rel(BASE_DIR)}/<path>`: each changed file as it was before the PR.\n\n"
        "For EACH comment, decide one of:\n"
        "- `apply`: the comment is right and the code should change.\n"
        "- `already_done`: the branch already does what it asks (a later commit, another "
        "part of the diff, or a reply in its own thread).\n"
        "- `wrong`: it is mistaken about what the code does, or no longer applies.\n"
        "- `needs_discussion`: it is a judgement call that is not yours to make alone.\n\n"
        "Check each one in the code before deciding; a verdict you did not verify is a guess."
        f"{subagent_hint} Do not change any file, and do not run tests or builds.\n\n"
        "For an `apply` verdict, the session that will make the change is a fresh one that "
        "has not read any of this. So write down what it needs: every file the change touches "
        "(`files_affected`), every OTHER place that uses what is about to change and must keep "
        "working (`callers_to_check` — search for them, this is where fixes break things), "
        "what the change could break (`risk`), and the change itself in prose (`proposed_fix`). "
        "For the other three verdicts write `reply_draft`: two or three sentences, as a "
        "colleague would answer in the thread, saying why.\n\n"
        "Answer with one entry per comment, using its `comment_id`, as this JSON and nothing "
        f"else:\n{json.dumps(_VERDICTS_SHAPE, indent=2)}\n"
    )


_VERDICTS_SHAPE = {
    "verdicts": [
        {
            "comment_id": "<the comment's id, as given in comments.md>",
            "verdict": "<apply|already_done|wrong|needs_discussion>",
            "reason": "<why, in one or two sentences, from what you checked in the code>",
            "files_affected": ["<path a fix would change>"],
            "callers_to_check": ["<other place that uses what would change>"],
            "risk": "<what the change could break, or null>",
            "proposed_fix": "<the change in prose, for an apply verdict, or null>",
            "reply_draft": "<the reply to post when no change is made, or null>",
        }
    ]
}


def judgement_json_schema() -> dict[str, Any]:
    """JSON Schema for `--json-schema`: the verdict list and nothing else."""
    return {
        "type": "object",
        "properties": {
            "verdicts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        # One type, not `integer|string`: the CLI validates this schema in
                        # Ajv strict mode, which rejects a union unless it includes `null`
                        # ("use allowUnionTypes ... (strictTypes)"), and a rejected schema
                        # makes the session answer `{"verdicts": []}`. A CLI without
                        # structured output can still answer with a digit string, which
                        # `to_verdict` accepts.
                        "comment_id": {"type": "integer"},
                        "verdict": {
                            "type": "string",
                            "enum": [v.value for v in CommentVerdictType],
                        },
                        "reason": {"type": "string"},
                        "files_affected": {"type": "array", "items": {"type": "string"}},
                        "callers_to_check": {"type": "array", "items": {"type": "string"}},
                        "risk": {"type": ["string", "null"]},
                        "proposed_fix": {"type": ["string", "null"]},
                        "reply_draft": {"type": ["string", "null"]},
                    },
                    "required": ["comment_id", "verdict", "reason"],
                },
            },
        },
        "required": ["verdicts"],
    }


def parse_judgement_response(stdout: str, *, structured: bool) -> ClientResult[list]:
    """Parse the judging session's answer into its list of raw verdicts.

    A bare array is accepted as well as the envelope: a model that ignores the shape, and the
    reformat retry, both return one.
    """
    match extract_json_payload(stdout, kind="object"):
        case ClientSuccess(data=payload) if isinstance(payload, dict) and isinstance(
            payload.get("verdicts"), list
        ):
            return ClientSuccess(data=payload["verdicts"])
        case ClientSuccess() if structured:
            return ClientError(
                error_message="Structured response missing 'verdicts' field",
                error_code="MISSING_VERDICTS_FIELD",
                log_level="warning",
            )
        case _:
            pass
    return extract_json_payload(stdout, kind="array")


def to_verdict(raw: Any, known_ids: set[int]) -> Optional[CommentVerdict]:
    """One raw entry as a `CommentVerdict`, or None when it cannot be trusted.

    Dropped rather than guessed: an id that is not one of the comments being judged (a
    hallucinated or mistyped number would otherwise attach an answer to the wrong thread),
    an unknown verdict, and a missing reason - a verdict with no reason cannot be judged by
    the user, which is the whole point of showing it to them.
    """
    if not isinstance(raw, dict):
        return None

    comment_id = _as_int(raw.get("comment_id"))
    if comment_id is None or comment_id not in known_ids:
        return None

    verdict = str(raw.get("verdict", "")).strip().lower()
    if verdict not in {v.value for v in CommentVerdictType}:
        return None

    reason = str(raw.get("reason") or "").strip()
    if not reason:
        return None

    return CommentVerdict(
        comment_id=comment_id,
        verdict=CommentVerdictType(verdict),
        reason=reason,
        files_affected=_as_str_list(raw.get("files_affected")),
        callers_to_check=_as_str_list(raw.get("callers_to_check")),
        risk=_as_text(raw.get("risk")),
        proposed_fix=_as_text(raw.get("proposed_fix")),
        reply_draft=_as_text(raw.get("reply_draft")),
    )


def _as_int(value: Any) -> Optional[int]:
    """An id as an int, accepting the digit string a CLI without a schema returns."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = str(value or "").strip()
    return int(text) if re.fullmatch(r"\d+", text) else None


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


def _as_text(value: Any) -> Optional[str]:
    text = str(value).strip() if value is not None else ""
    return text or None


def verdict_file_path(comment_id: int) -> str:
    """Where one comment's verdict is written, relative to the material directory."""
    return f"{VERDICTS_DIR}/comment-{comment_id}.md"


def render_verdict_file(verdict: CommentVerdict, thread: UICommentThread) -> str:
    """The verdict as the fix session reads it: the comment, the analysis, the change.

    Written as prose rather than JSON because it is read by a model that was given no schema,
    and because the user may have edited it before it got here.
    """
    main = thread.main_comment
    where = ""
    if main and main.path:
        where = f"{main.path}:{main.line}" if main.line else main.path

    lines = [f"# Review comment {verdict.comment_id}"]
    if where:
        lines.append(f"\nOn `{where}`.")
    lines.append("\n## The comment\n")
    for comment in [main, *(thread.replies or [])] if main else []:
        lines.append(f"@{comment.author_login}:\n{(comment.body or '').strip()}\n")

    lines.append("## What was found when the whole PR was read\n")
    lines.append(verdict.reason.strip())
    if verdict.files_affected:
        lines.append("\n### Files to change\n")
        lines += [f"- `{path}`" for path in verdict.files_affected]
    if verdict.callers_to_check:
        lines.append("\n### Other users of what changes — these must keep working\n")
        lines += [f"- `{caller}`" for caller in verdict.callers_to_check]
    if verdict.risk:
        lines.append(f"\n### Risk\n\n{verdict.risk.strip()}")
    if verdict.proposed_fix:
        lines.append(f"\n## The change\n\n{verdict.proposed_fix.strip()}")
    return "\n".join(lines) + "\n"


def build_fix_session_prompt(verdict_path: str, response_file: str) -> str:
    """What the interactive fix session is told, now that a verdict precedes it.

    It no longer evaluates: that was decided and the user approved it. It makes the change,
    with the analysis it would otherwise have to redo per comment, and the user steers it -
    which is what this workflow has always been good at.
    """
    return f"""Make the change this review comment asks for.

`{verdict_path}` holds the comment, what was found when the whole PR was read, the files to
change, and the other places that use what you are about to change.

## Your task

1. Read that file first.
2. Make the change in the repository you are in.
3. **Check every caller listed there, and search for any the analysis missed.** A fix that
   answers its comment and breaks another user of the same code is the failure this workflow
   is trying to stop.
4. Stay inside what the comment asks for. Unrelated improvements belong in another PR.
5. Follow this repository's own conventions and documentation.

If, reading the code, you conclude the change should NOT be made after all, do not change
anything: write why to {response_file} instead, in two or three sentences:

```bash
cat > {response_file} << 'EOF'
Your response text here
EOF
```

## When you're done

Tell the user: "Done. Press Ctrl+C twice to exit and return to Titan."
"""
