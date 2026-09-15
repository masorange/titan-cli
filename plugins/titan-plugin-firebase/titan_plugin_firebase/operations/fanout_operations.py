"""
Aggregating a change across several brands.

Each brand is its own Firebase project with its own template, so the same
edit can be valid in nine brands and impossible in the tenth — a missing
parameter, a condition that does not exist there, a value that clashes with a
different declared type. A fan-out must therefore report per brand and never
abandon the rest because one failed.

Pure functions: no context, no UI, no network.
"""

from __future__ import annotations

from typing import Iterable

from ..models.view import UIFanoutEntry, UIFanoutOutcome


def plan_summary(entries: Iterable[UIFanoutEntry]) -> dict[str, int]:
    """Count the entries of a plan by status."""
    counts = {"ready": 0, "noop": 0, "error": 0}
    for entry in entries:
        counts[entry.status] = counts.get(entry.status, 0) + 1
    return counts


def publishable_entries(entries: Iterable[UIFanoutEntry]) -> list[UIFanoutEntry]:
    """Return only the entries whose publish would change something."""
    return [entry for entry in entries if entry.is_publishable]


def select_entries(
    entries: Iterable[UIFanoutEntry],
    project_ids: Iterable[str],
) -> list[UIFanoutEntry]:
    """Keep the publishable entries the user chose, in plan order."""
    chosen = set(project_ids)
    return [
        entry
        for entry in entries
        if entry.is_publishable and entry.target.project_id in chosen
    ]


def outcome_summary(outcomes: Iterable[UIFanoutOutcome]) -> dict[str, int]:
    """Count published and failed brands."""
    published = 0
    failed = 0
    for outcome in outcomes:
        if outcome.succeeded:
            published += 1
        else:
            failed += 1
    return {"published": published, "failed": failed}


def describe_plan(entries: Iterable[UIFanoutEntry]) -> list[list[str]]:
    """Build the rows of the plan table: brand, project, status, detail."""
    return [
        [
            entry.target.brand or "—",
            entry.target.project_id,
            entry.status,
            entry.detail,
        ]
        for entry in entries
    ]


def describe_outcomes(outcomes: Iterable[UIFanoutOutcome]) -> list[list[str]]:
    """Build the rows of the result table: brand, project, result, detail."""
    return [
        [
            outcome.target.brand or "—",
            outcome.target.project_id,
            "ok" if outcome.succeeded else "error",
            outcome.detail,
        ]
        for outcome in outcomes
    ]
