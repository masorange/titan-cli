"""Shared by every test of the workspace: its picks go to a temporary store, never the user's own."""
import pytest

from titan_cli.core.mods import store


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "STORE_DIR", tmp_path)
