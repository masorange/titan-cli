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
