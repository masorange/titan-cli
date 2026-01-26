from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static

from titan_cli.ui.tui.widgets.statusbar import StatusBarWidget

class StatusBarPreviewApp(App):
    """
    Una aplicación de Textual para previsualizar el StatusBarWidget.
    """
    CSS_PATH = "../../tui/widgets/statusbar.css" # Ruta relativa al CSS del widget
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("b", "cycle_branch", "Cycle Branch"),
        ("a", "cycle_ai_status", "Cycle AI Status"),
        ("p", "cycle_project", "Cycle Project")
    ]

    def on_mount(self) -> None:
        self.set_interval(2, self.action_cycle_branch) # Cambiar la rama cada 2 segundos

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Pulsa 'q' para salir, 'b' para cambiar la branch, 'a' para AI Status, 'p' para Project.", classes="instructions")
        yield StatusBarWidget()
        yield Footer()

    def action_cycle_branch(self) -> None:
        """Cicla el nombre de la branch y actualiza el badge."""
        branch_badge = self.query_one("#branch-info", StatusBarWidget.BadgeWidget) # Acceder a la clase interna
        current_branch = branch_badge._value
        if current_branch == "N/A":
            new_branch = "main"
            new_type = "success"
        elif current_branch == "main":
            new_branch = "develop"
            new_type = "warning"
        elif current_branch == "develop":
            new_branch = "feature/new-feature"
            new_type = "info"
        elif current_branch.startswith("feature/"):
            new_branch = "bugfix/critical-fix"
            new_type = "error"
        else:
            new_branch = "N/A"
            new_type = "info" # Volvemos al valor por defecto
        
        # Eliminar las clases existentes y añadir la nueva
        for cls in list(branch_badge.classes):
            if cls.startswith("type--"):
                branch_badge.remove_class(cls)
        branch_badge.add_class(f"type--{new_type}")
        branch_badge.update_value(new_branch)
        branch_badge._badge_type = new_type # Actualizamos el tipo interno para futuras comparaciones

    def action_cycle_ai_status(self) -> None:
        """Cicla el estado de AI y actualiza el badge."""
        ai_badge = self.query_one("#ai-info", StatusBarWidget.BadgeWidget)
        current_status = ai_badge._value
        if current_status == "Ready":
            new_status = "Thinking..."
            new_type = "info"
        elif current_status == "Thinking...":
            new_status = "Error!"
            new_type = "error"
        else:
            new_status = "Ready"
            new_type = "success"

        for cls in list(ai_badge.classes):
            if cls.startswith("type--"):
                ai_badge.remove_class(cls)
        ai_badge.add_class(f"type--{new_type}")
        ai_badge.update_value(new_status)
        ai_badge._badge_type = new_type

    def action_cycle_project(self) -> None:
        """Cicla el nombre del proyecto y actualiza el badge."""
        project_badge = self.query_one("#project-info", StatusBarWidget.BadgeWidget)
        current_project = project_badge._value
        if current_project == "titan-cli":
            new_project = "another-project"
        else:
            new_project = "titan-cli"
        
        project_badge.update_value(new_project) # El tipo de proyecto no cambia el color aquí

if __name__ == "__main__":
    StatusBarPreviewApp().run()
