from titan_plugin_git.clients.services.worktree_service import _parse_refs
from titan_plugin_git.drawing import ref_color
from titan_plugin_git.models.mappers.commit_mapper import from_network_commit, split_refs
from titan_plugin_git.models.network.commit import NetworkGitCommit

DECORATION = "HEAD -> refs/heads/feat/x, tag: refs/tags/26.45.4, refs/remotes/origin/develop, refs/remotes/origin/HEAD"


def test_the_decoration_keeps_full_names_and_only_drops_the_head_pointer():
    assert _parse_refs(DECORATION) == [
        "refs/heads/feat/x", "tag: refs/tags/26.45.4", "refs/remotes/origin/develop", "refs/remotes/origin/HEAD",
    ]
    assert _parse_refs("") == []


def test_refs_are_split_into_plain_names_tags_and_remote_branches():
    names, tags, remotes = split_refs(_parse_refs(DECORATION))

    assert names == ["feat/x", "26.45.4", "origin/develop"]  # a remote's own HEAD is left out
    assert tags == ["26.45.4"]
    assert remotes == ["origin/develop"]


def test_a_ui_commit_carries_the_kinds_and_each_kind_has_its_colour():
    commit = from_network_commit(NetworkGitCommit(
        hash="a" * 40, message="m", author="A <a@b.c>", date="2026-11-04", refs=_parse_refs(DECORATION),
    ))

    assert [ref_color(commit, ref) for ref in commit.refs] == ["success", "warning", "info"]
