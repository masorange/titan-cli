"""Deciding how much attention each changed file is worth.

One pure function over the change manifest and the review profile. It answers "what
does this PR deserve", not "what can we afford" — the budget is applied later, on top
of this, and keeping the two apart is the point: when the size class decided both at
once, the answer to the first question was never visible and 87 of 99 files were
dropped without anyone being told.

The question each tier actually asks is **not** "is this file important?" but "is the
diff alone enough to judge this change?" A mapper's two-line edit can be wrong in a way
only the surrounding file reveals; a test's fifty new lines usually cannot.
"""

from dataclasses import dataclass, field

from ..models.review_enums import AttentionTier, FileChangeStatus
from ..models.review_models import ChangedFileEntry
from ..models.review_profile_models import ReviewProfile
from .review_profile_operations import classify_file_role, path_matches_any

# A role the profile does not mention is covered cheaply rather than skipped: the whole
# point of the tiers is that nothing goes unlooked-at by accident.
FALLBACK_TIER = AttentionTier.GLANCE


@dataclass(frozen=True)
class FileAttention:
    """The tier one file lands in, and the rule that put it there."""

    path: str
    tier: AttentionTier
    role: str
    reason: str


@dataclass(frozen=True)
class AttentionPlan:
    """Every changed file's tier, plus the counts worth showing a human."""

    files: list[FileAttention] = field(default_factory=list)

    def paths_for(self, tier: AttentionTier) -> list[str]:
        return [entry.path for entry in self.files if entry.tier == tier]

    def count_for(self, tier: AttentionTier) -> int:
        return sum(1 for entry in self.files if entry.tier == tier)

    @property
    def counts(self) -> dict[str, int]:
        """Counts keyed by tier value, including tiers that came out empty.

        Empty tiers are included on purpose: "0 skipped" is information, and a summary
        whose keys change shape between PRs is harder to compare across runs.
        """
        return {tier.value: self.count_for(tier) for tier in AttentionTier}

    @property
    def reviewable_count(self) -> int:
        """Files something will actually look at — the honest denominator.

        Coverage reported against the PR's total file count flatters the review on any
        PR with generated output in it; reported against this, it means something.
        """
        return len(self.files) - self.count_for(AttentionTier.SKIP)


def resolve_file_attention(
    files: list[ChangedFileEntry], review_profile: ReviewProfile
) -> AttentionPlan:
    """Assign every changed file a tier, in a fixed and explainable order.

    Precedence, highest first:

    1. **`always_deep`** — an explicit instruction from the project, and it outranks
       everything including the skips below. A hatch that gets second-guessed is not a
       hatch.
    0. **Deleted files** — `glance`, before everything else: nothing to open, but their
       diff is what the PR removes, which the triage must see.
    2. **Lockfiles and rename-only changes** — `skip`. Neither can carry a reviewable
       defect: one is machine-resolved dependency arithmetic, the other moves a file
       without changing what it does.
    3. **The role's configured tier** — the ordinary path.
    4. **`glance`** — when the role is not in the map.

    Every entry carries the reason it got its tier, because a skipped file has to be
    explainable on screen, not merely absent from the results.
    """
    entries: list[FileAttention] = []

    for changed in files or []:
        role = classify_file_role(
            changed.path,
            review_profile,
            is_test=changed.is_test,
            is_docs=changed.is_docs,
            is_generated=changed.is_generated,
            is_config=changed.is_config,
        )

        if changed.status == FileChangeStatus.DELETED:
            # To the triage, never to the deep session and never skipped. There is no
            # file left to open, but the diff says exactly what disappears, and "was this
            # migrated, or is it simply gone?" is the question a migration PR turns on.
            # Skipping them was measured on ragnarok PR #3720: the triage stopped seeing
            # the deleted event classes and asked 2-3 questions instead of 13-16 -- the
            # ones that found edit-user-details tracking removed outright.
            entries.append(FileAttention(changed.path, AttentionTier.GLANCE, role, "deleted"))
            continue

        if review_profile.always_deep and path_matches_any(
            changed.path, review_profile.always_deep
        ):
            entries.append(
                FileAttention(changed.path, AttentionTier.DEEP, role, "always_deep")
            )
            continue


        if changed.is_lockfile:
            entries.append(FileAttention(changed.path, AttentionTier.SKIP, role, "lockfile"))
            continue

        if changed.is_rename_only:
            entries.append(
                FileAttention(changed.path, AttentionTier.SKIP, role, "rename_only")
            )
            continue

        configured = review_profile.attention.get(role)
        if configured is None:
            entries.append(
                FileAttention(changed.path, FALLBACK_TIER, role, f"role_not_configured:{role}")
            )
            continue

        entries.append(FileAttention(changed.path, configured, role, f"role:{role}"))

    return AttentionPlan(files=entries)


def summarize_attention_plan(plan: AttentionPlan) -> dict:
    """Counts and skip reasons, shaped for a log line.

    Skip reasons are grouped rather than listed per path: on a PR that regenerates a
    lockfile and a hundred API stubs, the per-path list is the noise and the grouping
    is the signal.
    """
    skip_reasons: dict[str, int] = {}
    for entry in plan.files:
        if entry.tier == AttentionTier.SKIP:
            skip_reasons[entry.reason] = skip_reasons.get(entry.reason, 0) + 1

    return {
        "files_total": len(plan.files),
        "files_reviewable": plan.reviewable_count,
        "attention_counts": plan.counts,
        "skip_reasons": skip_reasons,
        "always_deep_files": [e.path for e in plan.files if e.reason == "always_deep"],
    }


def build_change_shape_lines(
    plan: AttentionPlan, files: list[ChangedFileEntry], reviewed_paths: set[str]
) -> list[str]:
    """One line per changed file: path, role, tier, churn, and who is reading it.

    The whole-PR context the deep session needs to answer the questions a human asks
    last — does the shape of this change match what the PR says it does, and what is
    missing. A migration that touched 11 of 12 call sites, a new API with no tests and a
    config nobody reads are all invisible to a reader that only sees the files it was
    handed, which is what every batch saw until now. No file CONTENT is included, so this
    stays a few dozen characters per file however large the PR is.
    """
    churn = {entry.path: (entry.additions, entry.deletions) for entry in files}
    lines: list[str] = []
    for entry in plan.files:
        additions, deletions = churn.get(entry.path, (0, 0))
        # Two labels, not three: there is no "another pass" any more. A deep tier that
        # does not fit loses diff detail, not shared understanding (D-014), so every file
        # is either read here or it is not read at all.
        read_by = "reviewed here" if entry.path in reviewed_paths else entry.tier.value
        lines.append(
            f"{entry.path} | role={entry.role} | {read_by} | +{additions}/-{deletions}"
        )
    return lines
