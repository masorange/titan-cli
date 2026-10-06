"""Throwaway test that fails on purpose (see .github/workflows/diagnose-demo.yml)."""


def bump_minor(version: str) -> str:
    major, minor, _patch = version.split(".")
    return f"{major}.{minor}.0"  # bug on purpose: the minor is never incremented


def test_bump_minor_resets_patch():
    assert bump_minor("0.10.3") == "0.11.0"
