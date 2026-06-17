"""Prompt budget manager for GitHub review workflows."""

from dataclasses import dataclass

from ..models.review_enums import FileReadMode
from ..models.review_models import FileContextEntry, FocusContextBatch, ReviewStrategy


@dataclass
class FitResult:
    """Result of trying to fit a findings batch under a prompt budget."""

    batches: list[FocusContextBatch]
    changed: bool


class PromptBudgetManager:
    """Own prompt-budget fitting and degradation policy for GitHub review workflows."""

    def content_budget_for_strategy(self, strategy: ReviewStrategy) -> int:
        """Return the content budget available after reserving prompt overhead."""
        reserve = 5000 if strategy.size_class.value in {"large", "huge"} else 3500
        return max(2500, strategy.max_prompt_chars - reserve)

    def fit_findings_batch_to_budget(
        self,
        batch: FocusContextBatch,
        prompt_parts: dict[str, str],
        budget_chars: int,
    ) -> FitResult:
        """Shrink or split a findings batch until it fits, or mark it oversized."""
        prompt = prompt_parts["prompt"]
        actual_chars = len(prompt)
        if actual_chars <= budget_chars:
            fitted = batch.model_copy(update={"prompt_actual_chars": actual_chars})
            return FitResult(batches=[fitted], changed=False)

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
            return FitResult(batches=[left, right], changed=True)

        only_path, only_entry = file_items[0]
        if not only_entry.worktree_reference:
            degraded_entry = self._degrade_file_context_to_worktree_reference(only_entry)
            degraded_batch = batch.model_copy(
                update={
                    "files_context": {only_path: degraded_entry},
                    "degraded_context": True,
                }
            )
            return FitResult(batches=[degraded_batch], changed=True)

        if batch.related_files:
            degraded_batch = batch.model_copy(update={"related_files": {}, "degraded_context": True})
            return FitResult(batches=[degraded_batch], changed=True)

        if batch.comment_context:
            degraded_batch = batch.model_copy(update={"comment_context": [], "degraded_context": True})
            return FitResult(batches=[degraded_batch], changed=True)

        oversized = batch.model_copy(
            update={
                "prompt_actual_chars": actual_chars,
                "prompt_still_too_large": True,
                "degraded_context": True,
            }
        )
        return FitResult(batches=[oversized], changed=False)

    def _degrade_file_context_to_worktree_reference(self, entry: FileContextEntry) -> FileContextEntry:
        """Downgrade inline file context to a worktree reference hint."""
        return entry.model_copy(
            update={
                "full_content": None,
                "expanded_hunks": [],
                "hunks": [],
                "read_mode": FileReadMode.WORKTREE_REFERENCE,
                "worktree_reference": True,
                "review_hint": entry.review_hint or "Read this file from the worktree and inspect the changed regions first.",
                "approximate_chars": min(800, entry.approximate_chars or 800),
            }
        )
