"""
The session-scoped AI override: what the user just chose with F2/F3, for now only.

Configuration answers "what should run my work from now on". This answers "run it on
this instead, for the moment" - trying something, working around a CLI that is having a
bad day, comparing two models on the same workflow. It is deliberately NOT persisted:
nothing here reaches `~/.titan/config.toml`, and closing the app forgets it.

It sits between a task's pin and an explicit call-site `model=` in the routing
precedence (ai_task_routing D-002):

    call-site model=  >  session override  >  task pin  >  global default

It overrides INSTANCES, never kinds: it can say "use gemini" but not "use a remote
connection instead of a CLI", which stays a per-task decision made in the config screen.
A remote connection's model is also out of scope - that model lives inside the provider
the connection builds, not in anything the router passes along.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AISessionOverride:
    """
    A CLI and/or model chosen for this session only.

    Mutable on purpose: one instance lives on the app and is edited in place, so a
    workflow context built earlier keeps seeing the current value rather than a copy of
    whatever was set when it was built.
    """

    cli: Optional[str] = None
    model: Optional[str] = None

    @property
    def is_active(self) -> bool:
        """Whether anything is being overridden at all."""
        return bool(self.cli or self.model)

    def clear(self) -> None:
        """Drop the override; saved configuration applies again."""
        self.cli = None
        self.model = None

    def describe(self) -> str:
        """A short human summary, for a status line or a notification."""
        if self.cli and self.model:
            return f"{self.cli} / {self.model}"
        return self.cli or self.model or ""


__all__ = ["AISessionOverride"]
