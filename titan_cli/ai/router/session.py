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

    # Which instance each model was chosen FOR. Without it the guard cannot tell "same
    # instance, keep the model" from "different instance, drop it" whenever the model
    # was picked before any instance was named - and either answer is wrong half the
    # time. A bare model with no owner is the shape both this module and the resolver's
    # rung guard exist to prevent.
    _cli_model_for: Optional[str] = None
    _connection_model_for: Optional[str] = None

    @property
    def is_active(self) -> bool:
        """Whether anything is being overridden at all."""
        return bool(self.cli or self.connection or self.cli_model or self.connection_model)

    def clear(self) -> None:
        """Drop the override; saved configuration applies again."""
        self.cli = None
        self.cli_model = None
        self._cli_model_for = None
        self.connection = None
        self.connection_model = None
        self._connection_model_for = None

    def set_cli_model(self, cli: Optional[str], model: Optional[str]) -> None:
        """Record a session model together with the CLI it was chosen for."""
        self.cli_model = model
        self._cli_model_for = cli if model else None

    def set_connection_model(self, connection: Optional[str], model: Optional[str]) -> None:
        """Record a session model together with the connection it was chosen for."""
        self.connection_model = model
        self._connection_model_for = connection if model else None

    def use_cli(self, cli: str) -> Optional[str]:
        """Override the CLI, forgetting a model chosen for a different one.

        Same rule as a task's pin: a model identifier only means something to the
        instance it was picked for, so `opus` must not survive a switch to codex. The
        connection's own model is untouched - it was never about this CLI.
        Returns the model it dropped, so the caller can say so.
        """
        # Compared against the instance the MODEL was chosen for, not against the
        # currently overridden one: a model-only override leaves `cli` unset, so
        # comparing with it either drops a model chosen for this very CLI or keeps one
        # chosen for another, depending on which way the guard leans.
        owner = self._cli_model_for or self.cli
        dropped = self.cli_model if (owner is not None and cli != owner) else None
        # Cleared BEFORE the new instance is published: the resolver reads this object
        # from the workflow thread while F2/F3 mutate it from the UI thread, and its
        # instance and model reads are separated by an availability probe - so the
        # other order leaves a real window of new-CLI-with-old-model.
        if dropped:
            self.cli_model = None
            self._cli_model_for = None
        self.cli = cli
        if self.cli_model and self._cli_model_for is None:
            self._cli_model_for = cli
        return dropped

    def use_connection(self, connection: str) -> Optional[str]:
        """Override the connection, forgetting a model chosen for a different one."""
        owner = self._connection_model_for or self.connection
        dropped = (
            self.connection_model if (owner is not None and connection != owner) else None
        )
        if dropped:
            self.connection_model = None
            self._connection_model_for = None
        self.connection = connection
        if self.connection_model and self._connection_model_for is None:
            self._connection_model_for = connection
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

    def is_active_for(self, remote: bool) -> bool:
        """Whether THIS kind is overridden. The other kind is not this caller's business."""
        return bool(self.instance_for(remote) or self.model_for(remote))

    def clear_for(self, remote: bool) -> None:
        """Drop only this kind's override, leaving the other alone.

        The two are set by different keys and reported in different places, so clearing
        one from the other's picker would remove a setting the user cannot even see from
        there.
        """
        if remote:
            self.connection = None
            self.connection_model = None
            self._connection_model_for = None
        else:
            self.cli = None
            self.cli_model = None
            self._cli_model_for = None

    def describe_for(self, remote: bool) -> str:
        """A short summary of THIS kind's override only."""
        instance = self.instance_for(remote)
        model = self.model_for(remote)
        if instance and model:
            return f"{instance} / {model}"
        return instance or model or ""

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
