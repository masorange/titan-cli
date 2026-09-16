"""
Shared prompt helpers for the Firebase steps.

Kept in one place because the single-project and multi-project flows have to ask
for the same things the same way: a parameter, a write target, and a value
whose input shape depends on its type.
"""

from __future__ import annotations

from typing import Any, Optional

from titan_cli.ui.tui.widgets import ChoiceOption, OptionItem, SelectionOption

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
    if isinstance(raw, RemoteConfigValueType):
        return raw
    if isinstance(raw, str):
        return RemoteConfigValueType.__members__.get(
            raw.strip().upper(),
            RemoteConfigValueType.UNKNOWN,
        )
    return RemoteConfigValueType.UNKNOWN


def normalize_target(value: Any) -> Optional[str]:
    """Map the textual forms of "the default value" to None."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"default", "defaultvalue", DEFAULT_TARGET}:
        return None
    return text


def condition_option_label(condition, *, max_expression: int = 90) -> str:
    """
    One-line label for a condition in a selection list.

    The expression is what tells two similarly named conditions apart, so it
    is kept — collapsed to one line and truncated, because these run long.
    """
    expression = condition.display_expression
    if len(expression) > max_expression:
        expression = f"{expression[: max_expression - 1]}…"
    return f"{condition.name} — {expression}"


def ask_targets(ctx, template) -> list[Optional[str]]:
    """
    Ask which values of a parameter to write: the default, conditions, or both.

    Returns the selected targets (None means the default value), or an empty
    list if the user cancelled — which is not the same as choosing the default.
    """
    if not template.conditions:
        return [None]

    options = [
        SelectionOption(
            value=DEFAULT_TARGET,
            label="Valor por defecto — se aplica si ninguna condición coincide",
            selected=False,
        )
    ]
    options.extend(
        SelectionOption(
            value=condition.name,
            label=condition_option_label(condition),
            selected=False,
        )
        for condition in template.conditions
    )

    selected = ctx.textual.ask_multiselect(
        "¿Sobre qué valores quieres escribir?",
        options,
    )
    if not selected:
        return []
    return [normalize_target(value) for value in selected]


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
    parts = [parameter.value_type.value, display_for_target(parameter, condition)]
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

    if value_type == RemoteConfigValueType.JSON:
        # JSON values are routinely multi-line; a single-line input would make
        # anything non-trivial uneditable.
        return ctx.textual.ask_multiline(
            f"{key} [{target}] — JSON:",
            default=current,
        )

    hint = "número" if value_type == RemoteConfigValueType.NUMBER else "texto"
    return ctx.textual.ask_text(
        f"{key} [{target}] — nuevo valor ({hint}):",
        default=current,
    )
