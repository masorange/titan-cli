"""Shared by every test of the mod, wherever it lives: the mod as Titan imports it, and fakes."""
from pathlib import Path

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
            return flatten(element.label) if isinstance(element.label, Text) else [element.label]
        if isinstance(element, Box):
            return [line for child in element.children for line in flatten(child)]
        return []
    return flatten
