"""The filled checklist kept after a review: its content, its location and its pruning."""

import json
import os
from datetime import datetime, timedelta
from types import SimpleNamespace

from titan_plugin_github.models.review_models import FocusContextBatch, PullRequestManifest
from titan_plugin_github.operations import coverage_record_operations
from titan_plugin_github.operations.coverage_record_operations import (
    build_coverage_record,
    coverage_record_path,
    select_stale_records,
)

NOW = datetime(2026, 9, 25, 10, 30, 0)


def _batch() -> FocusContextBatch:
    return FocusContextBatch(
        batch_id="deep_1",
        change_shape=[
            "core.py | role=business_logic | YOU: review | +4/-1",
            "steps.py | role=business_logic | YOU: review | +2/-0",
            "quiet.py | role=business_logic | YOU: review | +1/-0",
            "deploy.yml | role=config | YOU: triage question | +1/-1",
            "strings.xml | role=static | triage: Only translations | +9/-0",
        ],
        pr_manifest=PullRequestManifest(
            number=236, title="Firebase plugin", description="", base="main", head="f", author="a"
        ),
    )


def test_every_row_says_what_happened_to_its_file():
    record = build_coverage_record(
        _batch(),
        reviewed=[{"path": "core.py", "note": "checked the guard"}, {"path": "steps.py", "note": "fine"}],
        dismissed=[{"path": "deploy.yml", "reason": "the key is still read"}],
        findings=[{"path": "core.py", "title": "Guard inverted"}],
        session_notes={"key_facts": ["fanout takes condition"], "open_suspicions": ["sync may race"]},
        created_at=NOW,
    )

    rows = {row["path"]: row for row in record["rows"]}
    assert rows["core.py"]["state"] == "findings"
    assert rows["core.py"]["findings"] == ["Guard inverted"]
    assert rows["core.py"]["note"] == "checked the guard"
    assert rows["steps.py"]["state"] == "reviewed"
    assert rows["quiet.py"]["state"] == "not accounted for"
    assert rows["deploy.yml"]["state"] == "dismissed"
    # Rows that were not the session's task keep what the triage said, and no state.
    assert rows["strings.xml"] == {"path": "strings.xml", "covered_by": "triage: Only translations"}
    assert record["pr"] == 236
    assert record["key_facts"] == ["fanout takes condition"]
    assert record["open_suspicions"] == ["sync may race"]


def test_records_live_outside_the_repo_per_project_and_pr():
    path = coverage_record_path("my repo", 236, NOW)

    assert path.parent == coverage_record_operations.COVERAGE_RECORD_ROOT / "my_repo"
    assert path.name == "pr-236-20260925-103000.json"


def test_pruning_drops_what_is_old_and_what_is_beyond_the_newest_kept():
    records = [(f"r{i}.json", (NOW - timedelta(hours=i)).timestamp()) for i in range(25)]
    records.append(("old.json", (NOW - timedelta(days=8)).timestamp()))

    stale = select_stale_records(records, NOW, max_age_days=7, keep=20)

    assert "old.json" in stale
    assert set(stale) - {"old.json"} == {f"r{i}.json" for i in range(20, 25)}
    assert select_stale_records([("new.json", NOW.timestamp())], NOW) == []


def test_the_review_step_saves_the_record_and_prunes(tmp_path, monkeypatch):
    from titan_plugin_github.steps import code_review_steps

    monkeypatch.setattr(coverage_record_operations, "COVERAGE_RECORD_ROOT", tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    old = project / "pr-1-20000101-000000.json"
    old.write_text("{}")
    os.utime(old, (0, 0))
    ctx = SimpleNamespace(
        data={"project_root": str(project)},
        textual=SimpleNamespace(dim_text=lambda text: None),
    )

    code_review_steps._save_coverage_record(
        ctx, [_batch()], [{"path": "core.py", "note": "ok"}], [], [], {"key_facts": [], "open_suspicions": []}
    )

    saved = list(project.glob("pr-236-*.json"))
    assert len(saved) == 1
    assert json.loads(saved[0].read_text())["rows"][0]["state"] == "reviewed"
    assert not old.exists()


def test_the_record_marks_the_files_reviewed_in_depth():
    """So a missed defect can be placed: inside the focus is a depth problem, outside it
    the criteria chose wrong."""
    record = build_coverage_record(
        _batch(),
        reviewed=[{"path": "core.py", "note": "checked load() with a missing file"}],
        dismissed=[],
        findings=[],
        session_notes={},
        created_at=NOW,
        focus=[{"path": "core.py", "why": "writes to production"}],
    )

    rows = {row["path"]: row for row in record["rows"]}
    assert rows["core.py"]["focus"] == "writes to production"
    assert "focus" not in rows["steps.py"]
