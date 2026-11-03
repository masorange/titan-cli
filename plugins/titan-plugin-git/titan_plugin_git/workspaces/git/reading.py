"""What the workspace reads from the git client: snapshots of a selection's files and of one file's diff."""
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

from titan_cli.core.result import ClientError, ClientSuccess
from titan_plugin_git.models.view import UIFileChange, UIFileDiff

WIP = "wip"  # the selection that is the uncommitted changes rather than a commit's hash


@dataclass(frozen=True)
class Group:
    """A titled run of files read from one side: `staged`, `unstaged` or `commit`."""

    title: str
    side: str
    files: List[UIFileChange] = field(default_factory=list)


@dataclass(frozen=True)
class Files:
    """The files of one selection. `status` is `loading`, `done` or `error`."""

    status: str = "loading"
    groups: Tuple[Group, ...] = ()
    error: Optional[str] = None

    @property
    def all(self) -> List[UIFileChange]:
        return [f for g in self.groups for f in g.files]

    @property
    def additions(self) -> int:
        return sum(f.additions for f in self.all)

    @property
    def deletions(self) -> int:
        return sum(f.deletions for f in self.all)


@dataclass(frozen=True)
class FileDiff:
    """One file's diff. `status` is `loading`, `done` or `error`."""

    status: str = "loading"
    diff: Optional[UIFileDiff] = None
    error: Optional[str] = None


def card_key(selection: str, side: str, path: str) -> str:
    """What names one file card: the same path can be staged and unstaged, or in two commits."""
    return f"{selection}|{side}|{path}"


def read_files(git: Any, selection: str) -> Files:
    """The files of the uncommitted changes (staged and unstaged apart) or of a commit."""
    if git is None:
        return Files("error", error="git plugin not available")
    if selection == WIP:
        match git.get_uncommitted_files():
            case ClientSuccess(data=changes):
                groups = (Group("Staged", "staged", changes.staged), Group("Unstaged", "unstaged", changes.unstaged))
                return Files("done", tuple(g for g in groups if g.files))
            case ClientError(error_message=err):
                return Files("error", error=err)
    match git.get_commit_files(selection):
        case ClientSuccess(data=files):
            return Files("done", (Group("Files", "commit", files),) if files else ())
        case ClientError(error_message=err):
            return Files("error", error=err)


def read_file_diff(git: Any, selection: str, side: str, path: str, context_lines: int) -> FileDiff:
    """One file's diff, from the commit, the index or the working tree as the card says."""
    if git is None:
        return FileDiff("error", error="git plugin not available")
    if selection == WIP:
        result = git.get_worktree_file_diff(path, staged=(side == "staged"), context_lines=context_lines)
    else:
        result = git.get_commit_file_diff(selection, path, context_lines)
    match result:
        case ClientSuccess(data=diff):
            return FileDiff("done", diff)
        case ClientError(error_message=err):
            return FileDiff("error", error=err)
