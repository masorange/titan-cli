"""Prompt-budget policy for GitHub AI review workflows.

Centralizes the content-budget sizing and batch fit/split/degradation
policy previously duplicated as free functions in
`context_resolution_operations.py` and `code_review_steps.py`.
"""

from ..models.review_enums import FileReadMode, PRSizeClass
from ..models.review_models import FocusContextBatch, ReviewStrategy


class PromptBudgetManager:
    """Owns prompt-part sizing, batch fit/split decisions, and degradation policy."""

    def content_budget(self, strategy: ReviewStrategy) -> int:
        """Return the char budget available for file/related/comment context."""
        reserve = 5000 if strategy.size_class in {PRSizeClass.LARGE, PRSizeClass.HUGE} else 3500
        return max(2500, strategy.max_prompt_chars - reserve)

    def fit_batch_to_budget(
        self,
        batch: FocusContextBatch,
        prompt_parts: dict[str, str],
        budget_chars: int,
    ) -> tuple[list[FocusContextBatch], bool]:
        """Shrink or split a batch until it fits the prompt budget, or mark it oversized."""
        prompt = prompt_parts["prompt"]
        actual_chars = len(prompt)
        if actual_chars <= budget_chars:
            fitted = batch.model_copy(update={"prompt_actual_chars": actual_chars})
            return [fitted], False

        file_items = list(batch.files_context.items())
        if len(file_items) > 1:
            midpoint = max(1, len(file_items) // 2)
            left = batch.model_copy(
                update={
                    "batch_id": f"{batch.batch_id}a",
                    "files_context": dict(file_items[:midpoint]),
                    "degraded_context": True,
                }
            )
            right = batch.model_copy(
                update={
                    "batch_id": f"{batch.batch_id}b",
                    "files_context": dict(file_items[midpoint:]),
                    "degraded_context": True,
                }
            )
            return [left, right], True

        only_path, only_entry = file_items[0]
        if not only_entry.worktree_reference:
            degraded_entry = only_entry.model_copy(
                update={
                    "full_content": None,
                    "expanded_hunks": [],
                    "hunks": [],
                    "read_mode": FileReadMode.WORKTREE_REFERENCE,
                    "worktree_reference": True,
                    "review_hint": only_entry.review_hint
                    or "Read this file from the worktree and inspect the changed regions first.",
                    "approximate_chars": min(800, only_entry.approximate_chars or 800),
                }
            )
            return [
                batch.model_copy(
                    update={
                        "files_context": {only_path: degraded_entry},
                        "degraded_context": True,
                    }
                )
            ], True

        if batch.related_files:
            return [batch.model_copy(update={"related_files": {}, "degraded_context": True})], True

        if batch.comment_context:
            return [batch.model_copy(update={"comment_context": [], "degraded_context": True})], True

        oversized = batch.model_copy(
            update={
                "prompt_actual_chars": actual_chars,
                "prompt_still_too_large": True,
                "degraded_context": True,
            }
        )
        return [oversized], False


_default_manager = PromptBudgetManager()


def get_prompt_budget_manager() -> PromptBudgetManager:
    """Return the shared `PromptBudgetManager` instance."""
    return _default_manager
