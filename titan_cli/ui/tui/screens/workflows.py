"""
Workflows Screen

Screen for listing and executing workflows.
"""

from textual.app import ComposeResult
from textual.widgets import Static, OptionList
from textual.widgets.option_list import Option
from textual.containers import Container
from textual.containers import Horizontal
from textual.css.query import NoMatches

from .base import BaseScreen

class WorkflowsScreen(BaseScreen):
    """
    Workflows screen for selecting and executing workflows.

    Lists all available workflows and allows the user to:
    - View workflow details
    - Execute workflows
    - Go back to main menu
    """

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("q", "go_back", "Back"),
        ("left", "focus_plugins", "Plugins"),
        ("right", "focus_workflows", "Workflows"),
        ("tab", "focus_next", "Next Panel"),
    ]

    def __init__(self, config):
        super().__init__(config)
        self.selected_plugin = "all"  # Track selected plugin filter (start with "all")
        self._is_mounting = False  # Flag to prevent auto-update during mount
        self._all_workflows = None  # Cache for discovered workflows
        self._plugin_source_map = {}  # Map plugin names to their source identifiers

    def on_mount(self) -> None:
        """Initialize the screen with first options highlighted."""
        self._is_mounting = True

        try:
            # Highlight first plugin option
            plugin_list = self.query_one("#plugin-list", OptionList)
            if len(plugin_list._options) > 0:
                plugin_list.highlighted = 0

            # Highlight first workflow option
            workflow_list = self.query_one("#workflow-list", OptionList)
            if len(workflow_list._options) > 0:
                workflow_list.highlighted = 0
        except (NoMatches, AttributeError):
            pass
        finally:
            # Re-enable auto-filtering after mount completes
            self._is_mounting = False


    CSS = """
    WorkflowsScreen {
        align: center middle;
    }

    #workflows-container {
        width: 100%;
        height: 1fr;
        background: $surface-lighten-1;
    }

    #workflows-title {
        text-align: center;
        color: $primary;
        text-style: bold;
        margin-bottom: 1;
    }

    #workflows-container Horizontal {
        width: 100%;
        height: 1fr;
        padding: 1;
    }

    #left-panel {
        width: 20%;
        height: 100%;
        border: round $primary;
        border-title-align: center;
        background: $surface-lighten-1;
        padding: 0;
    }

    #left-panel OptionList {
        height: 100%;
        width: 100%;
        padding: 1 0;
        margin: 0;
    }

    #right-panel {
        width: 80%;
        height: 100%;
        border: round $primary;
        border-title-align: center;
        background: $surface-lighten-1;
        padding: 0;
    }

    #right-panel OptionList {
        height: 100%;
        width: 100%;
        padding: 1 0;
        margin: 0;
    }

    OptionList > .option-list--option {
        padding: 1;
    }
    """

    def compose_content(self) -> ComposeResult:
        """Compose the workflows screen content."""
        all_workflows = self.config.workflows.discover()

        # Cache and remove duplicates
        self._all_workflows = self._remove_duplicate_workflows(all_workflows)
        with Container(id="workflows-container"):
            yield Static("⚡ Available Workflows", id="workflows-title")

            if not self._all_workflows:
                yield Static("No workflows found.", id="no-workflows")
            else:
                # Get unique plugin names and create mapping
                plugin_names = set()
                self._plugin_source_map = {}  # Map formatted name -> workflow info objects

                for wf_info in self._all_workflows:
                    plugin_name = self._get_plugin_name_from_workflow(wf_info)
                    plugin_names.add(plugin_name)

                    # Map plugin name to workflow info objects for filtering
                    if plugin_name not in self._plugin_source_map:
                        self._plugin_source_map[plugin_name] = []
                    self._plugin_source_map[plugin_name].append(wf_info)

                # Build plugin filter options
                plugin_options = [Option("📦 All Plugins", id="all")]
                for plugin_name in sorted(plugin_names):
                    plugin_options.append(Option(f"🔌 {plugin_name}", id=plugin_name))

                # Build workflow options (initially show all)
                workflow_options = self._build_workflow_options(self._all_workflows)

                with Horizontal():
                    left_panel = Container(id="left-panel")
                    left_panel.border_title = "Plugins"
                    with left_panel:
                        yield OptionList(*plugin_options, id="plugin-list")

                    right_panel = Container(id="right-panel")
                    right_panel.border_title = "Workflows"
                    with right_panel:
                        yield OptionList(*workflow_options, id="workflow-list")

    def _get_plugin_name_from_workflow(self, wf_info) -> str:
        """
        Get the actual plugin name for a workflow, detecting the real plugin even for project/user workflows.

        Examples:
            Plugin workflow: "plugin:github" -> "Github"
            Project workflow using GitHub steps -> "Github"
            Project workflow using Jira steps -> "Jira"
            Project workflow with no plugins -> "Custom"
        """
        # If it's already from a plugin, extract the name
        if wf_info.source.startswith("plugin:"):
            plugin_name = wf_info.source.split(":", 1)[1]
            return plugin_name.capitalize()

        # For project/user workflows, check which plugin they use
        if wf_info.source in ["project", "user"]:
            if wf_info.required_plugins:
                # Use the first required plugin (most workflows use only one)
                primary_plugin = sorted(wf_info.required_plugins)[0]
                return primary_plugin.capitalize()
            else:
                # No plugin dependencies, it's a custom workflow
                return "Custom"

        # Fallback for other sources
        return wf_info.source.capitalize()

    def _remove_duplicate_workflows(self, workflows):
        """Remove duplicate workflows by name, keeping first occurrence."""
        seen = set()
        unique_workflows = []
        for wf in workflows:
            if wf.name not in seen:
                seen.add(wf.name)
                unique_workflows.append(wf)
        return unique_workflows

    def _build_workflow_options(self, workflows, selected_plugin=None):
        """Build workflow options, optionally filtered by plugin."""
        options = []

        # Get workflows for selected plugin
        if selected_plugin and selected_plugin != "all":
            # Use the pre-mapped workflows for this plugin
            workflows_to_show = self._plugin_source_map.get(selected_plugin, [])
        else:
            # Show all workflows
            workflows_to_show = workflows

        for wf_info in workflows_to_show:
            label = f"{wf_info.name.capitalize()}"
            description = f"{wf_info.description}"
            options.append(
                Option(f"{label}\n[dim]{description}[/dim]", id=wf_info.name)
            )

        return options if options else [Option("No workflows found", id="none", disabled=True)]

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Handle plugin navigation - auto-filter when highlighting."""
        # Ignore during mount to prevent duplicate updates
        if self._is_mounting:
            return

        if event.option_list.id == "plugin-list":
            # Only update if plugin actually changed to avoid duplicate updates
            if self.selected_plugin != event.option.id:
                self.selected_plugin = event.option.id
                self._update_workflow_list()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle workflow selection (Enter key)."""
        if event.option_list.id == "workflow-list":
            # Workflow selected - execute it
            workflow_name = event.option.id
            if workflow_name != "none":  # Don't execute disabled placeholder
                self.execute_workflow(workflow_name)

    def _update_workflow_list(self) -> None:
        """Update the workflow list based on selected plugin filter."""
        # Use cached workflows instead of discovering again
        workflow_options = self._build_workflow_options(self._all_workflows, self.selected_plugin)

        # Get the workflow list widget and replace its options
        workflow_list = self.query_one("#workflow-list", OptionList)

        # Clear and add in one operation
        workflow_list.clear_options()
        workflow_list.add_options(workflow_options)

        # Force refresh to update display
        workflow_list.refresh()

    def execute_workflow(self, workflow_name: str) -> None:
        """
        Execute a workflow.

        Args:
            workflow_name: Name of the workflow to execute
        """
        # TODO: Implement workflow execution
        # For now, just show a notification
        self.app.notify(f"Executing workflow: {workflow_name} - Coming soon!")

    def action_go_back(self) -> None:
        """Go back to main menu."""
        self.app.pop_screen()

    def action_focus_plugins(self) -> None:
        """Focus on the plugins panel."""
        try:
            plugin_list = self.query_one("#plugin-list", OptionList)
            plugin_list.focus()
        except NoMatches:
            pass

    def action_focus_workflows(self) -> None:
        """Focus on the workflows panel."""
        try:
            workflow_list = self.query_one("#workflow-list", OptionList)
            workflow_list.focus()
            # Ensure first item is highlighted if nothing is selected
            if workflow_list.highlighted is None and len(workflow_list._options) > 0:
                workflow_list.highlighted = 0
        except NoMatches:
            pass
