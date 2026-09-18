"""
The session-scoped AI override: what the user just chose with F2/F3, for now only.

Configuration answers "what should run my work from now on". This answers "run it on
this instead, for the moment" - trying something, working around a CLI that is having a
bad day, comparing two models on the same workflow. It is deliberately NOT persisted:
nothing here reaches `~/.titan/config.toml`, and closing the app forgets it.

It sits between a task's pin and an explicit call-site `model=` in the routing
precedence (ai_task_routing D-002):

    call-site model=  >  session override  >  task pin  >  global default

It overrides INSTANCES, never kinds: it can say "use gemini" or "use the other gateway",
but not "use a remote connection instead of a CLI" - that stays a per-task decision made
in the config screen. `cli` and `connection` therefore coexist, each applying only to the
kind it names, and each carries its own model for the same reason.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AISessionOverride:
    """
    A CLI and/or connection, each with its own model, chosen for this session only.

    Mutable on purpose: one instance lives on the app and is edited in place, so a
    workflow context built earlier keeps seeing the current value rather than a copy of
    whatever was set when it was built.

    The model is stored PER KIND. A single shared field made the two overrides interfere
    in both directions: a CLI identifier could be handed to a gateway, and choosing a CLI
    cleared a model that had been picked for a connection. They are different
    vocabularies, and `cli`/`connection` were already kept apart for exactly that reason.
    """

    cli: Optional[str] = None
    cli_model: Optional[str] = None
    connection: Optional[str] = None
    connection_model: Optional[str] = None

    @property
    def is_active(self) -> bool:
        """Whether anything is being overridden at all."""
        return bool(self.cli or self.connection or self.cli_model or self.connection_model)

    def clear(self) -> None:
        """Drop the override; saved configuration applies again."""
        self.cli = None
        self.cli_model = None
        self.connection = None
        self.connection_model = None

    def use_cli(self, cli: str) -> Optional[str]:
        """Override the CLI, forgetting a model chosen for a different one.

        Same rule as a task's pin: a model identifier only means something to the
        instance it was picked for, so `opus` must not survive a switch to codex. The
        connection's own model is untouched - it was never about this CLI.
        Returns the model it dropped, so the caller can say so.
        """
        dropped = self.cli_model if cli != self.cli else None
        self.cli = cli
        if dropped:
            self.cli_model = None
        return dropped

    def use_connection(self, connection: str) -> Optional[str]:
        """Override the connection, forgetting a model chosen for a different one."""
        dropped = self.connection_model if connection != self.connection else None
        self.connection = connection
        if dropped:
            self.connection_model = None
        return dropped

    def instance_for(self, remote: bool) -> Optional[str]:
        """The overridden instance for one kind of provider, if there is one.

        A CLI override and a connection override coexist - F2 sets one, F3 the other -
        and each applies only to the kind it names. Neither can make a task change kind.
        """
        return self.connection if remote else self.cli

    def model_for(self, remote: bool) -> Optional[str]:
        """The overridden model for one kind of provider, if there is one."""
        return self.connection_model if remote else self.cli_model

    def describe(self) -> str:
        """A short human summary, for a status line or a notification.

        Both halves when both are set: reporting only the CLI would leave a connection
        override invisible in the one place that announces it.
        """
        parts = [
            f"{instance} / {model}" if instance and model else (instance or model)
            for instance, model in (
                (self.cli, self.cli_model),
                (self.connection, self.connection_model),
            )
            if instance or model
        ]
        return " + ".join(parts)


__all__ = ["AISessionOverride"]
