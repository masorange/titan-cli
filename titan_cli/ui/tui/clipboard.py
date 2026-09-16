"""
Put text on the system clipboard, and say honestly whether it worked.

Textual's `App.copy_to_clipboard` writes an OSC 52 escape and hopes the terminal
acts on it. Plenty do not — VTE-based terminals (GNOME Terminal, Tilix, Terminator)
and macOS Terminal among them — and the sequence is fire-and-forget, so nothing
fails and nothing arrives. A copy button that silently does nothing is worse than
no copy button.

So the local helper is tried first, because when it returns zero the text really
is on the clipboard. OSC 52 is the fallback, since it is the only thing that
works when the session is not local at all — over SSH, in a container, on a bare
tty. It is also the *only* thing that would be right if this ran over SSH with
X11 forwarding, where `$DISPLAY` is set but points at the wrong machine; that
case is rare enough to accept, and the notification says which route was taken.

Domain-free, like the widgets that use it: it takes a string and nothing else.
"""

import os
import shutil
import subprocess
import sys
from typing import Optional

#: Each candidate: the command, and the environment variable that has to be set
#: for it to be pointing at anything. `None` means "no display needed".
HELPERS = [
    (["wl-copy"], "WAYLAND_DISPLAY"),
    (["xclip", "-selection", "clipboard"], "DISPLAY"),
    (["xsel", "--clipboard", "--input"], "DISPLAY"),
]

#: macOS has one that always works and needs no display.
MAC_HELPER = ["pbcopy"]

#: A clipboard helper that has not answered in this long is not going to.
TIMEOUT_SECONDS = 2


def copy_to_system_clipboard(text: str) -> Optional[str]:
    """
    Copy `text`, returning the command that took it, or None if none did.

    None does not mean the text is lost — the caller still has OSC 52 to try —
    it means nothing has *confirmed* taking it.
    """
    for command in _candidates():
        if _run(command, text):
            return command[0]
    return None


def _candidates() -> list[list[str]]:
    if sys.platform == "darwin" and shutil.which(MAC_HELPER[0]):
        return [MAC_HELPER]

    return [
        command for command, display in HELPERS
        if shutil.which(command[0]) and (display is None or os.environ.get(display))
    ]


def _run(command: list[str], text: str) -> bool:
    try:
        # stdout and stderr go to DEVNULL rather than to a pipe: both `xclip` and
        # `wl-copy` fork a process that holds the selection for as long as it is
        # offered, and that child inherits the pipes. Capturing them means waiting
        # for an EOF that only arrives when the clipboard contents are replaced.
        result = subprocess.run(
            command,
            input=text.encode("utf-8"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False

    return result.returncode == 0
