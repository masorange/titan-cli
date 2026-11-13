from types import SimpleNamespace

import pytest

from titan_cli.core.plugins.models import GitHubPluginConfig
from titan_cli.core.result import ClientError, ClientSuccess
from titan_plugin_github.agents import PRAgent

LABELER = """
etravel:
  - changed-files:
      - any-glob-to-any-file: ['pkg/etravel/**']
ios:
  - changed-files:
      - any-glob-to-any-file: ['pkg/**/ios/**']
"""

DIFF = (
    "diff --git a/pkg/etravel/ios/Home.swift b/pkg/etravel/ios/Home.swift\n"
    "--- a/pkg/etravel/ios/Home.swift\n+++ b/pkg/etravel/ios/Home.swift\n"
    "@@ -1 +1 @@\n-a\n+b\n"
)
README_DIFF = "diff --git a/README.md b/README.md\n@@ -1 +1 @@\n-a\n+b\n"


class FakeGit:
    """Answers the one question the agent asks of git here: a file at a ref."""

    main_branch = "master"

    def __init__(self, labeler=LABELER, error=None):
        self.labeler = labeler
        self.error = error
        self.asked = None

    def get_file_at_ref(self, ref, path):
        self.asked = (ref, path)
        if self.error:
            return ClientError(error_message=self.error)
        return ClientSuccess(data=self.labeler)


def _generate(model_title, diff=DIFF, git=None, github="labeler", **config):
    """Run the PR generation with a model that answers `model_title`; return (result, prompt, git)."""
    git = git or FakeGit()
    if github == "labeler":
        config.setdefault("pr_title_scope_source", "labeler")
        github = SimpleNamespace(config=GitHubPluginConfig(repo_owner="o", repo_name="r", **config))

    agent = PRAgent(generator=None, git_client=git, github_client=github)
    prompts = []

    def answer(request):
        prompts.append(request.context)
        return SimpleNamespace(
            parsed={"title": model_title, "description": "## Summary\nSomething real changed here."},
            tokens_used=1,
        )

    agent.generate = answer
    result = agent._generate_pr_description(
        commits=["c1"], diff=diff, head_branch="feat/x", base_branch="master", template="## Summary"
    )
    return result, prompts[0], git


def test_with_the_labeler_source_the_title_carries_the_scopes_of_the_files():
    result, _, _ = _generate("feat: add home screen")

    assert result["title"] == "feat(etravel,ios): Add home screen"
    assert result["title_warnings"] == []


def test_the_prompt_names_the_scope_and_drops_the_no_scope_rule():
    _, prompt, _ = _generate("feat: add home screen")

    assert "type(etravel,ios): Description" in prompt
    assert "WITHOUT scope" not in prompt
    assert "NEVER use format" not in prompt


def test_a_scope_the_model_invented_is_replaced_by_the_labelers():
    result, _, _ = _generate("feat(made-up): add home screen")

    assert result["title"] == "feat(etravel,ios): Add home screen"


def test_the_labeler_is_read_from_the_head_branch_whatever_the_working_directory():
    _, _, git = _generate("feat: add home screen", pr_title_labeler_path="./.github/labeler.yml")

    assert git.asked == ("feat/x", ".github/labeler.yml")


def test_the_configured_separator_joins_the_scopes():
    result, prompt, _ = _generate("feat: add home screen", pr_title_scope_separator="|")

    assert result["title"] == "feat(etravel|ios): Add home screen"
    assert "type(etravel|ios): Description" in prompt


def test_a_pr_no_rule_matches_gets_no_scope_and_a_warning():
    result, prompt, _ = _generate("feat(api): add readme", diff=README_DIFF)

    assert result["title"] == "feat: Add readme"
    assert any("No labeler rule matches" in w for w in result["title_warnings"])
    assert "WITHOUT scope" in prompt


def test_by_default_nothing_changes_and_the_labeler_is_never_read():
    result, prompt, git = _generate("feat: add home screen", pr_title_scope_source="off")

    assert result["title"] == "feat: Add home screen"
    assert result["title_warnings"] == []
    assert "WITHOUT scope" in prompt
    assert git.asked is None


def test_a_repo_that_configures_nothing_is_untouched():
    github = SimpleNamespace(config=GitHubPluginConfig(repo_owner="o", repo_name="r"))
    result, _, git = _generate("feat: add home screen", github=github)

    assert result["title"] == "feat: Add home screen"
    assert git.asked is None


def test_a_core_older_than_the_setting_is_treated_as_off():
    github = SimpleNamespace(config=SimpleNamespace(pr_template_path=None))
    result, _, git = _generate("feat: add home screen", github=github)

    assert result["title"] == "feat: Add home screen"
    assert git.asked is None


def test_without_a_github_client_the_title_has_no_scope_policy():
    result, _, _ = _generate("feat: add home screen", github=None)

    assert result["title"] == "feat: Add home screen"


def test_a_missing_labeler_keeps_the_title_as_written_and_warns():
    result, prompt, _ = _generate("feat: add home screen", git=FakeGit(labeler=None))

    assert result["title"] == "feat: Add home screen"
    assert any(".github/labeler.yml" in w and "not found" in w for w in result["title_warnings"])
    assert "WITHOUT scope" in prompt


def test_a_labeler_that_cannot_be_read_keeps_the_title_as_written_and_warns():
    result, _, _ = _generate("feat: add home screen", git=FakeGit(error="bad ref"))

    assert result["title"] == "feat: Add home screen"
    assert any("bad ref" in w for w in result["title_warnings"])


def test_a_rule_the_labeler_parser_skips_is_reported_with_the_title():
    labeler = LABELER + "\nbranchy:\n  - head-branch: ['^feat/']\n"
    result, _, _ = _generate("feat: add home screen", git=FakeGit(labeler=labeler))

    assert result["title"] == "feat(etravel,ios): Add home screen"
    assert any("branchy" in w for w in result["title_warnings"])


def test_the_review_limit_grows_with_the_scope_and_stays_72_without_one():
    scoped, _, _ = _generate("feat: add home screen")
    unscoped, _, _ = _generate("feat: add home screen", pr_title_scope_source="off")
    no_match, _, _ = _generate("feat: add readme", diff=README_DIFF)

    assert scoped["title_limit"] == 72 + len("(etravel,ios)")
    assert unscoped["title_limit"] == 72
    assert no_match["title_limit"] == 72


def test_a_labeler_that_cannot_be_applied_never_blocks_the_pr(monkeypatch):
    """Whatever the labeler holds, the description is still generated; only the scope is lost."""
    def explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("titan_plugin_github.agents.pr_agent.build_title_scopes", explode)

    result, prompt, _ = _generate("feat: add home screen")

    assert result["title"] == "feat: Add home screen"
    assert result["body"]
    assert any("boom" in w for w in result["title_warnings"])
    assert "WITHOUT scope" in prompt


@pytest.mark.parametrize(
    "labeler",
    [
        "a:\n  - changed-files:\n      - any-glob-to-any-file:\n",
        "a:\n  - changed-files:\n      - any-glob-to-any-file: [[x]]\n",
        "2.0:\n  - changed-files:\n      - any-glob-to-any-file: ['pkg/**']\n",
    ],
    ids=["no value", "nested list", "numeric label"],
)
def test_labelers_with_odd_but_valid_yaml_still_give_a_title_and_a_description(labeler):
    result, _, _ = _generate("feat: add home screen", git=FakeGit(labeler=labeler))

    assert result["title"].startswith("feat")
    assert result["body"]
