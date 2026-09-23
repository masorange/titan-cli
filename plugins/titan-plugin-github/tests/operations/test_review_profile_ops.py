"""Tests for pure review-profile operations."""

from titan_plugin_github.operations.review_profile_operations import path_matches_any


class TestRootLevelGlobs:
    """`**/x` has to match a top-level `x` too.

    `fnmatch` needs something before `**/`, so `**/core/**` matched
    `titan_cli/core/x.py` but not `core/x.py` — every pattern written in the idiom the
    docs themselves use silently missed a top-level directory of that name. In
    `always_deep` that is the worst kind of failure: a path the team declared critical
    would not be deep-read and nothing would say so.
    """

    def test_a_double_star_prefix_matches_at_the_root(self):
        assert path_matches_any("core/security/vault.py", ["**/core/security/**"])

    def test_it_still_matches_below_the_root(self):
        assert path_matches_any("titan_cli/core/security/vault.py", ["**/core/security/**"])

    def test_an_unrelated_path_still_does_not_match(self):
        assert not path_matches_any("app/screens/home.py", ["**/core/security/**"])

    def test_a_pattern_without_the_prefix_is_unaffected(self):
        assert path_matches_any("core/x.py", ["core/*.py"])
        assert not path_matches_any("titan_cli/core/x.py", ["core/*.py"])


# ============================================================================
# Axis selection: every applicable axis, and the security vocabulary
# ============================================================================


def _auth_candidates(paths: list[str]):
    from titan_plugin_github.models.review_enums import FileReadMode, FileReviewPriority
    from titan_plugin_github.models.review_models import ScoredReviewCandidate

    return [
        ScoredReviewCandidate(
            path=path,
            score=10,
            priority=FileReviewPriority.HIGH,
            suggested_read_mode=FileReadMode.HUNKS_ONLY,
        )
        for path in paths
    ]


def test_every_applicable_axis_is_selected_not_the_first_four():
    """The `[:4]` here was the last survivor of the per-size budget table D-001 deleted.

    Measured on ragnarok run `70777691`: a project offering 12 axes had 4 sent, and which
    4 came down to checklist order. What it defended was prompt characters — 12 axes at
    the 200-char description cap is ~2.4k against a 120,000-char budget."""
    from titan_plugin_github.checklists.defaults import DEFAULT_REVIEW_CHECKLIST
    from titan_plugin_github.operations.review_profile_operations import select_review_axes
    from titan_plugin_github.review_profiles import DEFAULT_REVIEW_PROFILE

    candidates = _auth_candidates(
        [
            "domain/credentials/CredentialsApiDIModule.kt",
            "network/models/credentials/NetworkThirdPartyTokenRequest.kt",
            "network/apis/credentials/SessionsApi.kt",
        ]
    )

    axes = select_review_axes(list(DEFAULT_REVIEW_CHECKLIST), candidates, DEFAULT_REVIEW_PROFILE)

    assert len(axes) > 4


def test_the_security_axis_knows_the_vocabulary_of_auth_code():
    """`credentials`, `token`, `session` are how auth code is actually named.

    Run `70777691` reviewed a 38-file PR about credentials, sessions, OTP and magic links
    and matched NONE of `auth`/`permission`/`security`/`payment`/`billing`, so the
    security axis was never asked about on the one PR that most needed it."""
    from titan_plugin_github.checklists.defaults import DEFAULT_REVIEW_CHECKLIST
    from titan_plugin_github.models.review_enums import ChecklistCategory
    from titan_plugin_github.operations.review_profile_operations import select_review_axes
    from titan_plugin_github.review_profiles import DEFAULT_REVIEW_PROFILE

    for path in (
        "domain/credentials/CredentialsModels.kt",
        "network/apis/credentials/SessionsApi.kt",
        "core/oauth/storage.py",
        "ui/login/LoginScreen.kt",
        "core/security/_vault.py",
    ):
        axes = select_review_axes(
            list(DEFAULT_REVIEW_CHECKLIST), _auth_candidates([path]), DEFAULT_REVIEW_PROFILE
        )
        assert ChecklistCategory.SECURITY in axes, path


