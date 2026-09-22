"""Tests for ai_cost_operations — what a review's AI calls reported spending.

The behaviour under test is almost entirely about one distinction: a figure the CLI
did not report is NOT zero. Three of the CLIs Titan can review with report tokens but
no price, and one reports nothing at all, so every total here has to be able to say
"this is a lower bound" rather than quietly presenting a partial sum as the answer.
"""

from titan_plugin_github.operations.ai_cost_operations import (
    AICallRecord,
    format_cost_summary,
    summarize_ai_calls,
)


def _call(**overrides) -> AICallRecord:
    base = dict(
        phase="code_review_findings",
        cli="claude",
        prompt_chars=1000,
        duration_seconds=10.0,
        succeeded=True,
    )
    base.update(overrides)
    return AICallRecord(**base)


class TestEmptyReview:

    def test_no_calls_summarizes_to_nothing_rather_than_to_zero_cost(self):
        summary = summarize_ai_calls([])

        assert summary.calls == 0
        assert summary.cost_usd is None
        assert summary.total_tokens is None
        # A review with no calls has not "completely accounted for its cost" - there is
        # nothing to account for, and claiming completeness would let an AI-off run
        # read as a verified $0.00.
        assert summary.cost_is_complete is False
        assert format_cost_summary(summary) == "no AI calls"


class TestTotals:

    def test_sums_duration_prompt_chars_tokens_and_cost(self):
        summary = summarize_ai_calls([
            _call(duration_seconds=10.0, prompt_chars=1000, total_tokens=100, cost_usd=0.10),
            _call(duration_seconds=5.5, prompt_chars=500, total_tokens=50, cost_usd=0.05),
        ])

        assert summary.calls == 2
        assert summary.duration_seconds == 15.5
        assert summary.prompt_chars == 1500
        assert summary.total_tokens == 150
        assert summary.cost_usd == 0.15
        assert summary.cost_is_complete is True

    def test_counts_failed_calls_without_excluding_their_spend(self):
        """A failed call still consumed tokens; dropping it would understate a review
        that had a retry in it."""
        summary = summarize_ai_calls([
            _call(cost_usd=0.10, total_tokens=100),
            _call(succeeded=False, cost_usd=0.04, total_tokens=40),
        ])

        assert summary.failed_calls == 1
        assert summary.cost_usd == 0.14
        assert summary.total_tokens == 140


class TestUnreportedFiguresAreNotZero:

    def test_a_partial_sum_is_flagged_as_incomplete(self):
        summary = summarize_ai_calls([
            _call(cli="claude", cost_usd=0.20, total_tokens=100),
            _call(cli="codex", cost_usd=None, total_tokens=5000),
        ])

        assert summary.cost_usd == 0.20
        assert summary.calls_missing_cost == 1
        assert summary.cost_is_complete is False

    def test_all_prices_absent_yields_none_not_zero(self):
        summary = summarize_ai_calls([_call(cli="codex"), _call(cli="agy")])

        assert summary.cost_usd is None
        assert summary.calls_missing_cost == 2
        assert summary.cost_per_call_usd is None

    def test_all_token_counts_absent_yields_none_not_zero(self):
        summary = summarize_ai_calls([_call(cli="gemini"), _call(cli="gemini")])

        assert summary.total_tokens is None
        assert summary.calls_missing_tokens == 2

    def test_average_divides_by_priced_calls_only(self):
        """Dividing by every call would drag the average toward zero and make sessions
        look cheaper than they are - the opposite of what this number is for."""
        summary = summarize_ai_calls([
            _call(cost_usd=0.20),
            _call(cost_usd=0.20),
            _call(cost_usd=None),
            _call(cost_usd=None),
        ])

        assert summary.cost_usd == 0.40
        assert summary.cost_per_call_usd == 0.20

    def test_a_reported_zero_price_counts_as_reported(self):
        """A free or local model's zero is a real price, not a silence."""
        summary = summarize_ai_calls([_call(cli="opencode", cost_usd=0.0)])

        assert summary.calls_missing_cost == 0
        assert summary.cost_is_complete is True
        assert summary.cost_usd == 0.0


class TestPhases:

    def test_phases_keep_execution_order(self):
        summary = summarize_ai_calls([
            _call(phase="code_review_plan"),
            _call(phase="code_review_findings"),
            _call(phase="code_review_findings"),
        ])

        assert [p.phase for p in summary.phases] == ["code_review_plan", "code_review_findings"]
        assert [p.calls for p in summary.phases] == [1, 2]

    def test_each_phase_carries_its_own_missing_cost_count(self):
        summary = summarize_ai_calls([
            _call(phase="code_review_plan", cli="codex", cost_usd=None),
            _call(phase="code_review_findings", cli="claude", cost_usd=0.30),
        ])

        plan, findings = summary.phases
        assert plan.cost_usd is None and plan.calls_missing_cost == 1
        assert findings.cost_usd == 0.30 and findings.calls_missing_cost == 0


class TestModelSubstitution:

    def test_a_cli_answering_with_another_model_is_counted(self):
        """The silent fallback to a CLI default is what makes two runs incomparable, so
        it is surfaced rather than inferred later from the logs."""
        summary = summarize_ai_calls([
            _call(model_requested="haiku", model_reported="claude-opus-5[1m]"),
            _call(model_requested="opus", model_reported="claude-opus-5[1m]"),
        ])

        assert summary.substituted_model_calls == 1
        assert summary.models_reported == ["claude-opus-5[1m]"]

    def test_nothing_is_claimed_when_either_side_is_unknown(self):
        assert _call(model_requested=None, model_reported="grok-4.7").model_substituted is False
        assert _call(model_requested="opus", model_reported=None).model_substituted is False

    def test_clis_are_listed_in_first_seen_order_without_repeats(self):
        summary = summarize_ai_calls([_call(cli="claude"), _call(cli="codex"), _call(cli="claude")])

        assert summary.clis == ["claude", "codex"]


class TestHumanReadableLine:

    def test_a_complete_total_is_stated_plainly(self):
        line = format_cost_summary(summarize_ai_calls([_call(cost_usd=0.25, total_tokens=1234)]))

        assert "$0.2500" in line
        assert "≥" not in line
        assert "1,234 tokens" in line

    def test_an_incomplete_total_is_marked_as_a_lower_bound(self):
        """A total that silently omits calls reads as complete, which is the one thing
        this line must never do."""
        line = format_cost_summary(summarize_ai_calls([
            _call(cost_usd=0.25),
            _call(cli="codex", cost_usd=None),
        ]))

        assert "≥$0.2500" in line
        assert "1 call(s) report no price" in line

    def test_failures_are_named(self):
        line = format_cost_summary(summarize_ai_calls([_call(succeeded=False, cost_usd=0.01)]))

        assert "1 failed" in line
