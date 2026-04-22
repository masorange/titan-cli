"""Tests for Titan logging mode detection."""

from titan_cli.core.logging.config import _is_development_mode


def test_development_mode_detected_for_titan_dev(monkeypatch) -> None:
    """titan-dev should enable development logging without --debug."""
    monkeypatch.delenv("TITAN_ENV", raising=False)
    monkeypatch.setattr("sys.argv", ["titan-dev"])

    assert _is_development_mode(debug=False) is True


def test_development_mode_disabled_for_regular_titan_without_flags(monkeypatch) -> None:
    """Regular titan should stay in production mode without explicit opt-in."""
    monkeypatch.delenv("TITAN_ENV", raising=False)
    monkeypatch.setattr("sys.argv", ["titan"])

    assert _is_development_mode(debug=False) is False
