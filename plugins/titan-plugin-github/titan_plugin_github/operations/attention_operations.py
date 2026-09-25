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
from typing import Callable, Optional

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
    2b. **Images, fonts and translatable text** — `glance`, whatever their role. The
       diff is the whole change; there is nothing around it to open.
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

        if changed.is_static_resource:
            # Glance at most, whatever the role says. Placed after `always_deep` (the
            # project's explicit hatch) and before the role tier, because a role glob is
            # usually a directory: ragnarok's `**/res/**` under UI sent strings.xml and
            # drawables to the deep session, where they cost the prompt room the code
            # needed and can hide nothing the diff does not already show.
            entries.append(
                FileAttention(changed.path, AttentionTier.GLANCE, role, "static_resource")
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
    plan: AttentionPlan,
    files: list[ChangedFileEntry],
    reviewed_paths: set[str],
    triage_notes: Optional[dict[str, str]] = None,
    flagged_paths: Optional[set[str]] = None,
) -> list[str]:
    """The review checklist: one line per changed file, with who covers it.

    Every changed file, its role and churn, and whose task it is: `YOU: review` for a file
    the deep session reads, `YOU: triage question` for one it only has to settle, and for
    the rest what the triage said about it, or its tier when the triage did not see it. No
    file CONTENT is included, so this stays a few dozen characters per file however large
    the PR is.

    The session's own rows come first. With every file in plan order, its tasks were
    scattered through the whole PR's list, and covering them was one instruction among
    many rather than a list it could see it had not finished.
    """
    notes = triage_notes or {}
    flagged = flagged_paths or set()
    churn = {entry.path: (entry.additions, entry.deletions) for entry in files}
    own: list[str] = []
    questions: list[str] = []
    rest: list[str] = []
    for entry in plan.files:
        additions, deletions = churn.get(entry.path, (0, 0))
        if entry.path in reviewed_paths:
            bucket, covered_by = own, "YOU: review"
        elif entry.path in flagged:
            bucket, covered_by = questions, "YOU: triage question"
        elif notes.get(entry.path):
            # A pipe inside the note would read as a new column.
            bucket, covered_by = rest, "triage: " + notes[entry.path].replace("|", "/").strip()
        else:
            bucket, covered_by = rest, entry.tier.value
        bucket.append(f"{entry.path} | role={entry.role} | {covered_by} | +{additions}/-{deletions}")
    return own + questions + rest


_TEST_STEM_PREFIXES = ("test_", "tests_")
_TEST_STEM_SUFFIXES = ("_tests", "_test", "_spec", "tests", "test", "spec")


def _relation_stem(path: str, is_test: bool) -> str:
    """The name a file shares with the files it belongs with: `foo` for `Foo.kt`,
    `FooTest.kt`, `test_foo.py` and `foo.spec.ts` alike."""
    stem = path.rsplit("/", 1)[-1].split(".", 1)[0].lower()
    if is_test:
        for prefix in _TEST_STEM_PREFIXES:
            if stem.startswith(prefix) and len(stem) > len(prefix):
                stem = stem[len(prefix):]
                break
        for suffix in _TEST_STEM_SUFFIXES:
            if stem.endswith(suffix) and len(stem) > len(suffix):
                stem = stem[: -len(suffix)].rstrip("_-")
                break
    return stem


