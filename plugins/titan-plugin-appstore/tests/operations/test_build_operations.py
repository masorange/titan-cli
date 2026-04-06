"""
Tests for build operations.

These tests verify business logic functions that don't make API calls.
"""

import pytest
from datetime import datetime

from titan_plugin_appstore.operations.build_operations import (
    prepare_whats_new_previews,
    get_whats_new_texts,
    format_build_for_selection,
    filter_valid_builds,
    group_builds_by_brand,
    create_submission_summary,
    validate_submission_readiness,
    WHATS_NEW_TEXT_ES,
    WHATS_NEW_TEXT_EN,
)
from titan_plugin_appstore.models.view import AppView, BuildView


# ==================== Fixtures ====================


@pytest.fixture
def sample_apps():
    """Sample app models for testing."""
    return [
        AppView(
            id="app1",
            name="Yoigo iOS",
            bundle_id="com.orange.yoigo",
            sku="yoigo-ios",
            primary_locale="es-ES",
        ),
        AppView(
            id="app2",
            name="Jazztel App",
            bundle_id="com.orange.jazztel",
            sku="jazztel-ios",
            primary_locale="es-ES",
        ),
    ]


@pytest.fixture
def sample_builds():
    """Sample build models for testing."""
    return [
        BuildView(
            id="build1",
            version="1.2.3",
            uploaded_date="2024-01-15T10:00:00Z",
            processing_state="VALID",
            expired=False,
        ),
        BuildView(
            id="build2",
            version="1.2.4",
            uploaded_date="2024-01-16T10:00:00Z",
            processing_state="VALID",
            expired=False,
        ),
        BuildView(
            id="build3",
            version="1.2.5",
            uploaded_date="2024-01-17T10:00:00Z",
            processing_state="PROCESSING",
            expired=False,
        ),
        BuildView(
            id="build4",
            version="1.2.6",
            uploaded_date="2024-01-18T10:00:00Z",
            processing_state="VALID",
            expired=True,
        ),
    ]


# ==================== prepare_whats_new_previews ====================


def test_prepare_whats_new_previews(sample_apps):
    """Test preparing What's New previews for apps."""
    previews = prepare_whats_new_previews(sample_apps)

    assert len(previews) == 2

    # Check first preview
    assert previews[0].brand_name == "Yoigo"
    assert previews[0].app_id == "app1"
    assert previews[0].text_es == WHATS_NEW_TEXT_ES
    assert previews[0].text_en == WHATS_NEW_TEXT_EN

    # Check second preview
    assert previews[1].brand_name == "Jazztel"
    assert previews[1].app_id == "app2"


def test_prepare_whats_new_previews_empty():
    """Test with empty app list."""
    previews = prepare_whats_new_previews([])
    assert previews == []


# ==================== get_whats_new_texts ====================


def test_get_whats_new_texts():
    """Test getting What's New texts for both locales."""
    texts = get_whats_new_texts()

    assert "es-ES" in texts
    assert "en-US" in texts
    assert texts["es-ES"] == WHATS_NEW_TEXT_ES
    assert texts["en-US"] == WHATS_NEW_TEXT_EN


# ==================== format_build_for_selection ====================


def test_format_build_for_selection(sample_builds):
    """Test formatting build for selection widget."""
    build = sample_builds[0]
    value, title, description = format_build_for_selection(build)

    assert value == "build1"
    assert title == "Build 1.2.3"
    assert "Uploaded: 2024-01-15" in description
    assert "Status: VALID" in description
    assert "✅" in description


def test_format_build_for_selection_expired(sample_builds):
    """Test formatting expired build."""
    build = sample_builds[3]  # Expired build
    value, title, description = format_build_for_selection(build)

    assert value == "build4"
    assert "Status: EXPIRED" in description
    assert "⏰" in description


def test_format_build_for_selection_processing(sample_builds):
    """Test formatting processing build."""
    build = sample_builds[2]  # Processing build
    value, title, description = format_build_for_selection(build)

    assert "Status: PROCESSING" in description
    assert "🔄" in description


# ==================== filter_valid_builds ====================


def test_filter_valid_builds(sample_builds):
    """Test filtering to only valid builds."""
    valid_builds = filter_valid_builds(sample_builds)

    assert len(valid_builds) == 2
    assert all(not build.expired for build in valid_builds)
    assert all(build.processing_state in ("VALID", None) for build in valid_builds)


