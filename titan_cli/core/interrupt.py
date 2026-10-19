"""
Cooperative interruption for blocking calls made from workflow threads.

A workflow runs on a non-daemon executor thread that the interpreter joins at
exit. The ask_* prompts already poll `app.is_running` so they unblock when the
user quits mid-prompt, but a call that blocks inside foreign code - an AI SDK's
HTTP request, a headless CLI subprocess - has no loop to poll from. Quitting
the TUI while one is in flight used to hang the console until the call
finished, needing a second Ctrl+C to kill the join.

`run_interruptible` closes that gap: it moves the blocking call onto a daemon
thread (which the interpreter never joins) and polls an abort check from the
workflow thread. When the TUI closes, the workflow thread raises
`WorkflowAborted` and dies cleanly; the abandoned call finishes alone on the
daemon thread and its result is discarded.

The abort check is process-global rather than threaded through every layer
because only one workflow runs at a time and the transports that need it
(AIClient, headless adapters) sit four layers below the screen that knows
whether the app is alive. When no check is registered - unit tests, headless
usage outside the TUI - `run_interruptible` calls the function inline and
behaves exactly like not being there.
"""

import contextvars
import subprocess
import threading
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")

_POLL_INTERVAL_SECONDS = 0.5

_abort_check: Optional[Callable[[], bool]] = None

_cancel_requested = False
_tracked_processes: set = set()
_tracked_lock = threading.Lock()


class WorkflowAborted(BaseException):
    """
    The TUI closed while a workflow call was in flight.

    Inherits `BaseException` deliberately: transports and the step loop catch
    `Exception` broadly to convert failures into step errors, and an abort must
    not be converted - it has to unwind the whole workflow thread, like
    `KeyboardInterrupt` would on the main thread.
    """


def set_abort_check(check: Callable[[], bool]) -> None:
    """Register the check consulted by `run_interruptible` (True = abort)."""
    global _abort_check, _cancel_requested
    _abort_check = check
    _cancel_requested = False


def clear_abort_check() -> None:
    """Remove the registered abort check."""
    global _abort_check
    _abort_check = None


def cancel_requested() -> bool:
    """Whether the user cancelled the running workflow (as opposed to quitting the app)."""
    return _cancel_requested


def request_cancel() -> None:
    """
    The user left a running workflow: abort its blocking calls and kill its children.

    Quitting the app already aborted blocking calls, but cancelling a workflow leaves
    the app running, so the abort check never fired and the headless CLI subprocess
    kept going for its full duration - minutes of paid AI work whose result nothing
    would ever read. Killing the tracked processes stops that spend at once; the flag
    makes the workflow thread raise `WorkflowAborted` on its next poll.
    """
    global _cancel_requested
    _cancel_requested = True
    kill_tracked_processes()


def kill_tracked_processes() -> None:
    """Kill every subprocess started through `run_tracked` that is still running."""
    with _tracked_lock:
        processes = list(_tracked_processes)
    for proc in processes:
        try:
            proc.kill()
        except Exception:
            pass


def run_tracked(cmd: list[str], *, input: Optional[str] = None, timeout: Optional[float] = None, capture_output: bool = True, text: bool = True, **kwargs: Any) -> "subprocess.CompletedProcess":
    """
    `subprocess.run(cmd, capture_output=True, text=True, ...)` whose child can be killed by `request_cancel`.

    Same contract as `subprocess.run` for the cases the headless adapters use: output is
    always captured as text (`capture_output`/`text` exist only so call sites read like `run`), `TimeoutExpired` is raised after killing the child, and a missing
    binary raises `FileNotFoundError`. Remaining keyword arguments go to `Popen`.
    """
    with subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE if input is not None else kwargs.pop("stdin", None),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        **kwargs,
    ) as proc:
        with _tracked_lock:
            _tracked_processes.add(proc)
        try:
            stdout, stderr = proc.communicate(input=input, timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise
        except BaseException:
            proc.kill()
            raise
        finally:
            with _tracked_lock:
                _tracked_processes.discard(proc)
        return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)


def abort_requested() -> bool:
    """Whether the registered check currently asks to abort."""
    if _cancel_requested:
        return True
    check = _abort_check
    if check is None:
        return False
    try:
        return bool(check())
    except Exception:
        # A check that can no longer answer (app torn down mid-call) means the
        # app is gone, which is exactly the abort condition.
        return True


def run_interruptible(fn: Callable[[], T]) -> T:
    """
    Run a blocking call so the calling thread can abandon it on app exit.

    Runs `fn` on a daemon thread and polls the abort check every half second.
    Returns `fn`'s result or re-raises its exception. Raises `WorkflowAborted`
    if the check fires first; `fn` keeps running on the daemon thread but its
    outcome is discarded and the thread cannot block interpreter shutdown.

    With no abort check registered, calls `fn` inline.

    The daemon thread runs inside a COPY of the caller's context, so contextvars set
    around the call still apply inside it. A bare `threading.Thread` starts with an
    empty context, which silently stripped the log's run id from everything that goes
    through here — measured 2026-09-22: 3,573 `findings_batch_adapter_call` events and
    every `ai_call_cost` event had no `run` field, because every AI call in a review is
    made through this function. Cost that cannot be attributed to a run cannot be
    compared between runs, which was the entire point of recording it.
    """
    if _abort_check is None:
        return fn()

    outcome: dict = {}
    done = threading.Event()
    caller_context = contextvars.copy_context()

    def _target() -> None:
        try:
            outcome["result"] = caller_context.run(fn)
        except BaseException as e:
            outcome["error"] = e
        finally:
            done.set()

    thread = threading.Thread(target=_target, name="titan-interruptible-call", daemon=True)
    thread.start()

    while not done.wait(timeout=_POLL_INTERVAL_SECONDS):
        if abort_requested():
            raise WorkflowAborted("Application closed while a blocking call was in flight")

    if _cancel_requested:
        # Killing the child made the call return on its own before the poll saw the
        # flag; its outcome is a killed process, not an answer.
        raise WorkflowAborted("Workflow cancelled while a blocking call was in flight")
    if "error" in outcome:
        raise outcome["error"]
    return outcome["result"]
