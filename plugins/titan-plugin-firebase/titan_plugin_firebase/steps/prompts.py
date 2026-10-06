"""
Shared prompt helpers for the Firebase steps.

Kept in one place because the single-project and multi-project flows have to ask
for the same things the same way: a parameter, a write target, and a value
whose input shape depends on its type.
"""

from __future__ import annotations

from typing import Any, Optional

from titan_cli.ui.tui.widgets import ChoiceOption, OptionItem

from ..models.values import RemoteConfigValueType

# Sentinel for "the parameter's default value", which is not a condition but is
# one of the choices a write target can take.
DEFAULT_TARGET = "__default__"

# Above this many parameters a flat list stops being navigable.
FILTER_THRESHOLD = 25


def blank_to_none(value: Any) -> Optional[str]:
    """
    Treat an empty workflow param as absent.

    Workflows declare optional params with an empty default, so `""` means
    "the user did not pass one", not "write an empty string".
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_value_type(raw: Any) -> RemoteConfigValueType:
    """Normalize a value type coming from workflow data."""
    from ..models.values import normalize_value_type as normalize_model_value_type

    return normalize_model_value_type(raw)


def ask_condition(ctx, template) -> tuple[Optional[str], bool]:
    """
    Ask which value of a parameter to write: the default or a condition.

    Returns:
        The condition name (None for the default value) and whether the user
        answered at all — a cancelled prompt is not the same as choosing the
        default.
    """
    if not template.conditions:
        return None, True

    options = [
        OptionItem(
            value=DEFAULT_TARGET,
            title="Valor por defecto",
            description="Se aplica cuando ninguna condición coincide",
        )
    ]
    options.extend(
        OptionItem(
            value=condition.name,
            title=condition.name,
            description=condition.display_expression,
        )
        for condition in template.conditions
    )

    selected = ctx.textual.ask_option("¿Sobre qué valor quieres trabajar?", options)
    if selected is None:
        return None, False
    return (None if selected == DEFAULT_TARGET else str(selected)), True


def ask_parameter(ctx, template, condition: Optional[str]):
    """
    Ask which parameter to change, filtering first when there are many.

    Returns the selected UI parameter, or None if the user cancelled or nothing
    matched the filter.
    """
    candidates = list(template.parameters)
    if not candidates:
        return None

    if len(candidates) > FILTER_THRESHOLD:
        needle = ctx.textual.ask_text(
            f"{len(candidates)} parámetros. Filtra por texto (vacío = todos):",
            default="",
        )
        if needle:
            lowered = needle.strip().lower()
            candidates = [
                parameter
                for parameter in candidates
                if lowered in parameter.key.lower()
                or lowered in (parameter.description or "").lower()
            ]
            if not candidates:
                return None

    selected = ctx.textual.ask_option(
        "¿Qué parámetro?",
        [
            OptionItem(
                value=parameter.key,
                title=parameter.key,
                description=describe_parameter(parameter, condition),
            )
            for parameter in candidates
        ],
    )
    if selected is None:
        return None
    return template.parameter(str(selected))


def describe_parameter(parameter, condition: Optional[str]) -> str:
    """One-line description of a parameter for the chosen target."""
    parts = [parameter.type_label, display_for_target(parameter, condition)]
    if parameter.description:
        parts.append(parameter.description)
    return " · ".join(part for part in parts if part)


def display_for_target(parameter, condition: Optional[str]) -> str:
    """Render a parameter's value for one target, flagging inheritance."""
    value = parameter.value_for(condition)
    if value is None:
        if condition is None:
            return "—"
        default = parameter.default_value
        return f"(hereda) {default.display_value if default else '—'}"
    return value.display_value


def ask_value(
    ctx,
    key: str,
    value_type: RemoteConfigValueType,
    current_value: Optional[object],
    condition: Optional[object],
) -> Optional[str]:
    """Prompt for a new value in the shape the type calls for."""
    target = condition or "valor por defecto"
    current = str(current_value) if current_value is not None else ""

    if value_type == RemoteConfigValueType.BOOLEAN:
        chosen = ctx.textual.ask_choice(
            f"{key} [{target}] — valor actual: {current or '(sin valor)'}",
            options=[
                ChoiceOption(value="true", label="true", variant="success"),
                ChoiceOption(value="false", label="false", variant="error"),
            ],
        )
        return str(chosen) if chosen is not None else None

    if value_type.supports_multiline_input:
        # JSON values are routinely multi-line; a single-line input would make
        # anything non-trivial uneditable.
        return ctx.textual.ask_multiline(
            f"{key} [{target}] — JSON:",
            default=current,
        )

    return ctx.textual.ask_text(
        f"{key} [{target}] — nuevo valor ({value_type.prompt_hint}):",
        default=current,
    )
