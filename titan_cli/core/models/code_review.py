"""
Data models for the iterative code review feature.

These models represent the state of a code review session:
- ReviewFinding: a single issue found during initial analysis
- RefinementIteration: one user→agent exchange within a comment session
- CommentReviewSession: full review of one PR comment thread
- CodeReviewSessionResult: aggregated result across all comments
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Dict, List, Optional


class ReviewSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


_SEVERITY_EMOJI: Dict[ReviewSeverity, str] = {
    ReviewSeverity.CRITICAL: "🔴",
    ReviewSeverity.HIGH: "🟡",
    ReviewSeverity.MEDIUM: "🟢",
    ReviewSeverity.LOW: "🟠",
}


@dataclass
class ReviewFinding:
    """A single issue found during initial AI analysis of the PR."""

    severity: ReviewSeverity
    title: str
    description: str
    file: Optional[str] = None
    line: Optional[int] = None
    suggestion: Optional[str] = None

    @property
    def emoji(self) -> str:
        return _SEVERITY_EMOJI.get(self.severity, "⚪")

    @property
    def display_header(self) -> str:
        location = f" — `{self.file}`" + (f":{self.line}" if self.line else "") if self.file else ""
        return f"{self.emoji} **{self.severity.upper()}**: {self.title}{location}"


class UserDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"


@dataclass
class RefinementIteration:
    """One round of the user→agent refinement loop for a single comment."""

    iteration_number: int
    agent_suggestion: str
    timestamp: datetime = field(default_factory=datetime.now)
    user_feedback: Optional[str] = None  # None on the first (automatic) iteration


@dataclass
class CommentReviewSession:
    """Tracks the full review of one PR comment thread."""

    comment_id: int
    original_comment: str
    existing_replies: List[str] = field(default_factory=list)
    iterations: List[RefinementIteration] = field(default_factory=list)
    user_decision: UserDecision = UserDecision.PENDING
    final_suggestion: Optional[str] = None

    @property
    def current_suggestion(self) -> Optional[str]:
        """The most recent agent suggestion, or None if no iteration yet."""
        return self.iterations[-1].agent_suggestion if self.iterations else None

    @property
    def iteration_count(self) -> int:
        return len(self.iterations)

    @property
    def is_decided(self) -> bool:
        return self.user_decision != UserDecision.PENDING


@dataclass
class CodeReviewSessionResult:
    """Aggregated result of reviewing all comment threads in a PR."""

    findings_initial: List[ReviewFinding] = field(default_factory=list)
    comment_sessions: Dict[int, CommentReviewSession] = field(default_factory=dict)

    @property
    def total_iterations(self) -> int:
        return sum(s.iteration_count for s in self.comment_sessions.values())

    @property
    def approved_sessions(self) -> List[CommentReviewSession]:
        return [s for s in self.comment_sessions.values() if s.user_decision == UserDecision.APPROVED]

    @property
    def approval_rate(self) -> float:
        decided = [s for s in self.comment_sessions.values() if s.is_decided]
        if not decided:
            return 0.0
        approved = sum(1 for s in decided if s.user_decision == UserDecision.APPROVED)
        return approved / len(decided)
