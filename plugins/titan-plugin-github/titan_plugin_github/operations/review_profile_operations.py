"""Pure operations for applying review profile configuration."""

from fnmatch import fnmatch

from ..models.review_enums import ChecklistCategory
from ..models.review_models import ReviewChecklistItem, ScoredReviewCandidate
from ..models.review_profile_models import CandidateScoringRule, ReviewProfile


def match_change_patterns(path: str, review_profile: ReviewProfile) -> list[str]:
    """Return all matching change pattern names for a path."""
    matches: list[str] = []
    for name, patterns in review_profile.change_patterns.items():
        if path_matches_any(path, patterns):
            matches.append(name)
    return matches


def classify_file_role(
    path: str,
    review_profile: ReviewProfile,
    *,
    is_test: bool = False,
    is_docs: bool = False,
    is_generated: bool = False,
    is_config: bool = False,
) -> str:
    """Classify a file into a functional role using manifest flags first."""
    if is_docs or is_generated:
        return "docs_or_generated"
    if is_test:
        return "tests"
    if is_config:
        return "config_or_contracts"

    for role, patterns in review_profile.file_roles.items():
        if path_matches_any(path, patterns):
            return role
    return "other"


def matching_scoring_rules(path: str, review_profile: ReviewProfile) -> list[CandidateScoringRule]:
    """Return all configured scoring rules that match a path."""
    return [rule for rule in review_profile.candidate_scoring if path_matches_any(path, rule.patterns)]


def select_review_axes(
    checklist: list[ReviewChecklistItem],
    focus_candidates: list[ScoredReviewCandidate],
    review_profile: ReviewProfile,
) -> list[ChecklistCategory]:
    """Select applicable review axes from checklist and profile configuration."""
    if not checklist:
        return [
            ChecklistCategory.FUNCTIONAL_CORRECTNESS,
            ChecklistCategory.ERROR_HANDLING,
        ]

    candidate_paths = [candidate.path for candidate in focus_candidates]
    selected: list[ChecklistCategory] = []

    for item in checklist:
        axis_rule = review_profile.review_axes.get(item.id)
        if axis_rule and axis_rule.always_include:
            selected.append(item.id)
            continue

        patterns = list(item.relevant_file_patterns)
        if axis_rule:
            patterns.extend(axis_rule.patterns)

        if patterns and any(path_matches_any(path, patterns) for path in candidate_paths):
            selected.append(item.id)

    if not selected:
        selected = [ChecklistCategory.FUNCTIONAL_CORRECTNESS, ChecklistCategory.ERROR_HANDLING]
    return selected[:4]


def path_matches_any(path: str, patterns: list[str]) -> bool:
    """Return True when path matches any glob pattern."""
    normalized_path = path.replace("\\", "/").lower()
    return any(fnmatch(normalized_path, pattern.lower()) for pattern in patterns)