def _directory(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else ""


def _shared_prefix_depth(left: str, right: str) -> int:
    depth = 0
    for a, b in zip(left.split("/"), right.split("/")):
        if a != b:
            break
        depth += 1
    return depth


def order_by_relation(paths: list[str], is_test: Callable[[str], bool]) -> list[str]:
    """Reorder ranked files so the ones that belong together are read together.

    Files sharing a directory form a group, and a test joins the file it is named after
    wherever it lives. Groups keep the ranking: a group sits where its highest-ranked file
    sat, and inside it the files keep their order, each test right after its subject.
    Nothing is added or dropped, so this only changes what the session reads next to what.

    A session reads "Code to Review" in order, and ranked order puts a step, the operation
    it calls and that operation's test wherever their scores land -- so the question that
    spans them comes up, if at all, dozens of files apart.
    """
    tests = {path for path in paths if is_test(path)}
    subjects_by_stem: dict[str, list[str]] = {}
    for path in paths:
        if path not in tests:
            subjects_by_stem.setdefault(_relation_stem(path, False), []).append(path)

    # Each test goes with the same-named subject nearest to it in the tree.
    tests_of: dict[str, list[str]] = {}
    for path in paths:
        if path not in tests:
            continue
        candidates = subjects_by_stem.get(_relation_stem(path, True))
        if candidates:
            subject = max(candidates, key=lambda c: _shared_prefix_depth(c, path))
            tests_of.setdefault(subject, []).append(path)
    attached = {test for group in tests_of.values() for test in group}

    groups: dict[str, list[str]] = {}
    for path in paths:
        if path in attached:
            continue
        group = groups.setdefault(_directory(path), [])
        group.append(path)
        group.extend(tests_of.get(path, []))
    return [path for group in groups.values() for path in group]


# Words a role name spells in lowercase that a reader expects in capitals.
_ACRONYMS = {"ui", "api", "ci", "db", "sql", "sdk", "cli", "ios"}

# Why a file got its tier, when the reason is not a role.
_REASON_LABELS = {
    "always_deep": "Always read in full (project rule)",
    "deleted": "Deleted",
    "lockfile": "Lockfiles",
    "rename_only": "Renamed, unchanged",
    "static_resource": "Images, fonts and texts",
}


@dataclass(frozen=True)
class AttentionGroup:
    """Files that share a tier and the reason for it, labelled for a person."""

    tier: AttentionTier
    label: str
    paths: list[str]


def humanize_role(role: str) -> str:
    """`entrypoints_or_ui` -> `Entrypoints / UI`.

    Roles are profile keys a project names, so there is no fixed table to look them up
    in; the snake_case id is turned into words instead.
    """
    words = [
        "/" if word == "or" else word.upper() if word in _ACRONYMS else word
        for word in role.split("_")
        if word
    ]
    text = " ".join(words)
    return text[:1].upper() + text[1:] if text else role


def describe_attention_reason(reason: str) -> str:
    """The on-screen label for a `FileAttention.reason`."""
    if reason in _REASON_LABELS:
        return _REASON_LABELS[reason]
    kind, _, role = reason.partition(":")
    if kind == "role":
        return humanize_role(role)
    if kind == "role_not_configured":
        return f"{humanize_role(role)} (no tier configured)"
    return reason


def group_attention_for_display(plan: AttentionPlan) -> list[AttentionGroup]:
    """Group files by tier, then by why they landed there, largest group first.

    A flat list of 22 full paths each followed by `role:entrypoints_or_ui` hid the one
    thing it was for: how the PR splits into kinds of change. Tiers keep their
    deep -> glance -> skip order; empty tiers are left out.
    """
    groups: list[AttentionGroup] = []
    for tier in AttentionTier:
        by_label: dict[str, list[str]] = {}
        for entry in plan.files:
            if entry.tier == tier:
                by_label.setdefault(describe_attention_reason(entry.reason), []).append(entry.path)
        for label, paths in sorted(by_label.items(), key=lambda item: -len(item[1])):
            groups.append(AttentionGroup(tier=tier, label=label, paths=paths))
    return groups


def split_display_path(path: str, keep_dirs: int = 2) -> tuple[str, str]:
    """(file name, shortened directory) -- the name is what a reader scans for.

    The directory keeps its first segment (the module: `app`, `network`) and its last
    `keep_dirs`, which is where files differ; the shared middle (`src/main/kotlin/com/...`)
    becomes `…`.
    """
    parts = path.split("/")
    name, dirs = parts[-1], parts[:-1]
    if len(dirs) > keep_dirs + 1:
        dirs = [dirs[0], "…", *dirs[-keep_dirs:]]
    return name, "/".join(dirs)
