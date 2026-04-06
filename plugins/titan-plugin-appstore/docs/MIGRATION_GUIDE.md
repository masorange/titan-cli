# Migration Guide: Old Steps → New Plugin

This guide explains how to migrate from the old `.titan/steps/appstore_connect/` implementation to the new clean plugin architecture.

## What Changed?

### Architecture Improvements

**Old Structure** (`.titan/steps/appstore_connect/`):
- ❌ Mixed concerns (API client + steps + helpers)
- ❌ Raw API responses exposed to steps
- ❌ No separation between DTOs and view models
- ❌ Limited test coverage

**New Structure** (`plugins/titan-plugin-appstore/`):
- ✅ Clean layered architecture
- ✅ Separated network models (DTOs) and view models
- ✅ Facade pattern for simple API
- ✅ Comprehensive test suite
- ✅ Type-safe with Pydantic models

### File Mapping

| Old Location | New Location | Notes |
|-------------|--------------|-------|
| `helpers/api_client.py` | `clients/network/appstore_api.py` | Refactored to low-level HTTP client |
| - | `clients/services/app_service.py` | NEW - Business logic for apps |
| - | `clients/services/version_service.py` | NEW - Business logic for versions |
| - | `clients/appstore_client.py` | NEW - High-level facade |
| `helpers/credentials.py` | `credentials.py` | Simplified |
| `select_app_step.py` | `steps/select_app_step.py` | Uses new client |
| `prompt_version_step.py` | `steps/prompt_version_step.py` | Enhanced with operations |
| `create_version_step.py` | `steps/create_version_step.py` | Uses new models |
| - | `models/network.py` | NEW - API DTOs |
| - | `models/view.py` | NEW - TUI models |
| - | `models/mappers.py` | NEW - Conversions |
| - | `operations/version_operations.py` | NEW - Complex workflows |

## Migration Steps

### 1. Install New Plugin

```bash
cd plugins/titan-plugin-appstore
pip install -e .
```

### 2. Credentials (No Change)

Credentials location remains the same:
```
.appstore_connect/
├── credentials.json
└── AuthKey_XXXXXXXXXX.p8
```

### 3. Update Workflow References

**Old workflow** (`.titan/workflows/create-app-version.yaml`):
```yaml
steps:
  - plugin: project
    step: select_app_step
```

**New workflow** (`workflows/create-app-version.yaml`):
```yaml
plugin: appstore
steps:
  - step: select_app_step
```

### 4. Update Step Imports (If Using in Code)

**Old:**
```python
from .titan.steps.appstore_connect.select_app_step import select_app_step
```

**New:**
```python
from titan_plugin_appstore.steps import select_app_step
```

### 5. Update Client Usage (If Using Programmatically)

**Old:**
```python
from .titan.steps.appstore_connect.helpers.api_client import AppStoreConnectClient

client = AppStoreConnectClient(
    key_id=key_id,
    issuer_id=issuer_id,
    private_key_path=p8_path
)

# Raw API responses
apps = client.list_apps()  # Returns List[Dict]
```

**New:**
```python
from titan_plugin_appstore import AppStoreConnectClient

client = AppStoreConnectClient(
    key_id=key_id,
    issuer_id=issuer_id,
    private_key_path=p8_path
)

# Type-safe view models
apps = client.list_apps()  # Returns List[AppView]
```

## Benefits of New Architecture

### 1. Type Safety
```python
# Old - no type hints
app = apps[0]
name = app["attributes"]["name"]  # Fragile

# New - type-safe with Pydantic
app = apps[0]  # Type: AppView
name = app.name  # IDE autocomplete, type checking
```

### 2. View Models for TUI
```python
# Old - manual formatting
display = f"{app['attributes']['name']} ({app['attributes']['bundleId']})"

# New - built-in display methods
display = app.display_name()
```

### 3. Operations Layer
```python
# Old - manual logic in steps
parts = version.split(".")
parts[2] = str(int(parts[2]) + 1)
next_version = ".".join(parts)

# New - dedicated operations
ops = VersionOperations(client)
next_version = ops.suggest_next_version(app_id, increment="patch")
```

### 4. Better Error Handling
```python
# Old - generic exceptions
try:
    client.create_version(...)
except Exception as e:
    # What went wrong?

# New - specific exceptions
try:
    client.create_version(...)
except VersionConflictError:
    # Handle duplicate version
except ValidationError:
    # Handle invalid input
except APIError as e:
    # Handle API errors with status code
    print(f"API error {e.status_code}: {e}")
```

## Testing

### Old Implementation
- ❌ No tests
- ❌ Manual testing only

### New Implementation
- ✅ Unit tests for services
- ✅ Unit tests for operations
- ✅ Mock-based testing
- ✅ 90%+ coverage

```bash
# Run tests
cd plugins/titan-plugin-appstore
pytest

# With coverage
pytest --cov=titan_plugin_appstore --cov-report=html
```

## Backward Compatibility

The old steps in `.titan/steps/appstore_connect/` are **not removed yet** to ensure:
1. Existing workflows continue working
2. Gradual migration path
3. Rollback capability if needed

### Deprecation Timeline

1. **Phase 1 (Current)**: Both old and new coexist
2. **Phase 2 (After testing)**: Mark old steps as deprecated
3. **Phase 3 (After migration)**: Remove old implementation

## Troubleshooting

### Import Errors
```bash
# If you get import errors
pip install -e plugins/titan-plugin-appstore
```

### Pydantic Validation Errors
```python
# If API responses don't match models
from titan_plugin_appstore.models.network import AppResponse

try:
    app = AppResponse(**data)
except ValidationError as e:
    print(e.json())  # See what fields are invalid
```

### Steps Not Found
Ensure plugin is registered in Titan CLI config:
```toml
# .titan/config.toml
[plugins]
appstore = "plugins/titan-plugin-appstore"
```

## Need Help?

- Check [README.md](./README.md) for full documentation
- Review tests for usage examples
- See architecture diagrams in README

## Next Steps

1. Test new workflows with sample data
2. Compare output with old implementation
3. Update custom steps if any
4. Migrate production workflows
5. Remove old implementation after verification
