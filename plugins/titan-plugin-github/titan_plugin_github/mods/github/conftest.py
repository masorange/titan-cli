"""Shared by the mod's tests: the mod as Titan imports it."""
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
    def pr(number):
        return SimpleNamespace(number=number, title=f"PR {number}", url=f"https://github.com/o/r/pull/{number}")
    return pr
