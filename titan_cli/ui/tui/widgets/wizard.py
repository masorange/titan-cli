"""
Wizard Widgets

Reusable building blocks for multi-step wizard screens:
  - StepStatus  — StrEnum for indicator state
  - WizardStep  — typed model for a single wizard step
  - StepIndicator — widget that renders a step with its status
"""

from dataclasses import dataclass
from enum import StrEnum

from textual.widgets import Static

from titan_cli.ui.tui.icons import Icons


class StepStatus(StrEnum):
    PENDING     = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED   = "completed"


@dataclass
class WizardStep:
    """Model for a single step in a multi-step wizard."""
    id: str
    title: str


class StepIndicator(Static):
    """Widget that renders a wizard step with its current status."""

    def __init__(self, step_number: int, step: WizardStep, status: StepStatus = StepStatus.PENDING):
        self.step_number = step_number
        self.step = step
        self.status = status
        super().__init__()

    def render(self) -> str:
        match self.status:
            case StepStatus.COMPLETED:
                icon, style = Icons.SUCCESS, "dim"
            case StepStatus.IN_PROGRESS:
                icon, style = Icons.RUNNING, "bold cyan"
            case _:
                icon, style = Icons.PENDING, "dim"

        return f"[{style}]{icon} {self.step_number}. {self.step.title}[/{style}]"
