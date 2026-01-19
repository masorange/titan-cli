# plugins/titan-plugin-jira/titan_plugin_jira/agents/token_tracker.py
"""
Centralized token tracking for JiraAgent.

Addresses PR #74 comment: "Token Tracking Inconsistente"
Provides consistent, transparent token usage tracking across all AI operations.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from enum import Enum

MAX_BUDGET_MULTIPLIER = 10

class OperationType(Enum):
    """Types of AI operations that consume tokens."""
    REQUIREMENTS_EXTRACTION = "requirements_extraction"
    RISK_ANALYSIS = "risk_analysis"
    DEPENDENCY_DETECTION = "dependency_detection"
    SUBTASK_SUGGESTION = "subtask_suggestion"
    COMMENT_GENERATION = "comment_generation"
    DESCRIPTION_ENHANCEMENT = "description_enhancement"
    SMART_LABELING = "smart_labeling"


@dataclass
class TokenUsage:
    """Record of token usage for a single operation."""
    operation: OperationType
    tokens_used: int
    issue_key: Optional[str] = None
    success: bool = True
    error: Optional[str] = None


@dataclass
class TokenBudget:
    """
    Token budget configuration for different operation types.

    Based on PR #74 comment about hardcoded magic numbers.
    Centralizes token allocation instead of using `max_tokens // 4` throughout code.
    """
    # Base max_tokens from config (e.g., 2000)
    base_max_tokens: int

    # Multipliers for different operations (0.0 to 1.0)
    requirements_multiplier: float = 1.0  # Full budget
    risk_multiplier: float = 1.0  # Full budget
    dependency_multiplier: float = 0.25  # 1/4 budget (was hardcoded as // 4)
    subtask_multiplier: float = 1.0  # Full budget
    comment_multiplier: float = 0.5  # 1/2 budget (was hardcoded as // 2)
    description_multiplier: float = 1.0  # Full budget
    labeling_multiplier: float = 0.25  # 1/4 budget

    def get_budget(self, operation: OperationType) -> int:
        """
        Get token budget for a specific operation.

        Args:
            operation: The type of operation

        Returns:
            Maximum tokens allowed for this operation
        """
        multipliers = {
            OperationType.REQUIREMENTS_EXTRACTION: self.requirements_multiplier,
            OperationType.RISK_ANALYSIS: self.risk_multiplier,
            OperationType.DEPENDENCY_DETECTION: self.dependency_multiplier,
            OperationType.SUBTASK_SUGGESTION: self.subtask_multiplier,
            OperationType.COMMENT_GENERATION: self.comment_multiplier,
            OperationType.DESCRIPTION_ENHANCEMENT: self.description_multiplier,
            OperationType.SMART_LABELING: self.labeling_multiplier,
        }

        multiplier = multipliers.get(operation, 1.0)
        return int(self.base_max_tokens * multiplier)


class TokenTracker:
    """
    Tracks token usage across all AI operations in a session.

    Features:
    - Consistent tracking across all operations
    - Budget enforcement
    - Usage reporting and analytics
    - Per-operation and total tracking
    """

    def __init__(self, budget: TokenBudget):
        """
        Initialize token tracker.

        Args:
            budget: Token budget configuration
        """
        self.budget = budget
        self.usage_history: List[TokenUsage] = []
        self._total_tokens = 0

    def record_usage(
        self,
        operation: OperationType,
        tokens_used: int,
        issue_key: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None
    ) -> None:
        """
        Record token usage for an operation.

        Args:
            operation: Type of operation
            tokens_used: Number of tokens consumed
            issue_key: Optional issue key being processed
            success: Whether the operation succeeded
            error: Optional error message if operation failed
        """
        usage = TokenUsage(
            operation=operation,
            tokens_used=tokens_used,
            issue_key=issue_key,
            success=success,
            error=error
        )

        self.usage_history.append(usage)
        self._total_tokens += tokens_used

    def get_total_tokens(self) -> int:
        """Get total tokens used across all operations."""
        return self._total_tokens

    def get_tokens_by_operation(self) -> Dict[OperationType, int]:
        """
        Get token usage broken down by operation type.

        Returns:
            Dict mapping operation type to total tokens used
        """
        result = {}
        for usage in self.usage_history:
            op_type = usage.operation
            result[op_type] = result.get(op_type, 0) + usage.tokens_used

        return result

    def get_failed_operations(self) -> List[TokenUsage]:
        """Get list of operations that failed."""
        return [u for u in self.usage_history if not u.success]

    def get_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive usage summary.

        Returns:
            Dict with total, by_operation, failed_count, etc.
        """
        by_operation = self.get_tokens_by_operation()
        failed = self.get_failed_operations()

        return {
            "total_tokens": self._total_tokens,
            "operation_count": len(self.usage_history),
            "by_operation": {
                op.value: tokens for op, tokens in by_operation.items()
            },
            "failed_operations": len(failed),
            "budget_base": self.budget.base_max_tokens,
            "success_rate": (
                (len(self.usage_history) - len(failed)) / len(self.usage_history)
                if self.usage_history else 1.0
            )
        }

    def format_summary(self) -> str:
        """
        Format usage summary as human-readable string.

        Returns:
            Formatted summary text
        """
        summary = self.get_summary()

        lines = [
            "Token Usage Summary:",
            f"  Total Tokens: {summary['total_tokens']}",
            f"  Operations: {summary['operation_count']}",
            f"  Success Rate: {summary['success_rate']:.1%}",
            "",
            "By Operation:"
        ]

        for op_name, tokens in summary['by_operation'].items():
            lines.append(f"  - {op_name}: {tokens} tokens")

        if summary['failed_operations'] > 0:
            lines.append("")
            lines.append(f"Failed Operations: {summary['failed_operations']}")

        return "\n".join(lines)

    def check_budget(self, operation: OperationType) -> bool:
        """
        Check if there's budget remaining for an operation.

        Args:
            operation: Operation type to check

        Returns:
            True if within budget, False otherwise
        """
        
        # For simplicity, just check if we haven't exceeded total budget
        # Could implement more sophisticated per-operation tracking

        return self._total_tokens < (self.budget.base_max_tokens * MAX_BUDGET_MULTIPLIER)  # Allow 10x for multi-issue analysis

    def reset(self) -> None:
        """Reset tracker (useful for new analysis session)."""
        self.usage_history = []
        self._total_tokens = 0
