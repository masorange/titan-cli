from subprocess import CompletedProcess, TimeoutExpired
from unittest.mock import MagicMock

from titan_plugin_firebase import auth


def _completed(stdout: str = "", returncode: int = 0) -> CompletedProcess:
    return CompletedProcess(args=["gcloud"], returncode=returncode, stdout=stdout, stderr="")


def test_is_gcloud_installed_when_version_succeeds(monkeypatch) -> None:
    run = MagicMock(return_value=_completed())
    monkeypatch.setattr(auth.subprocess, "run", run)

    assert auth.is_gcloud_installed() is True
    assert run.call_args.args[0] == ["gcloud", "--version"]


def test_is_gcloud_installed_returns_false_when_missing(monkeypatch) -> None:
    run = MagicMock(side_effect=FileNotFoundError)
    monkeypatch.setattr(auth.subprocess, "run", run)

    assert auth.is_gcloud_installed() is False


def test_get_active_account_returns_account(monkeypatch) -> None:
    monkeypatch.setattr(
        auth.subprocess,
        "run",
        MagicMock(return_value=_completed("user@example.com\n")),
    )

    assert auth.get_active_account() == "user@example.com"


def test_get_active_account_returns_none_on_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        auth.subprocess,
        "run",
        MagicMock(return_value=_completed("", returncode=1)),
    )

    assert auth.get_active_account() is None


def test_get_adc_access_token_returns_token(monkeypatch) -> None:
    run = MagicMock(return_value=_completed("ya29.token\n"))
    monkeypatch.setattr(auth.subprocess, "run", run)

    assert auth.get_adc_access_token() == "ya29.token"
    assert run.call_args.args[0] == [
        "gcloud",
        "auth",
        "application-default",
        "print-access-token",
    ]


def test_get_adc_access_token_returns_none_on_timeout(monkeypatch) -> None:
    monkeypatch.setattr(
        auth.subprocess,
        "run",
        MagicMock(side_effect=TimeoutExpired(cmd="gcloud", timeout=10)),
    )

    assert auth.get_adc_access_token() is None


def test_adc_login_hint_returns_exact_command() -> None:
    assert auth.adc_login_hint() == "gcloud auth application-default login"
