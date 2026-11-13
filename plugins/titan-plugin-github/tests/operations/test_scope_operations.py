import pytest

from titan_plugin_github.operations.scope_operations import (
    TitleScopes,
    UnsupportedGlob,
    apply_title_scopes,
    build_title_instruction,
    build_title_scopes,
    changed_paths_from_diff,
    compute_title_scopes,
    enforce_title_scopes,
    glob_to_regex,
    match_labels,
    parse_labeler_rules,
    scope_text,
    title_length_limit,
)

# The shape of a real monorepo labeler: areas by folder, platforms by any nested folder.
LABELER = """
etravel:
  - changed-files:
      - any-glob-to-any-file:
          - 'pkg/etravel/**'

docs:
  - changed-files:
      - any-glob-to-any-file: 'docs/**'

ios:
  - changed-files:
      - any-glob-to-any-file:
          - 'pkg/**/ios/**'
          - 'docs/**/ios/**'
          - 'Package.swift'

android:
  - changed-files:
      - any-glob-to-any-file:
          - 'pkg/**/android/**'
          - 'docs/**/android/**'

ci:
  - changed-files:
      - any-glob-to-any-file:
          - '.github/**'
"""


def _matches(glob: str, path: str) -> bool:
    return glob_to_regex(glob).fullmatch(path) is not None


def test_double_star_crosses_folders_and_matches_zero_of_them():
    assert _matches("pkg/**/ios/**", "pkg/etravel/ios/Home.swift")
    assert _matches("pkg/**/ios/**", "pkg/etravel/app/ios/deep/Home.swift")
    assert _matches("pkg/**/ios/**", "pkg/ios/Home.swift")


def test_single_star_stays_inside_one_path_segment():
    assert _matches("pkg/*/x.py", "pkg/a/x.py")
    assert not _matches("pkg/*/x.py", "pkg/a/b/x.py")


def test_a_literal_path_matches_only_itself():
    assert _matches("Package.swift", "Package.swift")
    assert not _matches("Package.swift", "pkg/Package.swift")


def test_dotfiles_match_like_the_labeler_does():
    assert _matches(".github/**", ".github/workflows/x.yml")
    assert _matches("pkg/**", "pkg/a/.hidden")


@pytest.mark.parametrize("glob", ["pkg/{a,b}/**", "pkg/[ab]/**", "!pkg/**", "pkg/\\*", "#comment", "pkg/@(a|b)"])
def test_syntax_it_cannot_translate_is_refused_rather_than_guessed(glob):
    with pytest.raises(UnsupportedGlob):
        glob_to_regex(glob)


def test_labeler_rules_keep_file_order_and_accept_a_bare_string_glob():
    rules, warnings = parse_labeler_rules(LABELER)

    assert list(rules) == ["etravel", "docs", "ios", "android", "ci"]
    assert rules["docs"][0].fullmatch("docs/guide.md")
    assert warnings == []


def test_a_matcher_other_than_changed_files_is_skipped_with_a_warning_and_the_label_is_kept():
    rules, warnings = parse_labeler_rules(
        "feat-branch:\n  - head-branch: ['^feat/']\nok:\n  - changed-files:\n      - any-glob-to-any-file: ['a/**']\n"
    )

    assert rules["feat-branch"] == []
    assert rules["ok"][0].fullmatch("a/x")
    assert len(warnings) == 1 and "feat-branch" in warnings[0]


def test_a_wrapped_any_block_is_reported_not_guessed():
    _, warnings = parse_labeler_rules(
        "area:\n  - any:\n      - changed-files:\n          - any-glob-to-any-file: ['a/**']\n"
    )

    assert len(warnings) == 1 and "area" in warnings[0]


def test_a_glob_it_cannot_translate_is_skipped_and_the_other_globs_still_count():
    rules, warnings = parse_labeler_rules(
        "area:\n  - changed-files:\n      - any-glob-to-any-file: ['{a,b}/**', 'c/**']\n"
    )

    assert len(rules["area"]) == 1 and rules["area"][0].fullmatch("c/x")
    assert len(warnings) == 1 and "{a,b}/**" in warnings[0]


def test_matching_two_globs_of_one_label_still_names_the_label_once():
    rules, _ = parse_labeler_rules(LABELER)

    assert match_labels(rules, ["pkg/a/ios/x.swift", "Package.swift"]) == ["ios"]


@pytest.mark.parametrize(
    "files, scopes",
    [
        (["pkg/etravel/ios/Home.swift"], ["etravel", "ios"]),
        (["pkg/etravel/ios/Home.swift", "pkg/etravel/android/Home.kt"], ["etravel", "ios", "android"]),
        (["docs/etravel/android/guide.md"], ["docs", "android"]),
        ([".github/workflows/x.yml"], ["ci"]),
        # A package's own docs earn the package, not the general `docs` label.
        (["pkg/etravel/docs/x.md"], ["etravel"]),
        (["README.md"], []),
        ([], []),
    ],
)
def test_scopes_are_the_labels_the_files_earn_in_labeler_order(files, scopes):
    assert compute_title_scopes(LABELER, files)[0] == scopes


def test_computing_scopes_hands_back_the_labeler_warnings():
    scopes, warnings = compute_title_scopes("a:\n  - head-branch: ['x']\n", ["a/x"])

    assert scopes == []
    assert len(warnings) == 1


def test_an_unparseable_labeler_gives_no_scopes_and_says_why():
    scopes, warnings = compute_title_scopes("a: [unclosed", ["a/x"])

    assert scopes == []
    assert len(warnings) == 1 and "YAML" in warnings[0]


def test_a_labeler_that_is_not_a_mapping_gives_no_scopes():
    scopes, warnings = compute_title_scopes("- just\n- a list\n", ["a/x"])

    assert scopes == []
    assert len(warnings) == 1