def test_a_pr_that_touches_no_credentials_does_not_get_the_security_axis():
    """The widened patterns are generic names, not a guess that every PR is about auth."""
    from titan_plugin_github.checklists.defaults import DEFAULT_REVIEW_CHECKLIST
    from titan_plugin_github.models.review_enums import ChecklistCategory
    from titan_plugin_github.operations.review_profile_operations import select_review_axes
    from titan_plugin_github.review_profiles import DEFAULT_REVIEW_PROFILE

    axes = select_review_axes(
        list(DEFAULT_REVIEW_CHECKLIST),
        _auth_candidates(["ui/list/ListViewModel.kt", "domain/offers/OffersStore.kt"]),
        DEFAULT_REVIEW_PROFILE,
    )

    assert ChecklistCategory.SECURITY not in axes


def test_an_axis_with_no_restriction_anywhere_applies():
    """Titan's own defaults were incoherent without this.

    `performance`, `concurrency`, `code_style` and `documentation` were offered in the
    default checklist with neither `relevant_file_patterns` nor a `review_axes` rule, and
    the old condition (`if patterns and any(...)`) dropped them silently — so 12 axes
    were advertised and only 8 could ever be asked about. The checklist says what a
    project cares about; the rule says WHEN each applies. Neither present means nothing
    restricts it."""
    from titan_plugin_github.models.review_enums import ChecklistCategory
    from titan_plugin_github.models.review_models import ReviewChecklistItem
    from titan_plugin_github.models.review_profile_models import ReviewProfile
    from titan_plugin_github.operations.review_profile_operations import select_review_axes

    unrestricted = ReviewChecklistItem(
        id=ChecklistCategory.CONCURRENCY, name="Concurrency", description="d"
    )

    axes = select_review_axes(
        [unrestricted], _auth_candidates(["anything.kt"]), ReviewProfile()
    )

    assert axes == [ChecklistCategory.CONCURRENCY]


def test_an_axis_whose_patterns_match_nothing_is_still_excluded():
    """"No restriction" is not "no filter": an axis that names the files it cares about
    and sees none of them does not apply, and asking about it would be asking about code
    that is not in the PR."""
    from titan_plugin_github.models.review_enums import ChecklistCategory
    from titan_plugin_github.models.review_models import ReviewChecklistItem
    from titan_plugin_github.models.review_profile_models import ReviewAxisRule, ReviewProfile
    from titan_plugin_github.operations.review_profile_operations import select_review_axes

    item = ReviewChecklistItem(
        id=ChecklistCategory.TEST_COVERAGE, name="Tests", description="d"
    )
    profile = ReviewProfile(
        review_axes={ChecklistCategory.TEST_COVERAGE: ReviewAxisRule(patterns=["**/*test*"])}
    )

    axes = select_review_axes([item], _auth_candidates(["src/main.kt"]), profile)

    assert ChecklistCategory.TEST_COVERAGE not in axes
    # With nothing applicable at all, the long-standing fallback asks about correctness
    # and error handling rather than about nothing.
    assert axes == [ChecklistCategory.FUNCTIONAL_CORRECTNESS, ChecklistCategory.ERROR_HANDLING]


def test_titan_defaults_can_ask_about_every_axis_they_offer():
    """The coherence check: nothing is advertised that cannot be selected."""
    from titan_plugin_github.checklists.defaults import DEFAULT_REVIEW_CHECKLIST
    from titan_plugin_github.models.review_profile_models import ReviewAxisRule
    from titan_plugin_github.review_profiles import DEFAULT_REVIEW_PROFILE
    from titan_plugin_github.operations.review_profile_operations import select_review_axes

    selectable = set()
    for item in DEFAULT_REVIEW_CHECKLIST:
        rule = DEFAULT_REVIEW_PROFILE.review_axes.get(item.id) or ReviewAxisRule()
        patterns = list(item.relevant_file_patterns) + list(rule.patterns)
        if rule.always_include or not patterns:
            selectable.add(item.id)
            continue
        # An axis with patterns is selectable if some path can match them; the patterns
        # themselves are the evidence, so a representative path is enough.
        probe = patterns[0].replace("**/*", "x/").replace("*", "y")
        if select_review_axes([item], _auth_candidates([probe]), DEFAULT_REVIEW_PROFILE):
            selectable.add(item.id)

    assert selectable == {item.id for item in DEFAULT_REVIEW_CHECKLIST}
