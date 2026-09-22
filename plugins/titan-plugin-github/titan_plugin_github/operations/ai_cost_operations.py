"""Aggregation of what a review's AI calls reported about their own cost.

Pure functions over records the steps collect. No UI, no ctx, no I/O: the steps
gather, this decides what the numbers mean, and the caller logs them.

The central rule here is that **an unreported figure is never treated as zero**.
Three of the five CLIs that report anything (codex, agy) give token counts but no
price, and gemini reports nothing at all, so a naive sum would present a review that
cost real money as costing $0.00. Every total therefore travels with the count of
calls it could not account for, and a summary whose `calls_missing_cost` is non-zero
is a lower bound — which is what `cost_is_complete` exists to say out loud.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class AICallRecord:
    """One headless CLI call made during a review.

    `model_requested` is what Titan pinned (None when it had no opinion);
    `model_reported` is what the CLI says actually answered. They differ whenever a
    pin was missing or unavailable and the CLI fell back to its own default, which is
    the silent substitution that makes two runs incomparable — so both are kept.
    """

    phase: str
    cli: str
    prompt_chars: int
    duration_seconds: float
    succeeded: bool
    model_requested: Optional[str] = None
    model_reported: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    usage_source: Optional[str] = None

    @property
    def model_substituted(self) -> bool:
        """Whether the CLI answered with a model other than the one asked for."""
        if self.model_requested is None or self.model_reported is None:
            return False
        return self.model_requested not in self.model_reported


@dataclass(frozen=True)
class AIPhaseCost:
    """What one phase of the review spent."""

    phase: str
    calls: int
    failed_calls: int
    duration_seconds: float
    prompt_chars: int
    total_tokens: Optional[int]
    cost_usd: Optional[float]
    calls_missing_cost: int
    calls_missing_tokens: int


@dataclass(frozen=True)
class AIReviewCostSummary:
    """The whole review's spend, per phase and in total."""

    calls: int
    failed_calls: int
    duration_seconds: float
    prompt_chars: int
    total_tokens: Optional[int]
    cost_usd: Optional[float]
    calls_missing_cost: int
    calls_missing_tokens: int
    phases: list[AIPhaseCost] = field(default_factory=list)
    clis: list[str] = field(default_factory=list)
    models_reported: list[str] = field(default_factory=list)
    substituted_model_calls: int = 0

    @property
    def cost_is_complete(self) -> bool:
        """True only when every call priced itself.

        When False, `cost_usd` is a LOWER BOUND and must be presented as one. This is
        the difference between "this review cost $1.20" and "this review cost at least
        $1.20, and 4 of its 11 calls do not report a price."
        """
        return self.calls > 0 and self.calls_missing_cost == 0

    @property
    def cost_per_call_usd(self) -> Optional[float]:
        """Average price across the calls that actually reported one.

        Divided by the priced calls, not by all of them: dividing by calls that never
        reported would drag the average toward zero and make sessions look cheaper
        than they are — the opposite of what this number is for.
        """
        priced = self.calls - self.calls_missing_cost
        if priced <= 0 or self.cost_usd is None:
            return None
        return self.cost_usd / priced


def _sum_optional(values: list[Optional[int]]) -> Optional[int]:
    """Sum the values that exist, or None when none of them do.

    None rather than 0 for an all-absent list: zero would assert that nothing was
    consumed, which is a different claim from "nobody told us".
    """
    present = [v for v in values if v is not None]
    return sum(present) if present else None


def _sum_optional_float(values: list[Optional[float]]) -> Optional[float]:
    present = [v for v in values if v is not None]
    return sum(present) if present else None


def summarize_ai_calls(records: list[AICallRecord]) -> AIReviewCostSummary:
    """Fold call records into per-phase and overall totals.

    Phases keep first-seen order, which is execution order, so the summary reads the
    way the review ran rather than alphabetically.
    """
    if not records:
        return AIReviewCostSummary(
            calls=0,
            failed_calls=0,
            duration_seconds=0.0,
            prompt_chars=0,
            total_tokens=None,
            cost_usd=None,
            calls_missing_cost=0,
            calls_missing_tokens=0,
        )

    phase_order: list[str] = []
    by_phase: dict[str, list[AICallRecord]] = {}
    for record in records:
        if record.phase not in by_phase:
            phase_order.append(record.phase)
            by_phase[record.phase] = []
        by_phase[record.phase].append(record)

    phases = [_phase_cost(phase, by_phase[phase]) for phase in phase_order]

    clis: list[str] = []
    models: list[str] = []
    for record in records:
        if record.cli not in clis:
            clis.append(record.cli)
        if record.model_reported and record.model_reported not in models:
            models.append(record.model_reported)

    return AIReviewCostSummary(
        calls=len(records),
        failed_calls=sum(1 for r in records if not r.succeeded),
        duration_seconds=round(sum(r.duration_seconds for r in records), 3),
        prompt_chars=sum(r.prompt_chars for r in records),
        total_tokens=_sum_optional([r.total_tokens for r in records]),
        cost_usd=_round_cost(_sum_optional_float([r.cost_usd for r in records])),
        calls_missing_cost=sum(1 for r in records if r.cost_usd is None),
        calls_missing_tokens=sum(1 for r in records if r.total_tokens is None),
        phases=phases,
        clis=clis,
        models_reported=models,
        substituted_model_calls=sum(1 for r in records if r.model_substituted),
    )


def _phase_cost(phase: str, records: list[AICallRecord]) -> AIPhaseCost:
    return AIPhaseCost(
        phase=phase,
        calls=len(records),
        failed_calls=sum(1 for r in records if not r.succeeded),
        duration_seconds=round(sum(r.duration_seconds for r in records), 3),
        prompt_chars=sum(r.prompt_chars for r in records),
        total_tokens=_sum_optional([r.total_tokens for r in records]),
        cost_usd=_round_cost(_sum_optional_float([r.cost_usd for r in records])),
        calls_missing_cost=sum(1 for r in records if r.cost_usd is None),
        calls_missing_tokens=sum(1 for r in records if r.total_tokens is None),
    )


def _round_cost(value: Optional[float]) -> Optional[float]:
    """Six decimals: enough for a sub-cent call, short enough to read in a log line."""
    return None if value is None else round(value, 6)


def format_cost_summary(summary: AIReviewCostSummary) -> str:
    """One human-readable line, honest about what it does not know.

    Used for the debug log and available to any future UI. It says "at least" whenever
    a call went unpriced, because a total that silently omits calls reads as complete.
    """
    if summary.calls == 0:
        return "no AI calls"

    parts = [f"{summary.calls} call(s)", f"{summary.duration_seconds:.1f}s"]
    if summary.total_tokens is not None:
        parts.append(f"{summary.total_tokens:,} tokens")
    if summary.cost_usd is not None:
        prefix = "" if summary.cost_is_complete else "≥"
        parts.append(f"{prefix}${summary.cost_usd:.4f}")
    if summary.calls_missing_cost:
        parts.append(f"{summary.calls_missing_cost} call(s) report no price")
    if summary.failed_calls:
        parts.append(f"{summary.failed_calls} failed")
    return " · ".join(parts)
