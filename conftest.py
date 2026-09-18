"""
Repo-wide pytest configuration.

Lives at the repository root so it applies to the plugin suites under
`plugins/*/tests/` as well as `tests/`.
"""

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def _isolate_titan_logs():
    """
    Send anything the suite logs to a temporary directory.

    Without this, running the tests writes into the user's real log at
    ~/.local/state/titan/logs/titan.log: one session there carried 219 error
    entries and 88 warnings that were all fixtures (PR #999, TEST-123,
    "credential missing"), plus an extra SESSION START banner per
    `setup_logging` call. Diagnosing a real run then means filtering out the
    test suite first, and a reader cannot reliably tell the two apart.
    """
    previous = os.environ.get("TITAN_LOG_DIR")
    with tempfile.TemporaryDirectory(prefix="titan-test-logs-") as tmp:
        os.environ["TITAN_LOG_DIR"] = tmp
        try:
            yield Path(tmp)
        finally:
            if previous is None:
                os.environ.pop("TITAN_LOG_DIR", None)
            else:
                os.environ["TITAN_LOG_DIR"] = previous
