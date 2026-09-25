"""The review's material, laid out as files in the review worktree.

Titan already fetches everything the review needs -- the diff, the PR, its comments -- so the
CLI does not pay calls to fetch it. Pasting it all into the prompt was the wrong delivery: a
400k-char prompt is re-read on every turn of the session (4.6M cache-read tokens on ragnarok
#3723), and a session that has everything in front of it explores less. As files it costs
nothing until opened, it reads the same way on every CLI (Read / Grep / Glob, no shell), and it
can carry what the prompt never could: the BASE version of each changed file, without which a
session guesses how the old code behaved.

The folder is hidden (`.titan-review/`): the CLIs' search tools skip hidden directories by
default, so a plain search of the tree does not mix the old code in with the new.
"""

from typing import Callable, Iterable, Optional

from ..models.review_models import CommentContextEntry, PullRequestManifest
from .findings_operations import _annotate_diff_hunk

MATERIAL_DIR = ".titan-review"
DIFFS_DIR = f"{MATERIAL_DIR}/diffs"
BASE_DIR = f"{MATERIAL_DIR}/base"
PR_FILE = f"{MATERIAL_DIR}/pr.md"
WHOLE_DIFF_FILE = f"{MATERIAL_DIR}/pr.diff"


def diff_file_path(path: str) -> str:
    """Where a changed file's diff lives, relative to the worktree root."""
    return f"{DIFFS_DIR}/{path}.diff"


def base_file_path(path: str) -> str:
    """Where a changed file's base version lives, relative to the worktree root."""
    return f"{BASE_DIR}/{path}"


def render_file_diff(path: str, hunks: Iterable[str]) -> str:
    """One file's diff with every line numbered and labelled, the same shape the prompt used.

    The numbers are the new file's lines, so a finding's `line` and `snippet` come straight
    from here, which is what inline anchoring depends on.
    """
    blocks = [_annotate_diff_hunk(hunk) for hunk in hunks]
    body = "\n\n".join(block for block in blocks if block)
    return f"# {path}\n\n{body}\n" if body else f"# {path}\n\n(no textual diff)\n"


def render_pr_file(
    pr: Optional[PullRequestManifest],
    comments: list[CommentContextEntry],
    base_sha: Optional[str],
) -> str:
    """The PR as the session needs it: what it claims, and what reviewers already said."""
    lines: list[str] = []
    if pr:
        lines += [f"# PR #{pr.number}: {pr.title}", "", f"{pr.base} <- {pr.head}"]
        if base_sha:
            lines.append(f"Base versions are taken at {base_sha}, the commit the diff is against.")
        lines += ["", "## Description", "", (pr.description or "(no description)").strip(), ""]
    lines += ["## Existing review comments (do not repeat what they already say)", ""]
    if not comments:
        lines.append("(none)")
    for entry in comments:
        where = f"{entry.path}:{entry.line}" if entry.path and entry.line else (entry.path or "PR")
        state = "resolved" if entry.is_resolved else "open"
        lines.append(f"- [{state}] {where} -- {entry.title}: {entry.summary}")
    return "\n".join(lines) + "\n"


def review_material_hint(path: str, has_base: bool) -> str:
    """The line under a file in the prompt: where its diff and its old version are."""
    base = f"base: `{base_file_path(path)}`" if has_base else "new file (no base version)"
    return f"diff: `{diff_file_path(path)}` · {base}"


def _collapse(text: str) -> str:
    return " ".join((text or "").split())


def check_old_code_claims(
    findings: list,
    read_base: Callable[[str], Optional[str]],
    read_head: Callable[[str], Optional[str]],
    base_paths: Iterable[str] = (),
) -> tuple[list, list]:
    """Keep a finding about what the old code did only if the old code says so.

    A finding that claims a behaviour was removed quotes, in `old_code`, the base-version line
    that had it. The claim stands only if some changed file had that line before and no
    longer has it: the finding's own file first, then every other changed file, because the
    old behaviour often lived elsewhere (on ragnarok #3723 the dropped `it.id != tariff.id`
    was in two ViewModels, and the finding named the new file that replaced them). Twice a
    session reported "the purchase analytics are now commented out" when they were commented
    out before the PR too: the quoted line is in both versions, so the claim is dropped.

    Compared with whitespace collapsed, so re-indentation does not count as a change.
    Returns (kept, rejected); each rejected item carries a `reason`.
    """
    others = list(base_paths)
    kept: list = []
    rejected: list = []
    for finding in findings:
        old = finding.get("old_code") if isinstance(finding, dict) else None
        if not isinstance(old, str) or not old.strip():
            kept.append(finding)
            continue
        own = str(finding.get("path") or "")
        quote = _collapse(old)
        had_it = [path for path in [own, *[p for p in others if p != own]] if quote in _collapse(read_base(path) or "")]
        if not had_it:
            rejected.append({**finding, "reason": "the old code it quotes is not in any base version"})
        elif all(quote in _collapse(read_head(path) or "") for path in had_it):
            rejected.append({**finding, "reason": "the old code it quotes is still in the new version"})
        else:
            kept.append(finding)
    return kept, rejected
