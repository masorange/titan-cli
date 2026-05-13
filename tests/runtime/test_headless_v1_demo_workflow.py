import json
from pathlib import Path

from typer.testing import CliRunner

from titan_cli.cli import app


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_headless_v1_demo_run_result_mode_completes() -> None:
    result = CliRunner().invoke(
        app,
        [
            "headless",
            "runs",
            "start",
            "headless-v1-demo",
            "--project-path",
            str(REPO_ROOT),
            "--prompt-responses-json",
            "[true]",
            "--mode",
            "run_result",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "completed"
    assert [step["id"] for step in payload["steps"]] == [
        "emit-text",
        "confirm-continue",
        "emit-markdown",
    ]
    assert payload["steps"][0]["outputs"][0]["format"] == "text"
    assert payload["steps"][-1]["outputs"][0]["format"] == "markdown"
    assert payload["result"]["format"] == "markdown"


def test_headless_v1_demo_event_stream_round_trip_completes() -> None:
    result = CliRunner().invoke(
        app,
        [
            "headless",
            "runs",
            "start",
            "headless-v1-demo",
            "--project-path",
            str(REPO_ROOT),
            "--mode",
            "event_stream",
        ],
        input='{"type":"submit_prompt_response","payload":{"prompt_id":"confirm-continue:confirm","value":true}}\n',
    )

    assert result.exit_code == 0
    lines = [json.loads(line) for line in result.stdout.strip().splitlines()]
    event_types = [line["type"] for line in lines]
    assert "run_started" in event_types
    assert "prompt_requested" in event_types
    assert "run_completed" in event_types
    assert any(
        line["type"] == "prompt_requested"
        and line["payload"]["prompt"]["prompt_id"] == "confirm-continue:confirm"
        for line in lines
    )


def test_headless_v1_demo_event_stream_cancel_run() -> None:
    result = CliRunner().invoke(
        app,
        [
            "headless",
            "runs",
            "start",
            "headless-v1-demo",
            "--project-path",
            str(REPO_ROOT),
            "--mode",
            "event_stream",
        ],
        input='{"type":"cancel_run","payload":{"reason":"user_cancelled_demo"}}\n',
    )

    assert result.exit_code == 0
    lines = [json.loads(line) for line in result.stdout.strip().splitlines()]
    event_types = [line["type"] for line in lines]
    assert "prompt_requested" in event_types
    assert event_types[-1] == "run_cancelled"
    assert lines[-1]["payload"]["message"] == "user_cancelled_demo"
