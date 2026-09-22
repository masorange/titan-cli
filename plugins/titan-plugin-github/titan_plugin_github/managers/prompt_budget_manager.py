"""Prompt-budget policy for GitHub AI review workflows.

Centralizes the content-budget sizing and batch fit/split/degradation
policy previously duplicated as free functions in
`context_resolution_operations.py` and `code_review_steps.py`.
"""

from ..models.review_enums import FileReadMode
from ..models.review_models import FileContextEntry, FocusContextBatch, ReviewBudget


class PromptBudgetManager:
    """Owns prompt-part sizing, batch fit/split decisions, and degradation policy."""

    # What a worktree_reference entry actually occupies in the prompt: a path, a hint and
    # the changed hunk headers.
    #
    # It used to be charged 5000 chars to stand in for the CLI's exploration cost, and
    # that inflation -- not any cost policy -- is half of why one deep file meant one AI
    # call: two such entries blew the content budget and spilled into separate batches.
    # Exploration is not paid in prompt characters, so charging it here mixed two units
    # (the deep tier is bounded by sessions, the glance tier by characters). The prompt's
    # real size is still enforced, against the actual string, in fit_batch_to_budget.
    WORKTREE_REFERENCE_PROMPT_CHARS = 400

    # What the prompt spends on everything that is not file content: the PR header, the
    # axes, the instructions and the response schema. Measured on a real batch at ~2.9k
    # chars, so 3500 leaves room without pretending to be exact.
    NON_CONTENT_RESERVE_CHARS = 3500

    def content_budget(self, budget: ReviewBudget) -> int:
        """Return the char budget available for file/related/comment context.

        One reserve, not two. The old version reserved 5000 chars on a PR classified
        LARGE or HUGE and 3500 otherwise, which only made sense while a big PR meant
        more focus files; the deep tier is now capped at a fixed number of sessions, so
        the PR's overall size says nothing about how much room one batch needs.
        """
        return max(2500, budget.deep_max_prompt_chars - self.NON_CONTENT_RESERVE_CHARS)

    def estimate_entry_chars(self, entry: FileContextEntry) -> int:
        """Estimate the prompt-budget cost of a resolved file context entry."""
        if entry.full_content:
            return len(entry.full_content)
        if entry.expanded_hunks:
            return sum(len(hunk) for hunk in entry.expanded_hunks)
        if entry.hunks:
            return sum(len(hunk) for hunk in entry.hunks)
        if entry.worktree_reference:
            return self.WORKTREE_REFERENCE_PROMPT_CHARS
        return 0

    def fit_batch_to_budget(
        self,
        batch: FocusContextBatch,
        prompt_parts: dict[str, str],
        budget_chars: int,
        allow_file_reads: bool = True,
    ) -> tuple[list[FocusContextBatch], bool]:
        """Shrink or split a batch until it fits the prompt budget, or mark it oversized.

        ``allow_file_reads=False`` forbids the worktree_reference degradation: that
        mode instructs the model to read the file from disk, which is exactly what
        the caller ruled out when the checkout is not provably the PR's revision.
        The batch then degrades through the remaining steps or reports oversized.
        """
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
        if not only_entry.worktree_reference and allow_file_reads:
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

        hunk_split = self._split_entry_hunks(batch, only_path, only_entry)
        if hunk_split:
            return hunk_split, True

        if only_entry.worktree_reference and only_entry.hunks:
            # Last resort for a file whose diff cannot be divided: a NEW file is one
            # single hunk, so PR 251's locks.py (+323) and models.py (+301) arrived as one
            # ~12k-char hunk each and were reported "too large even after reduction" --
            # skipped outright, which is the worst outcome available. Drop the inline diff
            # and keep the reference: the session opens the file from the working tree and
            # the hunk HEADERS still say which regions changed. Anchoring gets weaker for
            # this one file (no snippet to copy), and a reviewed file with weak anchors
            # beats an unreviewed one.
            return [
                batch.model_copy(
                    update={
                        "files_context": {
                            only_path: only_entry.model_copy(
                                update={
                                    "hunks": [],
                                    "approximate_chars": self.WORKTREE_REFERENCE_PROMPT_CHARS,
                                }
                            )
                        },
                        "degraded_context": True,
                    }
                )
            ], True

        oversized = batch.model_copy(
            update={
                "prompt_actual_chars": actual_chars,
                "prompt_still_too_large": True,
                "degraded_context": True,
            }
        )
        return [oversized], False

    def _split_entry_hunks(
        self, batch: FocusContextBatch, path: str, entry: FileContextEntry
    ) -> list[FocusContextBatch]:
        """Split one file's hunks across two batches, or return [] if that is impossible.

        The last resort before a batch is declared oversized, and the only degradation
        that helps the shape which actually broke: a single file whose own hunks exceed
        the budget. Splitting by file does nothing there -- measured on PR #254, one file
        with 22 hunks built a 149,353-char prompt against an 18,000 budget, and the batch
        was skipped rather than divided, leaving the PR's main file unreviewed in three
        consecutive runs.

        Whole-file content cannot be divided this way (the model is being shown the file,
        not a set of regions), and a single hunk is already indivisible, so both return []
        and the caller reports oversized as before.
        """
        field = "hunks" if entry.hunks else "expanded_hunks" if entry.expanded_hunks else None
        if entry.full_content or field is None:
            return []

        hunks = list(getattr(entry, field))
        if len(hunks) < 2:
            return []

        midpoint = max(1, len(hunks) // 2)
        halves = (hunks[:midpoint], hunks[midpoint:])
        return [
            batch.model_copy(
                update={
                    "batch_id": f"{batch.batch_id}{suffix}",
                    "files_context": {
                        path: entry.model_copy(
                            update={
                                field: half,
                                "approximate_chars": sum(len(hunk) for hunk in half),
                            }
                        )
                    },
                    "degraded_context": True,
                }
            )
            for suffix, half in zip(("a", "b"), halves)
        ]


_default_manager = PromptBudgetManager()


def get_prompt_budget_manager() -> PromptBudgetManager:
    """Return the shared `PromptBudgetManager` instance."""
    return _default_manager
