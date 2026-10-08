"""Explaining why a CI job failed: the log excerpt, the AI answer and the report."""
from titan_plugin_github.models.view import UIJobDiagnosis
from titan_plugin_github.operations import (
    build_job_diagnosis_prompt,
    extract_failure_excerpt,
    format_job_diagnoses,
    parse_job_diagnosis,
)

LOG = "\n".join(
    ["2026-10-06T10:00:00.0000000Z noise line"] * 2000
    + [
        "2026-10-06T10:00:01.0000000Z > Task :app:testDebugUnitTest FAILED",
        "2026-10-06T10:00:01.0000000Z FooTest > bar FAILED at FooTest.kt:42",
    ]
    + ["2026-10-06T10:00:00.0000000Z noise line"] * 2000
    + ["2026-10-06T10:00:02.0000000Z tail"] * 5
)


def test_excerpt_keeps_failures_and_the_tail_without_timestamps():
    excerpt = extract_failure_excerpt(LOG)

    assert "> Task :app:testDebugUnitTest FAILED" in excerpt
    assert "2026-10-06T" not in excerpt
    assert excerpt.count("noise line") < 400
    assert excerpt.endswith("tail")


def test_excerpt_is_cut_to_max_chars_keeping_the_end():
    assert extract_failure_excerpt(LOG, max_chars=10) == extract_failure_excerpt(LOG)[-10:]


def test_prompt_names_the_job_and_carries_the_excerpt():
    prompt, system = build_job_diagnosis_prompt("test", "the excerpt")

    assert prompt.startswith("Job: test") and "the excerpt" in prompt
    assert '"quote"' in system


def test_a_quote_that_is_not_in_the_log_is_flagged():
    excerpt = extract_failure_excerpt(LOG)
    real = parse_job_diagnosis(
        "test", '{"cause": "FooTest.bar fails", "where": "FooTest.kt:42", "quote": "FooTest > bar FAILED at FooTest.kt:42"}', excerpt
    )
    made_up = parse_job_diagnosis("test", 'Sure! {"cause": "x", "quote": "NullPointerException in Bar"}', excerpt)
    fenced = parse_job_diagnosis("test", '```json\n{"cause": "y"}\n```', excerpt)
    prose = parse_job_diagnosis("test", "The build failed because of a test.", excerpt)

    assert (real.where, real.is_quote_in_log) == ("FooTest.kt:42", True)
    assert made_up.is_quote_in_log is False
    assert fenced.cause == "y"
    assert prose.cause == "The build failed because of a test."


def test_report_lists_each_job_and_warns_on_made_up_quotes():
    text = format_job_diagnoses(
        7, "Fix login", [UIJobDiagnosis("build", "Gradle failed", "a.kt:1", "boom", is_quote_in_log=False)], "Claude"
    )

    assert text.splitlines()[:4] == ["PR #7 Fix login", "Diagnosed by Claude", "", "✗ build"]
    assert "> boom" in text and "do not trust the cause" in text
