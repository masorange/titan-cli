"""
What the dock says: the F2 and F3 cells, and how a tile reads.

The dock is the only place F2 and F3 are advertised, so what it says about them is worth
pinning down.
"""

from titan_cli.ai.router.session import AISessionOverride
from titan_cli.core.models import AIConfig, AIConnectionConfig
from titan_cli.ui.tui.widgets.dock import ai_cells


def _cells(ai_config, **override):
    session = AISessionOverride()
    for name, value in override.items():
        setattr(session, name, value)
    cli, ai = ai_cells(ai_config, session)
    return {"cli": cli, "ai": ai}


def _gateway(model="gpt-5"):
    return AIConnectionConfig(
        name="Work gateway",
        connection_type="gateway",
        gateway_backend="openai_compatible",
        base_url="https://gateway.example/v1",
        default_model=model,
    )


def test_both_cells_name_the_key_that_changes_them():
    cells = _cells(
        AIConfig(
            default_cli="claude",
            cli_models={"claude": "opus"},
            default_connection="work",
            connections={"work": _gateway()},
        )
    )

    assert cells["cli"] == "F2 claude · opus"
    assert cells["ai"].startswith("F3 ")
    assert "gpt-5" in cells["ai"]


def test_an_unpinned_cli_model_reads_as_the_clis_own_default():
    """The CLI still has a model; Titan just isn't the one choosing it."""
    cells = _cells(AIConfig(default_cli="gemini"))

    assert cells["cli"] == "F2 gemini · default"


def test_nothing_configured_shows_a_dash_rather_than_a_stale_name():
    cells = _cells(AIConfig())

    assert cells["cli"] == "F2 —"
    assert cells["ai"] == "F3 —"


class TestSessionOverrideInTheDock:
    """
    An active session override takes over the F2 cell and marks itself (air-004, D-003).

    Showing the saved value while something else actually runs would make the dock lie -
    and this is the only place an override announces itself once the picker is closed.
    """

    @staticmethod
    def _cells_with_override(ai_config, *, cli=None, model=None):
        return _cells(ai_config, cli=cli, cli_model=model)

    def test_an_overridden_cli_replaces_the_saved_one_and_is_starred(self):
        cells = self._cells_with_override(
            AIConfig(default_cli="claude", cli_models={"claude": "opus"}), cli="codex"
        )

        assert cells["cli"] == "F2 codex · default ●"

    def test_an_overridden_model_shows_against_the_saved_cli(self):
        cells = self._cells_with_override(
            AIConfig(default_cli="claude", cli_models={"claude": "opus"}), model="haiku"
        )

        assert cells["cli"] == "F2 claude · haiku ●"

    def test_no_override_leaves_the_cell_exactly_as_it_was(self):
        cells = self._cells_with_override(
            AIConfig(default_cli="claude", cli_models={"claude": "opus"})
        )

        assert cells["cli"] == "F2 claude · opus"


class TestRemoteSessionOverrideInTheDock:
    """The F3 cell behaves like the F2 one once a connection can be overridden (D-006)."""

    @staticmethod
    def _cells(ai_config, *, connection=None, model=None, cli=None):
        return _cells(ai_config, connection=connection, connection_model=model, cli=cli)

    @staticmethod
    def _two_connections():
        return AIConfig(
            default_cli="claude",
            cli_models={"claude": "opus"},
            default_connection="work",
            connections={"work": _gateway("gpt-5"), "personal": _gateway("mini")},
        )

    def test_an_overridden_connection_takes_over_the_f3_cell(self):
        cells = self._cells(self._two_connections(), connection="personal")

        assert cells["ai"].endswith("· mini ●")

    def test_an_overridden_model_shows_in_the_f3_cell_too(self):
        cells = self._cells(self._two_connections(), model="gpt-5-mini")

        assert cells["ai"].endswith("· gpt-5-mini ●")

    def test_a_connection_only_override_leaves_the_f2_cell_alone(self):
        """Each key's cell answers for its own transport; neither claims the other's."""
        cells = self._cells(self._two_connections(), connection="personal")

        assert cells["cli"] == "F2 claude · opus"

    def test_a_cli_only_override_leaves_the_f3_cell_alone(self):
        cells = self._cells(self._two_connections(), cli="codex")

        assert cells["ai"].endswith("· gpt-5")
        assert "●" not in cells["ai"]


def test_a_mod_tile_shows_the_icon_over_the_label_and_its_badge_in_the_severity_color():
    from titan_cli.core.mods import DockSlot
    from titan_cli.ui.tui import colors
    from titan_cli.ui.tui.widgets.dock import slot_text

    text = slot_text(DockSlot("PRs", icon="🔀", badge="2", severity="error"))

    assert text.plain == "🔀\nPRs 2"
    assert colors.ERROR in str(text.spans[-1].style)


def test_a_plugin_tile_carries_every_badge_mods_put_on_it():
    from titan_cli.ui.tui.widgets.dock import plugin_tile, tile_text

    icon, label = plugin_tile("github")
    text = tile_text(icon, label, [("2 to review", "warning"), ("CI ✗", "error")])

    assert text.plain.endswith("GitHub 2 to review CI ✗")


def test_an_unknown_plugin_tile_reads_its_name_behind_the_plug():
    from titan_cli.ui.tui.icons import Icons
    from titan_cli.ui.tui.widgets.dock import plugin_tile

    assert plugin_tile("play-store") == (Icons.PLUGIN, "Play Store")
