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

import re
import shutil
from pathlib import Path
from typing import Iterable, Optional

from titan_cli.core.logging import get_logger

from ..models.review_models import PullRequestManifest
from ..models.view import UIComment, UICommentThread

MATERIAL_DIR = ".titan-review"
DIFFS_DIR = f"{MATERIAL_DIR}/diffs"
BASE_DIR = f"{MATERIAL_DIR}/base"
PR_FILE = f"{MATERIAL_DIR}/pr.md"
WHOLE_DIFF_FILE = f"{MATERIAL_DIR}/pr.diff"

logger = get_logger(__name__)


def _is_inside(root: Path, target: Path) -> bool:
    """True when `target` resolves (symlinks followed) to a path under `root`."""
    try:
        target.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def read_file_content(path: str, cwd: Optional[str] = None) -> Optional[str]:
    """A file of the reviewed tree as text, or None when it cannot be read.

    The tree is the PR author's checkout, so a path that resolves outside it (a committed
    symlink to a file elsewhere) is refused rather than shown as the file's content.
    """
    try:
        base = Path(cwd) if cwd else Path.cwd()
        file_path = base / path
        if not _is_inside(base, file_path):
            logger.warning("file_read_outside_tree", path=path)
            return None
        if file_path.exists() and file_path.is_file():
            return file_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError) as e:
        logger.debug("file_read_failed", path=path, error=str(e))
    return None


def prepare_material_dir(root: Path) -> Path:
    """A fresh, real `.titan-review/` directory inside `root`.

    The PR can commit anything at that path (a symlink, or files to be overwritten), so
    whatever is there is removed before the review's material is written.
    """
    material = root / MATERIAL_DIR
    if material.is_symlink() or material.is_file():
        material.unlink()
    elif material.exists():
        shutil.rmtree(material)
    material.mkdir(parents=True)
    return material


def safe_material_target(root: Path, relative_path: str) -> Path:
    """`root / relative_path`, guaranteed to resolve inside the material directory.

    Raises OSError otherwise (e.g. a `..` in a changed file's path, or a symlink planted
    under the directory).
    """
    target = root / relative_path
    if not _is_inside(root / MATERIAL_DIR, target):
        raise OSError(f"review material path escapes {MATERIAL_DIR}: {relative_path}")
    return target


def diff_file_path(path: str) -> str:
    """Where a changed file's diff lives, relative to the worktree root."""
    return f"{DIFFS_DIR}/{path}.diff"


def base_file_path(path: str) -> str:
    """Where a changed file's base version lives, relative to the worktree root."""
    return f"{BASE_DIR}/{path}"


def annotate_diff_hunk(hunk: str) -> str:
    """One hunk with each line labelled, and numbered by the new file where it has a line.

    `[ADDED]` and `[CONTEXT]` lines carry their line number in the new file, which is what
    a finding's `line` and `snippet` are anchored to. `[DELETED]` lines have no number: they
    are not in the new file. Removed code is labelled rather than hidden, because what a
    migration or refactor loses is often the defect (PR #3720: two analytics reducers
    removed while their actions are still dispatched).
    """
    lines = hunk.splitlines()
    if not lines:
        return ""

    header_line = next((line for line in lines if line.startswith("@@")), None)
    match = re.search(r"\+(\d+)", header_line) if header_line else None
    if match is None:
        return "\n".join(lines)

    result = [header_line]
    current_line = int(match.group(1))
    width = len(str(current_line + 100))
    for line in lines:
        if line.startswith("@@"):
            continue
        if line.startswith("---") or line.startswith("+++"):
            result.append(line)
        elif line.startswith("-"):
            result.append(f"[DELETED] {line[1:]}")
        elif line.startswith("+"):
            result.append(f"{str(current_line).rjust(width)} [ADDED] {line[1:]}")
            current_line += 1
        elif line.startswith(" "):
            result.append(f"{str(current_line).rjust(width)} [CONTEXT] {line[1:]}")
            current_line += 1
        else:
            result.append(line)
    return "\n".join(result)


def diff_unavailable(hunks: Iterable[str], additions: int, deletions: int) -> bool:
    """True when a file changed lines but no hunk text is available for it.

    Distinguishes a diff that was not fetched (too large a PR, patch omitted by GitHub)
    from files that have nothing textual to review (binary, pure rename).
    """
    return not any(hunks) and (additions + deletions) > 0


def render_file_diff(path: str, hunks: Iterable[str], unavailable: bool = False) -> str:
    """One file's diff with every line numbered and labelled, the same shape the prompt used.

    The numbers are the new file's lines, so a finding's `line` and `snippet` come straight
    from here, which is what inline anchoring depends on.
    """
    blocks = [annotate_diff_hunk(hunk) for hunk in hunks]
    body = "\n\n".join(block for block in blocks if block)
    if not body and unavailable:
        return f"# {path}\n\n(diff unavailable: read the file)\n"
    return f"# {path}\n\n{body}\n" if body else f"# {path}\n\n(no textual diff)\n"


def render_pr_file(
    pr: Optional[PullRequestManifest],
    threads: list[UICommentThread],
    general_comments: list[UICommentThread],
    base_sha: Optional[str],
) -> str:
    """The PR as `gh pr view --comments` would show it: what it claims, and every comment.

    Every thread in full, replies included, open and resolved. This used to be a summary of
    at most eight bug-like open threads cut to 220 chars, a limit set when the comments sat
    in the prompt; as a file it costs nothing until opened, and a reviewer told not to
    repeat what is already raised has to be able to see all of it.
    """
    lines: list[str] = []
    if pr:
        lines += [f"# PR #{pr.number}: {pr.title}", "", f"{pr.base} <- {pr.head}"]
        if base_sha:
            lines.append(f"Base versions are taken at {base_sha}, the commit the diff is against.")
        lines += ["", "## Description", "", (pr.description or "(no description)").strip(), ""]
    lines += ["## Review comments already made (do not repeat what they raise)", ""]
    if not threads and not general_comments:
        lines.append("(none)")
    for thread in threads:
        main = thread.main_comment
        where = f"{main.path}:{main.line}" if main.path and main.line else (main.path or "PR")
        state = "resolved" if thread.is_resolved else "open"
        if thread.is_outdated:
            state += ", outdated"
        lines += [f"### [{state}] {where}", ""]
        lines += [_comment_block(comment) for comment in [main, *thread.replies]]
    if general_comments:
        lines += ["## General comments", ""]
        for thread in general_comments:
            lines += [_comment_block(comment) for comment in [thread.main_comment, *thread.replies]]
    return "\n".join(lines) + "\n"


def _comment_block(comment: UIComment) -> str:
    return f"@{comment.author_login}:\n{(comment.body or '').strip()}\n"
