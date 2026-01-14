"""
Tests for ConfigSchemaRenderer - Dynamic plugin configuration.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from titan_cli.core.plugins.config_schema_renderer import ConfigSchemaRenderer


@pytest.fixture
def renderer():
    """Create a ConfigSchemaRenderer instance with mocked UI components."""
    with patch('titan_cli.core.plugins.config_schema_renderer.PromptsRenderer') as mock_prompts, \
         patch('titan_cli.core.plugins.config_schema_renderer.TextRenderer') as mock_text, \
         patch('titan_cli.core.plugins.config_schema_renderer.SecretManager') as mock_secrets:

        renderer = ConfigSchemaRenderer()
        renderer.prompts = mock_prompts.return_value
        renderer.text = mock_text.return_value
        renderer.secrets = mock_secrets.return_value

        return renderer


class TestConfigSchemaRenderer:
    """Test suite for ConfigSchemaRenderer."""

    def test_render_string_field_basic(self, renderer):
        """Test rendering a basic string field."""
        schema = {
            'type': 'string',
            'prompt': {'message': 'Enter name:'}
        }

        renderer.prompts.ask_text.return_value = 'test_value'

        result = renderer._render_field('name', schema, None)

        assert result == 'test_value'
        renderer.prompts.ask_text.assert_called_once()

    def test_render_password_field(self, renderer):
        """Test rendering a password field (secret)."""
        schema = {
            'type': 'string',
            'secret': True,
            'prompt': {'message': 'Enter API Key:'}
        }

        renderer.prompts.ask_password.return_value = 'secret123'

        result = renderer._render_field('api_key', schema, None)

        assert result == 'secret123'
        renderer.prompts.ask_password.assert_called_once_with(
            message='Enter API Key:',
            required=False
        )

    def test_render_select_field(self, renderer):
        """Test rendering a select field (enum)."""
        schema = {
            'type': 'string',
            'enum': ['option1', 'option2', 'option3'],
            'prompt': {'message': 'Choose option:'}
        }

        renderer.prompts.ask_choice.return_value = 'option2'

        result = renderer._render_field('mode', schema, None)

        assert result == 'option2'
        renderer.prompts.ask_choice.assert_called_once()

        # Check choices were auto-generated from enum
        call_args = renderer.prompts.ask_choice.call_args
        assert call_args[1]['choices'] == ['option1', 'option2', 'option3']

    def test_render_select_field_custom_choices(self, renderer):
        """Test rendering select field with custom choice labels."""
        schema = {
            'type': 'string',
            'enum': ['val1', 'val2'],
            'prompt': {
                'message': 'Choose:',
                'choices': [
                    {'name': 'Label 1', 'value': 'val1'},
                    {'name': 'Label 2', 'value': 'val2'}
                ]
            }
        }

        renderer.prompts.ask_choice.return_value = 'val1'

        result = renderer._render_field('choice', schema, None)

        assert result == 'val1'

        # Check custom choices were used (only values extracted)
        call_args = renderer.prompts.ask_choice.call_args
        assert call_args[1]['choices'] == ['val1', 'val2']

    def test_render_boolean_field(self, renderer):
        """Test rendering a boolean field."""
        schema = {
            'type': 'boolean',
            'prompt': {'message': 'Enable feature?'}
        }

        renderer.prompts.ask_confirm.return_value = True

        result = renderer._render_field('enabled', schema, None)

        assert result is True
        renderer.prompts.ask_confirm.assert_called_once_with(
            question='Enable feature?',
            default=True
        )

    def test_render_boolean_field_custom_default(self, renderer):
        """Test boolean field with custom default."""
        schema = {
            'type': 'boolean',
            'default': False,
            'prompt': {'message': 'Enable?'}
        }

        renderer.prompts.ask_confirm.return_value = False

        result = renderer._render_field('enabled', schema, None)

        assert result is False
        renderer.prompts.ask_confirm.assert_called_once_with(
            question='Enable?',
            default=False
        )

    def test_render_integer_field(self, renderer):
        """Test rendering an integer field."""
        schema = {
            'type': 'integer',
            'minimum': 1,
            'maximum': 100,
            'prompt': {'message': 'Enter timeout:'}
        }

        renderer.prompts.ask_text.return_value = '30'

        result = renderer._render_field('timeout', schema, None)

        assert result == 30
        assert isinstance(result, int)

    def test_render_integer_field_validation_min(self, renderer):
        """Test integer field validates minimum value."""
        schema = {
            'type': 'integer',
            'minimum': 10,
            'prompt': {'message': 'Enter value:'}
        }

        # First returns value too small, then valid value
        renderer.prompts.ask_text.side_effect = ['5', '15']

        result = renderer._render_field('value', schema, None)

        assert result == 15
        # Should have been called twice (once failed, once succeeded)
        assert renderer.prompts.ask_text.call_count == 2

    def test_render_integer_field_validation_max(self, renderer):
        """Test integer field validates maximum value."""
        schema = {
            'type': 'integer',
            'maximum': 100,
            'prompt': {'message': 'Enter value:'}
        }

        # First returns value too large, then valid value
        renderer.prompts.ask_text.side_effect = ['150', '50']

        result = renderer._render_field('value', schema, None)

        assert result == 50
        assert renderer.prompts.ask_text.call_count == 2

    def test_validate_email_valid(self, renderer):
        """Test email validation with valid email."""
        assert renderer._validate_email('user@example.com') is True
        assert renderer._validate_email('test.user+tag@domain.co.uk') is True

    def test_validate_email_invalid(self, renderer):
        """Test email validation with invalid email."""
        with pytest.raises(ValueError, match="Invalid email format"):
            renderer._validate_email('not-an-email')

        with pytest.raises(ValueError, match="Invalid email format"):
            renderer._validate_email('missing@domain')

    def test_validate_uri_valid(self, renderer):
        """Test URI validation with valid URLs."""
        assert renderer._validate_uri('https://example.com') is True
        assert renderer._validate_uri('http://localhost:8080') is True

    def test_validate_uri_invalid(self, renderer):
        """Test URI validation with invalid URLs."""
        with pytest.raises(ValueError, match="must start with http"):
            renderer._validate_uri('ftp://example.com')

        with pytest.raises(ValueError, match="must start with http"):
            renderer._validate_uri('example.com')

    def test_validate_pattern_valid(self, renderer):
        """Test pattern validation with matching value."""
        pattern = r'^[A-Z]{2,4}$'
        assert renderer._validate_pattern('ABC', pattern) is True
        assert renderer._validate_pattern('ABCD', pattern) is True

    def test_validate_pattern_invalid(self, renderer):
        """Test pattern validation with non-matching value."""
        pattern = r'^[A-Z]{2,4}$'

        with pytest.raises(ValueError, match="does not match required pattern"):
            renderer._validate_pattern('abc', pattern)  # lowercase

        with pytest.raises(ValueError, match="does not match required pattern"):
            renderer._validate_pattern('ABCDE', pattern)  # too long

    def test_validate_length_min(self, renderer):
        """Test length validation minimum."""
        assert renderer._validate_length('test', min_len=3, max_len=None) is True

        with pytest.raises(ValueError, match="at least 5 characters"):
            renderer._validate_length('test', min_len=5, max_len=None)

    def test_validate_length_max(self, renderer):
        """Test length validation maximum."""
        assert renderer._validate_length('test', min_len=None, max_len=10) is True

        with pytest.raises(ValueError, match="at most 3 characters"):
            renderer._validate_length('test', min_len=None, max_len=3)

    def test_string_field_with_email_format(self, renderer):
        """Test string field with email format validation."""
        schema = {
            'type': 'string',
            'format': 'email',
            'required': True,
            'prompt': {'message': 'Email:'}
        }

        # Invalid email, then valid
        renderer.prompts.ask_text.side_effect = ['invalid', 'user@example.com']

        result = renderer._render_field('email', schema, None)

        assert result == 'user@example.com'
        assert renderer.prompts.ask_text.call_count == 2

    def test_string_field_with_uri_format(self, renderer):
        """Test string field with URI format validation."""
        schema = {
            'type': 'string',
            'format': 'uri',
            'prompt': {'message': 'URL:'}
        }

        # Invalid URI, then valid
        renderer.prompts.ask_text.side_effect = ['example.com', 'https://example.com']

        result = renderer._render_field('url', schema, None)

        assert result == 'https://example.com'
        assert renderer.prompts.ask_text.call_count == 2

    def test_render_config_wizard_full(self, renderer):
        """Test full wizard with multiple fields."""
        schema = {
            'title': 'Test Plugin Config',
            'description': 'Configure test plugin',
            'properties': {
                'url': {
                    'type': 'string',
                    'format': 'uri',
                    'prompt': {'message': 'URL:'}
                },
                'api_key': {
                    'type': 'string',
                    'secret': True,
                    'prompt': {'message': 'API Key:'}
                },
                'enabled': {
                    'type': 'boolean',
                    'default': True,
                    'prompt': {'message': 'Enable?'}
                }
            }
        }

        # Mock responses
        renderer.prompts.ask_text.return_value = 'https://example.com'
        renderer.prompts.ask_password.return_value = 'secret123'
        renderer.prompts.ask_confirm.return_value = True

        config = renderer.render_config_wizard(schema, 'test_plugin')

        # Check config has non-secret values
        assert config['url'] == 'https://example.com'
        assert config['enabled'] is True

        # Secret should NOT be in config (saved separately)
        assert 'api_key' not in config

        # Check secret was saved
        renderer.secrets.set.assert_called_once_with(
            'TEST_PLUGIN_API_KEY',
            'secret123',
            scope='user'
        )

    def test_render_config_wizard_empty_schema(self, renderer):
        """Test wizard with no properties returns empty dict."""
        schema = {
            'title': 'Empty Config',
            'properties': {}
        }

        config = renderer.render_config_wizard(schema, 'empty_plugin')

        assert config == {}

    def test_render_config_wizard_with_existing_config(self, renderer):
        """Test wizard pre-fills existing values."""
        schema = {
            'properties': {
                'url': {
                    'type': 'string',
                    'prompt': {'message': 'URL:'}
                }
            }
        }

        existing = {'url': 'https://old.com'}

        renderer.prompts.ask_text.return_value = 'https://new.com'

        config = renderer.render_config_wizard(schema, 'plugin', existing)

        # Should use new value
        assert config['url'] == 'https://new.com'

        # Should have been called with existing value as default
        call_args = renderer.prompts.ask_text.call_args
        assert 'https://old.com' in str(call_args)

    def test_required_field_validation(self, renderer):
        """Test required field doesn't accept empty value."""
        schema = {
            'type': 'string',
            'required': True,
            'prompt': {'message': 'Required field:'}
        }

        # Empty string, then valid value
        renderer.prompts.ask_text.side_effect = ['', 'value']

        result = renderer._render_field('field', schema, None)

        assert result == 'value'
        assert renderer.prompts.ask_text.call_count == 2

    def test_array_field_comma_separated(self, renderer):
        """Test array field with free-form comma-separated values."""
        schema = {
            'type': 'array',
            'prompt': {'message': 'Enter tags:'}
        }

        renderer.prompts.ask_text.return_value = 'tag1, tag2, tag3'

        result = renderer._render_field('tags', schema, None)

        assert result == ['tag1', 'tag2', 'tag3']

    def test_get_validator_returns_none_for_no_validation(self, renderer):
        """Test _get_validator returns None when no validation needed."""
        schema = {'type': 'string'}

        validator = renderer._get_validator(schema)

        assert validator is None

    def test_help_text_displayed(self, renderer):
        """Test help text is displayed before prompting."""
        schema = {
            'type': 'string',
            'prompt': {
                'message': 'Enter value:',
                'help': 'This is a helpful hint'
            }
        }

        renderer.prompts.ask_text.return_value = 'value'

        result = renderer._render_field('field', schema, None)

        # Check help text was displayed
        renderer.text.body.assert_any_call(
            '  💡 This is a helpful hint',
            style='dim cyan'
        )
