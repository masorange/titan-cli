"""Shared by every test of the mod, wherever it lives: the mod as Titan imports it, and fakes."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from titan_cli.core.mods import Box, Button, Link, Text, import_mod

MOD_DIR = Path(__file__).resolve().parent


@pytest.fixture(scope="session")
def mod():
    return import_mod(MOD_DIR)


@pytest.fixture
def flatten():
    def flatten(element):
        """Every string a tree would show, in order."""
        if isinstance(element, str):
            return [element]
        if isinstance(element, Text):
            return ["".join("".join(flatten(p)) for p in element.parts)]
        if isinstance(element, (Button, Link)):
            return [element.label]
        if isinstance(element, Box):
            lines = [line for child in element.children for line in flatten(child)]
            # A row is one line in the pane: the first child at the left, the rest at the right.
            return [" ".join(lines)] if element.row else lines
        return []
    return flatten


@pytest.fixture
def pr():
    """A github plugin PR (the fields the mod reads of a UIPullRequest) as the client returns it."""
    from titan_plugin_github.models.view import UIFailedCheck

    def pr(number, review="review required", checks="passing", failed=0, draft=False, conflicts=False,
           reviewers=(), assignees=(), labels=()):
        return SimpleNamespace(
            number=number, title=f"PR {number}", author_name="ana", is_draft=draft, review_status_summary=review,
            checks_state=checks, has_conflicts=conflicts, url=f"https://github.com/o/r/pull/{number}",
            failed_checks=[UIFailedCheck(f"job{i}", f"https://github.com/o/r/actions/runs/1/job/{i}", job_id=i) for i in range(failed)],
            reviewers=list(reviewers), assignees=list(assignees), labels=list(labels),
            branch_info=f"feat/{number} → develop", stats="+10 −2", files_changed=3,
            additions=10, deletions=2,
            opened_age="5d ago", updated_age="2h ago",
        )
    return pr
