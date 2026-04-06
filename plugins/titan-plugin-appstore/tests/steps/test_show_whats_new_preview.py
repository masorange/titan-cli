"""
Basic tests for show_whats_new_preview step.
"""

import pytest
from unittest.mock import MagicMock

from titan_plugin_appstore.steps.show_whats_new_preview import show_whats_new_preview
from titan_cli.engine import Success, Exit, Error


# ==================== Fixtures ====================


@pytest.fixture
def mock_context():
    """Mock workflow context."""
    ctx = MagicMock()
    ctx.textual = MagicMock()
    ctx.get = MagicMock()
    ctx.set = MagicMock()
    return ctx


@pytest.fixture
def sample_apps_data():
    """Sample app data from context."""
    return [
        {
            "id": "app1",
            "name": "Yoigo iOS",
            "bundle_id": "com.orange.yoigo",
            "sku": "yoigo-ios",
        },
        {
            "id": "app2",
            "name": "Jazztel App",
            "bundle_id": "com.orange.jazztel",
            "sku": "jazztel-ios",
        },
    ]


# ==================== Tests ====================


def test_happy_path_user_confirms(mock_context, sample_apps_data):
    """Test successful preview with user confirmation."""
    # Setup mock context
    mock_context.get.return_value = sample_apps_data
    mock_context.textual.ask_confirm.return_value = True

    # Execute step
    result = show_whats_new_preview(mock_context)

    # Verify result
    assert isinstance(result, Success)
    assert "confirmed" in result.message.lower()

    # Verify context was updated
    mock_context.set.assert_called_once_with("whats_new_confirmed", True)

    # Verify UI interactions
    mock_context.textual.begin_step.assert_called_once()
    mock_context.textual.end_step.assert_called_once_with("success")
    mock_context.textual.ask_confirm.assert_called_once()


def test_user_cancels(mock_context, sample_apps_data):
    """Test when user cancels confirmation."""
    # Setup mock context
    mock_context.get.return_value = sample_apps_data
    mock_context.textual.ask_confirm.return_value = False

    # Execute step
    result = show_whats_new_preview(mock_context)

    # Verify result
    assert isinstance(result, Exit)
    assert "cancelled" in result.message.lower()

    # Verify context was NOT updated
    mock_context.set.assert_not_called()

    # Verify UI showed cancellation
    mock_context.textual.end_step.assert_called_once_with("cancelled")


def test_no_apps_selected(mock_context):
    """Test when no apps in context."""
    # Setup mock context with no apps
    mock_context.get.return_value = None

    # Execute step
    result = show_whats_new_preview(mock_context)

    # Verify result
    assert isinstance(result, Error)
    assert "no apps" in result.message.lower()

    # Verify UI showed error
    mock_context.textual.end_step.assert_called_once_with("error")


def test_no_textual_context(mock_context):
    """Test when textual UI is not available."""
    # Setup mock context without textual
    mock_context.textual = None

    # Execute step
    result = show_whats_new_preview(mock_context)

    # Verify result
    assert isinstance(result, Error)
    assert "textual" in result.message.lower()
