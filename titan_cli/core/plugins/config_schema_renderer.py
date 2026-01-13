"""
Dynamic configuration schema renderer for plugins.

This module provides the ConfigSchemaRenderer class that translates JSON Schema
definitions from plugin.json into interactive UI prompts, allowing plugins to
define their configuration needs declaratively without writing UI code.
"""

import re
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path

from titan_cli.ui.views.prompts import PromptsRenderer
from titan_cli.ui.components.typography import TextRenderer
from titan_cli.ui.components.panel import PanelRenderer
from titan_cli.core.secrets import SecretManager
from titan_cli.core.config import TitanConfig


class ConfigSchemaRenderer:
    """
    Renders interactive configuration wizards based on JSON Schema.

    This class acts as a "dumb orchestrator" that translates the configSchema
    from a plugin's plugin.json into interactive prompts using PromptsRenderer.

    The plugin defines what it needs (JSON Schema), and this renderer handles
    the UI presentation, validation, and persistence automatically.

    Example:
        >>> schema = {
        ...     "type": "object",
        ...     "title": "JIRA Configuration",
        ...     "properties": {
        ...         "url": {
        ...             "type": "string",
        ...             "required": True,
        ...             "format": "uri",
        ...             "prompt": {"message": "JIRA URL:"}
        ...         },
        ...         "api_token": {
        ...             "type": "string",
        ...             "secret": True,
        ...             "prompt": {"message": "API Token:", "type": "password"}
        ...         }
        ...     }
        ... }
        >>> renderer = ConfigSchemaRenderer()
        >>> config = renderer.render_config_wizard(schema, "jira")
        # Shows interactive prompts and returns config dict
    """

    def __init__(self):
        """Initialize the renderer with UI components."""
        self.prompts = PromptsRenderer()
        self.text = TextRenderer()
        self.panel = PanelRenderer()
        self.secrets = SecretManager()

    def render_config_wizard(
        self,
        schema: Dict[str, Any],
        plugin_name: str,
        existing_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Render the complete configuration wizard for a plugin.

        Args:
            schema: The configSchema object from plugin.json
            plugin_name: Plugin identifier (used for secret key namespacing)
            existing_config: Existing configuration values (for reconfiguration)

        Returns:
            Dictionary with configuration values entered by the user.
            Secret values are saved to SecretManager and not returned.

        Raises:
            KeyboardInterrupt: If user cancels the wizard
            ValueError: If schema is invalid or required fields are missing
        """
        # Display wizard header
        title = schema.get('title', f'{plugin_name.title()} Configuration')
        self.text.title(f"⚙️  {title}")

        description = schema.get('description')
        if description:
            self.text.body(description, style="dim")

        self.text.line()

        # Process schema properties
        properties = schema.get('properties', {})
        if not properties:
            self.text.warning("No configuration required for this plugin")
            return {}

        config = existing_config.copy() if existing_config else {}

        # Render each field
        for field_name, field_schema in properties.items():
            try:
                value = self._render_field(
                    field_name,
                    field_schema,
                    config.get(field_name)
                )

                # Save value (secret or regular config)
                if field_schema.get('secret'):
                    # Save to secure storage with namespaced key
                    secret_key = f"{plugin_name.upper()}_{field_name.upper()}"
                    self.secrets.set(secret_key, value, scope="user")
                    self.text.body(f"  ✓ {field_name} saved securely", style="dim green")
                else:
                    # Save to config dict
                    config[field_name] = value

            except KeyboardInterrupt:
                self.text.line()
                self.text.warning("Configuration cancelled by user")
                raise
            except Exception as e:
                self.text.error(f"Error configuring {field_name}: {e}")
                raise

        self.text.line()
        self.text.success("✅ Configuration completed successfully!")

        return config

    def _render_field(
        self,
        name: str,
        schema: Dict[str, Any],
        default_value: Any = None
    ) -> Any:
        """
        Render a single configuration field based on its schema.

        Args:
            name: Field name
            schema: Field schema definition
            default_value: Existing value (if reconfiguring)

        Returns:
            User input value, type-converted and validated

        Raises:
            ValueError: If validation fails
        """
        field_type = schema.get('type', 'string')
        prompt_config = schema.get('prompt', {})
        message = prompt_config.get('message', schema.get('title', name))
        is_required = schema.get('required', False)

        # Use existing value or schema default
        if default_value is None:
            default_value = schema.get('default')

        # Show help text if available
        help_text = prompt_config.get('help')
        if help_text:
            self.text.body(f"  💡 {help_text}", style="dim cyan")

        # Route to appropriate renderer based on type
        if field_type == 'string':
            return self._render_string_field(name, schema, default_value, is_required)

        elif field_type == 'boolean':
            return self._render_boolean_field(message, default_value)

        elif field_type in ['integer', 'number']:
            return self._render_number_field(
                message,
                schema,
                default_value,
                is_required,
                is_integer=(field_type == 'integer')
            )

        elif field_type == 'array':
            return self._render_array_field(message, schema, default_value)

        elif field_type == 'object':
            return self._render_object_field(name, schema, default_value)

        else:
            # Fallback to text input
            return self.prompts.ask_text(
                message=message,
                default=str(default_value) if default_value else None
            )

    def _render_string_field(
        self,
        name: str,
        schema: Dict[str, Any],
        default_value: Any,
        is_required: bool
    ) -> str:
        """Render a string field (text, password, select, or validated)."""
        prompt_config = schema.get('prompt', {})
        message = prompt_config.get('message', schema.get('title', name))

        # String with enum → Select menu
        if 'enum' in schema:
            choices = []
            enum_values = schema['enum']

            # Use custom choices if provided
            if 'choices' in prompt_config:
                choices = prompt_config['choices']
            else:
                # Auto-generate choices from enum
                choices = [{'name': str(v), 'value': v} for v in enum_values]

            return self.prompts.ask_select(
                message=message,
                choices=choices,
                default=default_value
            )

        # String with secret flag → Password input
        elif schema.get('secret'):
            return self.prompts.ask_password(
                message=message,
                required=is_required
            )

        # Regular string with validation
        else:
            placeholder = prompt_config.get('placeholder')
            validator = self._get_validator(schema)

            while True:
                try:
                    value = self.prompts.ask_text(
                        message=message,
                        default=default_value or placeholder
                    )

                    # Check required
                    if is_required and not value:
                        self.text.error("  ✗ This field is required")
                        continue

                    # Run validator if present
                    if value and validator:
                        validator(value)

                    return value

                except ValueError as e:
                    self.text.error(f"  ✗ {e}")
                    continue

    def _render_boolean_field(
        self,
        message: str,
        default_value: Any
    ) -> bool:
        """Render a boolean field as yes/no confirmation."""
        default = default_value if default_value is not None else True
        return self.prompts.ask_confirm(
            message=message,
            default=default
        )

    def _render_number_field(
        self,
        message: str,
        schema: Dict[str, Any],
        default_value: Any,
        is_required: bool,
        is_integer: bool = True
    ) -> float:
        """Render a numeric field with validation."""
        min_val = schema.get('minimum')
        max_val = schema.get('maximum')

        # Build constraint message
        constraints = []
        if min_val is not None:
            constraints.append(f"min: {min_val}")
        if max_val is not None:
            constraints.append(f"max: {max_val}")

        if constraints:
            message = f"{message} ({', '.join(constraints)})"

        while True:
            value_str = self.prompts.ask_text(
                message=message,
                default=str(default_value) if default_value is not None else None
            )

            # Check required
            if is_required and not value_str:
                self.text.error("  ✗ This field is required")
                continue

            # Convert to number
            try:
                num = int(value_str) if is_integer else float(value_str)

                # Validate range
                if min_val is not None and num < min_val:
                    self.text.error(f"  ✗ Value must be >= {min_val}")
                    continue
                if max_val is not None and num > max_val:
                    self.text.error(f"  ✗ Value must be <= {max_val}")
                    continue

                return num

            except ValueError:
                number_type = "integer" if is_integer else "number"
                self.text.error(f"  ✗ Value must be a valid {number_type}")

    def _render_array_field(
        self,
        message: str,
        schema: Dict[str, Any],
        default_value: Any
    ) -> List[Any]:
        """Render an array field (multi-select or comma-separated)."""
        items_schema = schema.get('items', {})

        # Array with enum → Multi-select
        if 'enum' in items_schema:
            choices = [{'name': str(v), 'value': v} for v in items_schema['enum']]

            # PromptsRenderer doesn't have multiselect yet, fallback to manual
            self.text.body(f"{message} (select multiple, comma-separated):")
            for i, choice in enumerate(choices, 1):
                self.text.body(f"  {i}. {choice['name']}", style="dim")

            value_str = self.prompts.ask_text(
                message="Enter numbers (e.g., 1,3,5):",
                default=None
            )

            if not value_str:
                return default_value or []

            # Parse selections
            try:
                indices = [int(x.strip()) - 1 for x in value_str.split(',')]
                return [choices[i]['value'] for i in indices if 0 <= i < len(choices)]
            except (ValueError, IndexError):
                self.text.warning("Invalid selection, using default")
                return default_value or []

        # Free-form array (comma-separated)
        else:
            default_str = ','.join(map(str, default_value)) if default_value else None
            value_str = self.prompts.ask_text(
                message=f"{message} (comma-separated):",
                default=default_str
            )

            if not value_str:
                return []

            return [v.strip() for v in value_str.split(',') if v.strip()]

    def _render_object_field(
        self,
        name: str,
        schema: Dict[str, Any],
        default_value: Any
    ) -> Dict[str, Any]:
        """Render nested object field recursively."""
        self.text.subtitle(f"  {schema.get('title', name)}")
        self.text.line()

        # Recursive call to render nested schema
        return self.render_config_wizard(
            schema,
            name,
            default_value
        )

    def _get_validator(self, schema: Dict[str, Any]) -> Optional[Callable]:
        """
        Get validator function based on schema format/pattern.

        Args:
            schema: Field schema with format or pattern

        Returns:
            Validator function or None
        """
        # Format validators
        format_type = schema.get('format')
        if format_type == 'email':
            return self._validate_email
        elif format_type == 'uri':
            return self._validate_uri
        elif format_type == 'hostname':
            return self._validate_hostname

        # Pattern validator
        pattern = schema.get('pattern')
        if pattern:
            return lambda v: self._validate_pattern(v, pattern)

        # Length validators
        min_length = schema.get('minLength')
        max_length = schema.get('maxLength')
        if min_length or max_length:
            return lambda v: self._validate_length(v, min_length, max_length)

        return None

    @staticmethod
    def _validate_email(value: str) -> bool:
        """Validate email format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, value):
            raise ValueError("Invalid email format")
        return True

    @staticmethod
    def _validate_uri(value: str) -> bool:
        """Validate URI format (must start with http:// or https://)."""
        if not value.startswith(('http://', 'https://')):
            raise ValueError("URL must start with http:// or https://")
        return True

    @staticmethod
    def _validate_hostname(value: str) -> bool:
        """Validate hostname format."""
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
        if not re.match(pattern, value):
            raise ValueError("Invalid hostname format")
        return True

    @staticmethod
    def _validate_pattern(value: str, pattern: str) -> bool:
        """Validate value against regex pattern."""
        if not re.match(pattern, value):
            raise ValueError(f"Value does not match required pattern: {pattern}")
        return True

    @staticmethod
    def _validate_length(value: str, min_len: Optional[int], max_len: Optional[int]) -> bool:
        """Validate string length."""
        if min_len and len(value) < min_len:
            raise ValueError(f"Must be at least {min_len} characters")
        if max_len and len(value) > max_len:
            raise ValueError(f"Must be at most {max_len} characters")
        return True
