from titan_cli.core.migrations import (
    CURRENT_CONFIG_VERSION,
    LEGACY_VERSION,
    LegacyToV1Migration,
    MigrationManager,
)


def test_legacy_to_v1_migrates_ai_provider_config():
    """Legacy AI provider config should migrate to connection-based config."""
    raw_config = {
        "ai": {
            "default": "personal-claude",
            "providers": {
                "personal-claude": {
                    "name": "Personal Claude",
                    "type": "individual",
                    "provider": "anthropic",
                    "model": "claude-3-5-sonnet",
                    "temperature": 0.2,
                    "max_tokens": 2048,
                }
            },
        }
    }

    migrated = LegacyToV1Migration().migrate(raw_config)

    assert migrated["config_version"] == CURRENT_CONFIG_VERSION
    assert migrated["ai"]["default_connection"] == "personal-claude"
    assert "default" not in migrated["ai"]
    assert "providers" not in migrated["ai"]

    connection = migrated["ai"]["connections"]["personal-claude"]
    assert connection["name"] == "Personal Claude"
    assert connection["connection_type"] == "direct_provider"
    assert connection["provider"] == "anthropic"
    assert connection["default_model"] == "claude-3-5-sonnet"
    assert "model" not in connection
    assert "type" not in connection
    assert connection["temperature"] == 0.2
    assert connection["max_tokens"] == 2048


def test_legacy_to_v1_migrates_custom_provider_to_gateway():
    """Legacy custom provider config should migrate to gateway config."""
    raw_config = {
        "ai": {
            "default": "litellm",
            "providers": {
                "litellm": {
                    "name": "LiteLLM",
                    "type": "corporate",
                    "provider": "custom",
                    "model": "gpt-4o-mini",
                    "base_url": "http://litellm-proxy:4000",
                }
            },
        }
    }

    migrated = LegacyToV1Migration().migrate(raw_config)
    connection = migrated["ai"]["connections"]["litellm"]

    assert connection["connection_type"] == "gateway"
    assert connection["gateway_backend"] == "openai_compatible"
    assert connection["base_url"] == "http://litellm-proxy:4000"
    assert connection["default_model"] == "gpt-4o-mini"
    assert "provider" not in connection
    assert "type" not in connection


def test_legacy_to_v1_merges_corporate_connections_by_base_url():
    raw_config = {
        "version": "1.0",
        "ai": {
            "default": "corp-gemini",
            "providers": {
                "corp-claude": {
                    "name": "Corp Claude",
                    "type": "corporate",
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-5",
                    "base_url": "https://llm.company.com/",
                },
                "corp-gemini": {
                    "name": "Corp Gemini",
                    "type": "corporate",
                    "provider": "gemini",
                    "model": "gemini-2.5-pro",
                    "base_url": "https://llm.company.com/",
                },
            },
        },
    }

    migrated = LegacyToV1Migration().migrate(raw_config)

    assert "version" not in migrated
    assert migrated["config_version"] == CURRENT_CONFIG_VERSION
    assert migrated["ai"]["default_connection"] == "corp-gemini"
    assert list(migrated["ai"]["connections"].keys()) == ["corp-gemini"]

    connection = migrated["ai"]["connections"]["corp-gemini"]
    assert connection["connection_type"] == "gateway"
    assert connection["gateway_backend"] == "openai_compatible"
    assert connection["base_url"] == "https://llm.company.com/"
    assert connection["default_model"] == "gemini-2.5-pro"
    assert connection["name"] == "Corp Gemini"


def test_legacy_to_v1_keeps_individual_connections_separate():
    raw_config = {
        "ai": {
            "default": "personal-gemini",
            "providers": {
                "personal-gemini": {
                    "name": "Personal Gemini",
                    "type": "individual",
                    "provider": "gemini",
                    "model": "gemini-2.5-flash",
                }
            },
        }
    }

    migrated = LegacyToV1Migration().migrate(raw_config)
    connection = migrated["ai"]["connections"]["personal-gemini"]
    assert connection["connection_type"] == "direct_provider"
    assert connection["provider"] == "gemini"
    assert connection["default_model"] == "gemini-2.5-flash"


def test_legacy_to_v1_normalizes_connection_ids():
    raw_config = {
        "ai": {
            "default": "Individual Gemini (Google)",
            "providers": {
                "Individual Gemini (Google)": {
                    "name": "Individual Gemini (Google)",
                    "type": "individual",
                    "provider": "gemini",
                    "model": "gemini-3-flash-preview",
                }
            },
        }
    }

    migrated = LegacyToV1Migration().migrate(raw_config)

    assert migrated["ai"]["default_connection"] == "individual-gemini-google"
    assert "individual-gemini-google" in migrated["ai"]["connections"]
    assert "Individual Gemini (Google)" not in migrated["ai"]["connections"]
    assert (
        migrated["ai"]["connections"]["individual-gemini-google"]["name"]
        == "Individual Gemini (Google)"
    )


def test_legacy_to_v1_preserves_existing_connection_entries():
    """Migration should not overwrite already-migrated connection entries."""
    raw_config = {
        "ai": {
            "default": "legacy-provider",
            "default_connection": "new-connection",
            "providers": {
                "legacy-provider": {
                    "name": "Legacy Provider",
                    "type": "individual",
                    "provider": "anthropic",
                    "model": "claude-3-haiku",
                }
            },
            "connections": {
                "legacy-provider": {
                    "name": "Already Migrated",
                    "connection_type": "direct_provider",
                    "provider": "gemini",
                    "default_model": "gemini-2.5-flash",
                }
            },
        }
    }

    migrated = LegacyToV1Migration().migrate(raw_config)

    assert migrated["ai"]["default_connection"] == "new-connection"
    assert migrated["ai"]["connections"]["legacy-provider"]["provider"] == "gemini"
    assert (
        migrated["ai"]["connections"]["legacy-provider"]["default_model"]
        == "gemini-2.5-flash"
    )


def test_migration_manager_detects_legacy_when_version_missing():
    """Config without version should be treated as legacy."""
    manager = MigrationManager()

    assert manager.detect_version({}) == LEGACY_VERSION


def test_migration_manager_applies_legacy_to_v1():
    """Migration manager should apply the configured migration chain."""
    manager = MigrationManager()
    raw_config = {
        "ai": {
            "default": "corp-gemini",
            "providers": {
                "corp-gemini": {
                    "name": "Corporate Gemini",
                    "type": "corporate",
                    "provider": "gemini",
                    "model": "gemini-2.0-flash",
                }
            },
        }
    }

    result = manager.migrate(raw_config)

    assert result.original_version == LEGACY_VERSION
    assert result.final_version == CURRENT_CONFIG_VERSION
    assert result.applied_steps == [f"{LEGACY_VERSION}->{CURRENT_CONFIG_VERSION}"]
    assert result.changed is True
    assert result.data["config_version"] == CURRENT_CONFIG_VERSION
    assert result.data["ai"]["default_connection"] == "corp-gemini"
    assert "corp-gemini" in result.data["ai"]["connections"]
