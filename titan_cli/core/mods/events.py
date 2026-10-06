"""
Inputs of the events a mod can hook.

Each one is frozen: a hook that wants the rest of the chain to see something
different passes `dataclasses.replace(e, ...)` to `next`, it never mutates `e`.
"""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Optional


def _frozen(mapping: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(mapping))


@dataclass(frozen=True)
class WorkflowRun:
    """`workflow.run`: wraps a whole workflow. Before `next` is the start, after it the end."""

    workflow: str
    source: str
    nested: bool


@dataclass(frozen=True)
class StepCall:
    """
    `step.call`: wraps one step.

    Exactly one of `plugin`+`step`, `command` or `nested_workflow` is set, the
    same shapes a workflow YAML accepts. `params` is what the step will see; a
    hook that passes a replaced `params` to `next` changes it for the step.
    """

    workflow: str
    step_id: str
    step_name: str
    plugin: Optional[str] = None
    step: Optional[str] = None
    command: Optional[str] = None
    nested_workflow: Optional[str] = None
    params: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "params", _frozen(self.params))


@dataclass(frozen=True)
class AppStart:
    """`app.start`: the TUI has mounted. Open panes and start timers here; never block."""

    project_root: str


@dataclass(frozen=True)
class UIRender:
    """
    `ui.render`: draw one slot. Answer with an element tree from
    `titan_cli.core.mods.elements`, or `next(e)` to leave it to others.

    `component` is the slot (`"Pane"` for now), `pane` the id the mod opened it
    with, `width` the columns the slot has.
    """

    component: str
    pane: Optional[str]
    width: int
