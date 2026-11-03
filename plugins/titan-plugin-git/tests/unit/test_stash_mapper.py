from titan_plugin_git.models.mappers import from_network_stash
from titan_plugin_git.models.network import NetworkGitStash


def test_a_stash_made_with_a_message_splits_branch_and_message():
    ui = from_network_stash(NetworkGitStash("stash@{0}", "On feat/x: half done", "2 hours ago"))
    assert (ui.ref, ui.branch, ui.message, ui.formatted_date) == ("stash@{0}", "feat/x", "half done", "2 hours ago")


def test_a_wip_stash_keeps_the_commit_it_was_made_on_as_its_message():
    ui = from_network_stash(NetworkGitStash("stash@{1}", "WIP on main: abc1234 last commit"))
    assert (ui.branch, ui.message) == ("main", "abc1234 last commit")


def test_an_unknown_subject_is_kept_whole():
    ui = from_network_stash(NetworkGitStash("stash@{2}", "something else"))
    assert (ui.branch, ui.message) == ("", "something else")
