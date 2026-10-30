"""Running a workflow run again from the pane: its failed jobs, or every job.

GitHub only accepts this once the run has finished. Sending blocks on the
network, so it runs through `m.run`; the pane shows it in flight and both run
lists are read again once it lands.
"""
from typing import Optional

from titan_cli.core.result import ClientError, ClientSuccess

PROGRESS = {"rerun_failed": "re-running failed jobs", "rerun_all": "re-running every job"}
VERB = {"rerun_failed": "re-run failed jobs of", "rerun_all": "re-run"}
DONE = {"rerun_failed": "Re-running failed jobs of", "rerun_all": "Re-running"}


def running(m, run_id: int) -> Optional[str]:
    """The action in flight on this run, if any."""
    return (m.state.get("run_acting") or {}).get(str(run_id))


def start(m, run_id: int, kind: str, label: str) -> None:
    """Claim the run and send on a background thread; a second press while it runs does nothing.

    The button's state is from the last repaint, so two quick presses both saw
    the run free: claiming in state here closes that window.
    """
    key = str(run_id)
    claimed = []

    def claim(all_):
        all_ = all_ or {}
        if all_.get(key):
            return all_
        claimed.append(True)
        return {**all_, key: kind}

    m.state.update("run_acting", claim, default={})
    if claimed:
        m.run(lambda: _send(m, run_id, kind, label))


def _send(m, run_id: int, kind: str, label: str) -> None:
    github = m.client("github")
    try:
        if github is None:
            raise RuntimeError("github plugin not available")
        result = github.rerun_failed_jobs(run_id) if kind == "rerun_failed" else github.rerun_workflow(run_id)
        match result:
            case ClientSuccess():
                m.ui.toast(f"{DONE[kind]} {label}")
                refresh(m)
            case ClientError(error_message=err):
                m.ui.toast(f"Could not {VERB[kind]} {label}: {err}", severity="error")
    except Exception as e:
        m.ui.toast(f"Could not {VERB[kind]} {label}: {e}", severity="error")
    finally:
        m.state.update("run_acting", lambda all_: {k: v for k, v in (all_ or {}).items() if k != str(run_id)}, default={})


def refresh(m) -> None:
    """Read both run lists again, so the row shows the run it now is."""
    for key in ("refresh_runs", "refresh_queue_runs"):
        reread = m.state.get(key)
        if reread is not None:
            reread()