def test_filter_valid_builds_empty():
    """Test filtering empty list."""
    valid_builds = filter_valid_builds([])
    assert valid_builds == []


def test_filter_valid_builds_none_processing_state():
    """Test builds with None processing state are considered valid."""
    builds = [
        BuildView(
            id="build1",
            version="1.0.0",
            uploaded_date="2024-01-15T10:00:00Z",
            processing_state=None,
            expired=False,
        )
    ]

    valid_builds = filter_valid_builds(builds)
    assert len(valid_builds) == 1


# ==================== group_builds_by_brand ====================


def test_group_builds_by_brand(sample_apps, sample_builds):
    """Test grouping builds by brand."""
    all_builds = {
        "app1": sample_builds[:2],  # Yoigo
        "app2": sample_builds[2:],  # Jazztel
    }

    grouped = group_builds_by_brand(sample_apps, all_builds)

    assert "Yoigo" in grouped
    assert "Jazztel" in grouped

    # Check Yoigo group
    yoigo_entries = grouped["Yoigo"]
    assert len(yoigo_entries) == 1
    app, builds = yoigo_entries[0]
    assert app.name == "Yoigo iOS"
    assert len(builds) == 2

    # Check Jazztel group
    jazztel_entries = grouped["Jazztel"]
    assert len(jazztel_entries) == 1
    app, builds = jazztel_entries[0]
    assert app.name == "Jazztel App"
    assert len(builds) == 2


def test_group_builds_by_brand_no_builds(sample_apps):
    """Test grouping when no builds available."""
    all_builds = {}

    grouped = group_builds_by_brand(sample_apps, all_builds)

    assert len(grouped) == 2
    assert all(len(entries[0][1]) == 0 for entries in grouped.values())


# ==================== create_submission_summary ====================


def test_create_submission_summary(sample_apps):
    """Test creating submission summary."""
    selected_builds = {
        "app1": "build1",
        "app2": "build2",
    }

    summary = create_submission_summary(selected_builds, sample_apps)

    assert len(summary) == 2

    # Check first entry
    brand, app_name, build_id = summary[0]
    assert brand == "Yoigo"
    assert app_name == "Yoigo iOS"
    assert build_id == "build1"

    # Check second entry
    brand, app_name, build_id = summary[1]
    assert brand == "Jazztel"
    assert app_name == "Jazztel App"
    assert build_id == "build2"


def test_create_submission_summary_partial_selection(sample_apps):
    """Test summary when only some apps have builds selected."""
    selected_builds = {
        "app1": "build1",
        # app2 not selected
    }

    summary = create_submission_summary(selected_builds, sample_apps)

    assert len(summary) == 1
    assert summary[0][0] == "Yoigo"


def test_create_submission_summary_empty():
    """Test with no builds selected."""
    summary = create_submission_summary({}, [])
    assert summary == []


# ==================== validate_submission_readiness ====================


def test_validate_submission_readiness_all_ok():
    """Test validation when everything is ready."""
    is_ready, errors = validate_submission_readiness(
        app_id="app1",
        build_id="build1",
        whats_new_locales=["es-ES", "en-US"],
    )

    assert is_ready is True
    assert errors == []


def test_validate_submission_readiness_missing_build():
    """Test validation when build is missing."""
    is_ready, errors = validate_submission_readiness(
        app_id="app1",
        build_id="",
        whats_new_locales=["es-ES", "en-US"],
    )

    assert is_ready is False
    assert "No build assigned" in errors


def test_validate_submission_readiness_missing_locale():
    """Test validation when a locale is missing."""
    is_ready, errors = validate_submission_readiness(
        app_id="app1",
        build_id="build1",
        whats_new_locales=["es-ES"],  # Missing en-US
    )

    assert is_ready is False
    assert any("Missing What's New" in error for error in errors)
    assert any("en-US" in error for error in errors)


def test_validate_submission_readiness_multiple_errors():
    """Test validation with multiple errors."""
    is_ready, errors = validate_submission_readiness(
        app_id="app1",
        build_id="",
        whats_new_locales=[],
    )

    assert is_ready is False
    assert len(errors) == 2
    assert "No build assigned" in errors
    assert any("Missing What's New" in error for error in errors)
