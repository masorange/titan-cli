#!/usr/bin/env python3
"""
Plugin Verification Script

Runs comprehensive checks to verify the plugin is working correctly.
"""

import sys
from pathlib import Path


def print_header(text: str):
    """Print formatted header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print('='*60)


def print_success(text: str):
    """Print success message."""
    print(f"✅ {text}")


def print_error(text: str):
    """Print error message."""
    print(f"❌ {text}")


def verify_imports():
    """Verify all main classes can be imported."""
    print_header("1. Verifying Imports")

    try:
        from titan_plugin_appstore import AppStoreConnectClient, CredentialsManager
        print_success("Main exports importable")
    except ImportError as e:
        print_error(f"Failed to import main exports: {e}")
        return False

    try:
        from titan_plugin_appstore.models.view import AppView, VersionView
        from titan_plugin_appstore.models.network import AppResponse, AppStoreVersionResponse
        from titan_plugin_appstore.models.mappers import NetworkToViewMapper
        print_success("Models importable")
    except ImportError as e:
        print_error(f"Failed to import models: {e}")
        return False

    try:
        from titan_plugin_appstore.operations import VersionOperations
        print_success("Operations importable")
    except ImportError as e:
        print_error(f"Failed to import operations: {e}")
        return False

    try:
        from titan_plugin_appstore.clients.services import AppService, VersionService
        print_success("Services importable")
    except ImportError as e:
        print_error(f"Failed to import services: {e}")
        return False

    return True


def verify_models():
    """Verify models work correctly."""
    print_header("2. Verifying Models")

    try:
        from titan_plugin_appstore.models.network import AppResponse, AppStoreVersionResponse
        from titan_plugin_appstore.models.mappers import NetworkToViewMapper

        # Test app model
        app_data = {
            "type": "apps",
            "id": "123456",
            "attributes": {
                "name": "Test App",
                "bundleId": "com.test.app",
                "sku": "TEST-SKU",
                "primaryLocale": "en-US",
            }
        }
        app_response = AppResponse(**app_data)
        app_view = NetworkToViewMapper.app_to_view(app_response)

        assert app_view.name == "Test App"
        assert app_view.display_name() == "Test App (com.test.app)"
        print_success(f"App models work: {app_view.display_name()}")

        # Test version model
        version_data = {
            "type": "appStoreVersions",
            "id": "987654",
            "attributes": {
                "versionString": "1.2.3",
                "platform": "IOS",
                "appStoreState": "READY_FOR_SALE",
                "releaseType": "MANUAL",
            }
        }
        version_response = AppStoreVersionResponse(**version_data)
        version_view = NetworkToViewMapper.version_to_view(version_response)

        assert version_view.version_string == "1.2.3"
        assert "Ready for Sale" in version_view.format_state()
        print_success(f"Version models work: {version_view.version_string} - {version_view.format_state()}")

        return True
    except Exception as e:
        print_error(f"Model verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_operations():
    """Verify operations work correctly."""
    print_header("3. Verifying Operations")

    try:
        from unittest.mock import Mock
        from titan_plugin_appstore.operations import VersionOperations
        from titan_plugin_appstore.models.view import VersionView

        # Mock client
        mock_client = Mock()

        # Test version suggestion
        latest = VersionView(
            id="123",
            version_string="1.2.3",
            platform="IOS",
            state="READY_FOR_SALE",
        )
        mock_client.get_latest_version.return_value = latest

        ops = VersionOperations(mock_client)

        next_patch = ops.suggest_next_version("app123", increment="patch")
        assert next_patch == "1.2.4", f"Expected 1.2.4, got {next_patch}"
        print_success(f"Patch increment: 1.2.3 → {next_patch}")

        next_minor = ops.suggest_next_version("app123", increment="minor")
        assert next_minor == "1.3.0", f"Expected 1.3.0, got {next_minor}"
        print_success(f"Minor increment: 1.2.3 → {next_minor}")

        next_major = ops.suggest_next_version("app123", increment="major")
        assert next_major == "2.0.0", f"Expected 2.0.0, got {next_major}"
        print_success(f"Major increment: 1.2.3 → {next_major}")

        # Test version comparison
        assert ops.compare_versions("1.2.3", "1.2.4") == -1
        assert ops.compare_versions("1.2.3", "1.2.3") == 0
        assert ops.compare_versions("1.2.4", "1.2.3") == 1
        print_success("Version comparison works")

        # Test validation
        mock_client.version_exists.return_value = False
        is_valid, error = ops.validate_version_creation("app123", "1.2.3")
        assert is_valid, f"Should be valid: {error}"
        print_success(f"Validation works: 1.2.3 is valid")

        return True
    except Exception as e:
        print_error(f"Operations verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_structure():
    """Verify directory structure."""
    print_header("4. Verifying Directory Structure")

    base_path = Path(__file__).parent / "titan_plugin_appstore"

    required_files = [
        "models/network.py",
        "models/view.py",
        "models/mappers.py",
        "clients/network/appstore_api.py",
        "clients/services/app_service.py",
        "clients/services/version_service.py",
        "clients/appstore_client.py",
        "operations/version_operations.py",
        "steps/select_app_step.py",
        "steps/prompt_version_step.py",
        "steps/create_version_step.py",
    ]

    missing = []
    for file in required_files:
        if not (base_path / file).exists():
            missing.append(file)

    if missing:
        print_error(f"Missing files: {', '.join(missing)}")
        return False

    print_success(f"All {len(required_files)} required files present")
    return True


def verify_package_metadata():
    """Verify package metadata."""
    print_header("5. Verifying Package Metadata")

    try:
        import titan_plugin_appstore

        assert hasattr(titan_plugin_appstore, '__version__')
        print_success(f"Version: {titan_plugin_appstore.__version__}")

        assert hasattr(titan_plugin_appstore, '__plugin_name__')
        print_success(f"Plugin name: {titan_plugin_appstore.__plugin_name__}")

        return True
    except Exception as e:
        print_error(f"Metadata verification failed: {e}")
        return False


def main():
    """Run all verification checks."""
    print("\n" + "="*60)
    print("  TITAN PLUGIN APP STORE CONNECT - VERIFICATION")
    print("="*60)

    results = []

    results.append(("Imports", verify_imports()))
    results.append(("Models", verify_models()))
    results.append(("Operations", verify_operations()))
    results.append(("Structure", verify_structure()))
    results.append(("Metadata", verify_package_metadata()))

    # Summary
    print_header("VERIFICATION SUMMARY")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")

    print("\n" + "="*60)
    print(f"  Result: {passed}/{total} checks passed")
    print("="*60 + "\n")

    if passed == total:
        print("🎉 All verifications passed! Plugin is ready to use.")
        return 0
    else:
        print("⚠️  Some verifications failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
