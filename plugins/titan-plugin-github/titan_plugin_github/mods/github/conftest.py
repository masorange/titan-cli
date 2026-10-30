"""Shared by the mod's tests: the mod as Titan imports it, and PRs shaped like the client's."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from titan_cli.core.mods import import_mod

MOD_DIR = Path(__file__).resolve().parent


@pytest.fixture(scope="session")
def mod():
    return import_mod(MOD_DIR)


@pytest.fixture
def pr():
    def pr(number, review="review required", checks="passing", draft=False, conflicts=False, author="ana", age="2d ago"):
        return SimpleNamespace(
            number=number, title=f"PR {number}", author_name=author, review_status_summary=review,
            checks_state=checks, is_draft=draft, has_conflicts=conflicts, opened_age=age,
        )
    return pr
