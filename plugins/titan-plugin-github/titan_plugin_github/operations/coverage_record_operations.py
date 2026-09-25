"""The filled-in review checklist, kept for a while after the review ends.

The checklist travels in the prompt and the session writes nothing, so without a record
the only trace of what happened to each file is scattered across log lines. The record is
one small JSON per review: every checklist row with what the session said about it, plus
what it established and left open. It lives outside the repository and is pruned on every
write, so it never accumulates.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from .findings_operations import normalize_finding_path

COVERAGE_RECORD_ROOT = Path.home() / ".titan" / "tmp" / "review-checklists"
COVERAGE_RECORD_MAX_AGE_DAYS = 7
COVERAGE_RECORDS_KEPT = 20


def build_coverage_record(
    batch,
    reviewed: list[dict],
    dismissed: list[dict],
    findings: list,
    session_notes: dict[str, list[str]],
    created_at: datetime,
    focus: Optional[list[dict]] = None,
) -> dict[str, Any]:
    """Every checklist row with its outcome: what the session said, or that it said nothing."""
    focus_why = {normalize_finding_path(item["path"]): item.get("why", "") for item in focus or []}
    notes = {normalize_finding_path(item["path"]): item.get("note", "") for item in reviewed}
    reasons = {normalize_finding_path(item["path"]): item.get("reason", "") for item in dismissed}
    titles: dict[str, list[str]] = {}
    for finding in findings or []:
        if isinstance(finding, dict):
            path = normalize_finding_path(finding.get("path") or "")
            titles.setdefault(path, []).append(finding.get("title") or "")

    rows: list[dict[str, Any]] = []
    for line in batch.change_shape:
        columns = [column.strip() for column in line.split(" | ")]
        path = columns[0]
        covered_by = columns[2] if len(columns) > 2 else ""
        key = normalize_finding_path(path)
        row: dict[str, Any] = {"path": path, "covered_by": covered_by}
        if covered_by.startswith("YOU"):
            if key in titles:
                row["state"] = "findings"
            elif key in reasons:
                row["state"] = "dismissed"
            elif key in notes:
                row["state"] = "reviewed"
            else:
                row["state"] = "not accounted for"
            if key in notes:
                row["note"] = notes[key]
            if key in reasons:
                row["dismissed"] = reasons[key]
            if key in titles:
                row["findings"] = titles[key]
            if key in focus_why:
                row["focus"] = focus_why[key]
        rows.append(row)

    pr = batch.pr_manifest
    return {
        "pr": pr.number if pr else None,
        "title": pr.title if pr else None,
        "created_at": created_at.isoformat(timespec="seconds"),
        "rows": rows,
        "key_facts": list(session_notes.get("key_facts", [])),
        "open_suspicions": list(session_notes.get("open_suspicions", [])),
    }


def coverage_record_path(project_name: str, pr_number: Optional[int], created_at: datetime) -> Path:
    safe_project = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in project_name) or "project"
    return (
        COVERAGE_RECORD_ROOT
        / safe_project
        / f"pr-{pr_number if pr_number is not None else 'unknown'}-{created_at:%Y%m%d-%H%M%S}.json"
    )


def select_stale_records(
    records: list[tuple[str, float]],
    now: datetime,
    max_age_days: int = COVERAGE_RECORD_MAX_AGE_DAYS,
    keep: int = COVERAGE_RECORDS_KEPT,
) -> list[str]:
    """Which records to delete: older than `max_age_days`, or beyond the `keep` newest."""
    cutoff = (now - timedelta(days=max_age_days)).timestamp()
    newest_first = sorted(records, key=lambda record: record[1], reverse=True)
    return [
        path
        for index, (path, modified) in enumerate(newest_first)
        if index >= keep or modified < cutoff
    ]
