"""Mapper: unified diff text → `UIFileDiff`. Pure: no I/O, no logging."""
import re

from ..view import UIDiffHunk, UIDiffLine, UIFileDiff

_HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
_BINARY_MARKERS = ("Binary files ", "GIT binary patch")


def from_unified_diff(text: str, path: str) -> UIFileDiff:
    """
    Parse the output of `git diff` / `git show` for one file.

    The file headers (`diff --git`, `index`, `---`, `+++`) are skipped; each `@@` block
    becomes a hunk whose lines carry their old/new numbers. Empty input is a diff with no
    hunks (nothing changed); a binary patch is marked `is_binary` and has no hunks.
    """
    hunks = []
    header = None
    lines = []
    old_no = new_no = 0
    is_binary = False

    def close():
        if header is not None:
            hunks.append(UIDiffHunk(header=header, lines=lines))

    for raw in text.split("\n"):
        match = _HUNK.match(raw)
        if match:
            close()
            header, lines = raw, []
            old_no, new_no = int(match.group(1)), int(match.group(2))
            continue
        if header is None:
            if raw.startswith(_BINARY_MARKERS):
                is_binary = True
            continue
        if raw.startswith("\\"):
            lines.append(UIDiffLine(kind="no_newline", text=raw[1:].strip()))
        elif raw.startswith("+"):
            lines.append(UIDiffLine(kind="add", text=raw[1:], new_no=new_no))
            new_no += 1
        elif raw.startswith("-"):
            lines.append(UIDiffLine(kind="del", text=raw[1:], old_no=old_no))
            old_no += 1
        elif raw.startswith(" "):
            lines.append(UIDiffLine(kind="context", text=raw[1:], old_no=old_no, new_no=new_no))
            old_no += 1
            new_no += 1
        # Anything else is the empty piece after the last newline (or a stray header line).
    close()
    return UIFileDiff(path=path, hunks=hunks, is_binary=is_binary)