def test_scope_text_wraps_the_scopes_and_is_empty_without_them():
    assert scope_text(["a", "b"]) == "(a,b)"
    assert scope_text(["a", "b"], "|") == "(a|b)"
    assert scope_text([]) == ""


def test_the_title_limit_grows_by_the_room_the_scope_takes():
    assert title_length_limit([]) == 72
    assert title_length_limit(["etravel", "ios"]) == 72 + len("(etravel,ios)")


def test_applying_scopes_adds_them_to_a_bare_title():
    assert apply_title_scopes("feat: Add home", ["etravel", "ios"]) == "feat(etravel,ios): Add home"


def test_applying_scopes_replaces_what_the_model_invented():
    assert apply_title_scopes("feat(made-up): Add home", ["etravel"]) == "feat(etravel): Add home"


def test_applying_no_scopes_removes_the_one_the_title_had():
    assert apply_title_scopes("feat(api): Add home", []) == "feat: Add home"


def test_applying_scopes_keeps_the_breaking_marker_and_uses_the_separator():
    assert apply_title_scopes("feat(a)!: Drop v1", ["x", "y"], "|") == "feat(x|y)!: Drop v1"


def test_applying_scopes_keeps_issue_ids_in_the_description():
    assert apply_title_scopes("fix: PROJ-1, PROJ-2 Handle nulls", ["api"]) == "fix(api): PROJ-1, PROJ-2 Handle nulls"


def test_a_title_without_a_type_prefix_cannot_take_a_scope():
    assert apply_title_scopes("Add home screen", ["etravel"]) is None
    assert apply_title_scopes("", ["etravel"]) is None


DIFF = """\
diff --git a/pkg/etravel/ios/Home.swift b/pkg/etravel/ios/Home.swift
index 1..2 100644
--- a/pkg/etravel/ios/Home.swift
+++ b/pkg/etravel/ios/Home.swift
@@ -1 +1 @@
-a
+b
diff --git a/docs/old.md b/pkg/etravel/docs/new.md
similarity index 90%
rename from docs/old.md
rename to pkg/etravel/docs/new.md
diff --git a/.github/gone.yml b/.github/gone.yml
deleted file mode 100644
"""


def test_changed_paths_come_from_the_diff_headers_with_renames_under_their_new_name():
    assert changed_paths_from_diff(DIFF) == [
        "pkg/etravel/ios/Home.swift",
        "pkg/etravel/docs/new.md",
        ".github/gone.yml",
    ]


def test_a_diff_with_no_headers_has_no_paths():
    assert changed_paths_from_diff("") == []
    assert changed_paths_from_diff("just text") == []


def test_a_file_listed_twice_in_a_diff_is_one_path():
    twice = "diff --git a/x b/x\n+1\ndiff --git a/x b/x\n+2\n"

    assert changed_paths_from_diff(twice) == ["x"]


def test_the_policy_is_the_scopes_of_the_files_in_the_diff():
    policy = build_title_scopes(LABELER, DIFF)

    assert policy.enabled
    # The rename lands in a package's own docs, so it earns the package, not `docs`.
    assert policy.scopes == ("etravel", "ios", "ci")


def test_a_missing_labeler_leaves_the_policy_off_and_names_the_file():
    policy = build_title_scopes(None, DIFF, labeler_path="ci/labeler.yml")

    assert not policy.enabled
    assert "ci/labeler.yml" in policy.warnings[0]


def test_enforcing_replaces_the_scope_the_model_wrote_with_the_policys():
    policy = TitleScopes(enabled=True, scopes=("etravel", "ios"))

    title, warnings = enforce_title_scopes("feat(made-up): Add home", policy)

    assert title == "feat(etravel,ios): Add home"
    assert warnings == []


def test_enforcing_with_no_matching_label_drops_the_scope_and_says_so():
    policy = TitleScopes(enabled=True, scopes=())

    title, warnings = enforce_title_scopes("feat(api): Add home", policy)

    assert title == "feat: Add home"
    assert len(warnings) == 1 and "No labeler rule matches" in warnings[0]


def test_enforcing_a_disabled_policy_leaves_the_title_alone_and_passes_its_warnings_on():
    policy = TitleScopes(enabled=False, warnings=("labeler missing",))

    title, warnings = enforce_title_scopes("feat(api): Add home", policy)

    assert title == "feat(api): Add home"
    assert warnings == ["labeler missing"]


def test_enforcing_warns_when_the_title_has_no_type_to_attach_a_scope_to():
    policy = TitleScopes(enabled=True, scopes=("etravel",))

    title, warnings = enforce_title_scopes("Add home screen", policy)

    assert title == "Add home screen"
    assert any("type:" in w for w in warnings)


def test_enforcing_leaves_the_length_to_the_review_which_is_told_the_scope_aware_limit():
    policy = TitleScopes(enabled=True, scopes=("etravel",))

    title, warnings = enforce_title_scopes("feat: " + "x" * 90, policy)

    assert title == "feat(etravel): " + "x" * 90
    assert warnings == []


def test_the_instruction_without_scopes_is_the_rule_prompts_always_had():
    text = build_title_instruction()

    assert "WITHOUT scope" in text
    assert "NEVER use format like" in text
    assert "≤72 characters" in text


def test_the_instruction_with_scopes_names_them_and_widens_the_limit():
    text = build_title_instruction(["etravel", "ios"])

    assert "type(etravel,ios): Description" in text
    assert "≤85 characters total, scope included" in text
    assert "WITHOUT scope" not in text
    assert "NEVER" not in text


def test_the_instruction_uses_the_configured_separator():
    assert "feat(a|b): Add user auth flow" in build_title_instruction(["a", "b"], "|")
