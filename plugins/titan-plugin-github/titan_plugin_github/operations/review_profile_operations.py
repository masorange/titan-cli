"""Pure operations for applying review profile configuration."""

from fnmatch import fnmatch

from ..models.review_enums import AttentionTier, ChecklistCategory
from ..models.review_models import ReviewChecklistItem
from ..models.review_profile_models import ReviewProfile


_TIER_DEPTH = {AttentionTier.SKIP: 0, AttentionTier.GLANCE: 1, AttentionTier.DEEP: 2}


def classify_file_role(
    path: str,
    review_profile: ReviewProfile,
    *,
    is_test: bool = False,
    is_docs: bool = False,
    is_generated: bool = False,
    is_config: bool = False,
) -> str:
    """Classify a file into the functional role that decides its attention tier.

    Docs, generated output and tests are facts the manifest detected about the file,
    so they decide outright. Everything else is a pattern match, and a path can match
    several roles: then **the role asking for the most attention wins**, and list order
    only breaks a tie. First-match used to decide, and on ragnarok `*ViewModel.kt` sat
    under `entrypoints_or_ui` ahead of `business_logic`, so the post-login flow was
    triaged from its diff. A project that lists a path under a deep role has said it
    wants it read; the order it happened to write its roles in must not undo that.

    `is_config` is a guess from the file name, not a fact, so it only nominates
    `config_or_contracts` as one more candidate.
    """
    if is_docs or is_generated:
        return "docs_or_generated"
    if is_test:
        return "tests"

    candidates = [
        role
        for role, patterns in review_profile.file_roles.items()
        if path_matches_any(path, patterns)
    ]
    if is_config and "config_or_contracts" not in candidates:
        candidates.append("config_or_contracts")
    if not candidates:
        return "other"
    # max() keeps the first of equal depth, so list order is the tie-break. A role the
    # attention map does not name counts as glance, which is what it would get.
    return max(
        candidates,
        key=lambda role: _TIER_DEPTH[review_profile.attention.get(role, AttentionTier.GLANCE)],
    )


def select_review_axes(
    checklist: list[ReviewChecklistItem],
    focus_paths: list[str],
    review_profile: ReviewProfile,
) -> list[ChecklistCategory]:
    """Select applicable review axes from checklist and profile configuration.

    Every axis that applies is returned. There used to be a `[:4]` here, and it was the
    last survivor of the per-size budget table D-001 deleted: on ragnarok run `70777691`
    a project offering 12 axes had 4 sent, and which 4 came down to checklist order. What
    it defended was prompt characters -- 12 axes at the 200-char description cap is ~2.4k
    against a 120,000-char budget -- so it defended nothing and cost coverage.
    """
    if not checklist:
        return [
            ChecklistCategory.FUNCTIONAL_CORRECTNESS,
            ChecklistCategory.ERROR_HANDLING,
        ]

    candidate_paths = list(focus_paths)
    selected: list[ChecklistCategory] = []

    for item in checklist:
        axis_rule = review_profile.review_axes.get(item.id)
        if axis_rule and axis_rule.always_include:
            selected.append(item.id)
            continue

        # WHEN an axis applies lives in the profile only; the checklist says what the
        # axis IS. It used to be both, unioned, so one question had two answers in two
        # files and editing one of them did not change the result.
        patterns = list(axis_rule.patterns) if axis_rule else []

        if not patterns:
            # No restriction anywhere means the axis applies. The checklist is where a
            # project says what it cares about; `review_axes` is where it says WHEN each
            # one applies (the model's own words: "rule that determines when a review
            # axis should apply"). An entry with neither patterns nor a rule has nothing
            # restricting it.
            #
            # It used to be dropped here, silently, and that made Titan's own defaults
            # incoherent: `performance`, `concurrency`, `code_style` and `documentation`
            # were offered in the checklist and could never be selected, so 12 axes were
            # advertised and only 8 could ever be asked about.
            selected.append(item.id)
            continue

        if any(path_matches_any(path, patterns) for path in candidate_paths):
            selected.append(item.id)

    if not selected:
        selected = [ChecklistCategory.FUNCTIONAL_CORRECTNESS, ChecklistCategory.ERROR_HANDLING]
    return selected


def path_matches_any(path: str, patterns: list[str]) -> bool:
    """Return True when path matches any glob pattern.

    A leading `**/` also matches at the repository root. `fnmatch` needs something
    before `**/` to match, so `**/core/**` matched `titan_cli/core/x.py` but NOT
    `core/x.py` — which means every pattern written in the idiom the docs use silently
    missed a top-level directory of that name. The intent of `**/core/**` is "a core
    directory anywhere", root included, so the prefix-stripped form is tried too.
    """
    normalized_path = path.replace("\\", "/").lower()
    for pattern in patterns:
        candidate = pattern.lower()
        if fnmatch(normalized_path, candidate):
            return True
        if candidate.startswith("**/") and fnmatch(normalized_path, candidate[3:]):
            return True
    return False
