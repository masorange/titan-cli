# Plugin Structure Documentation

Complete overview of the titan-plugin-appstore architecture.

## Directory Tree

```
titan-plugin-appstore/
├── pyproject.toml                 # Package manifest & dependencies
├── README.md                      # User documentation
├── MIGRATION_GUIDE.md            # Migration from old implementation
├── STRUCTURE.md                  # This file
│
├── titan_plugin_appstore/        # Main package
│   ├── __init__.py               # Package exports
│   ├── exceptions.py             # Custom exceptions
│   ├── credentials.py            # Credentials management
│   ├── plugin.py                 # Plugin manifest
│   │
│   ├── models/                   # Data models
│   │   ├── __init__.py
│   │   ├── network.py            # API DTOs (AppResponse, VersionResponse)
│   │   ├── view.py               # TUI models (AppView, VersionView)
│   │   └── mappers.py            # NetworkToViewMapper
│   │
│   ├── clients/                  # API clients
│   │   ├── __init__.py
│   │   ├── appstore_client.py    # HIGH-LEVEL FACADE (main entry point)
│   │   │
│   │   ├── network/              # Low-level HTTP layer
│   │   │   ├── __init__.py
│   │   │   └── appstore_api.py   # JWT + HTTP requests
│   │   │
│   │   └── services/             # Business logic layer
│   │       ├── __init__.py
│   │       ├── app_service.py    # App management
│   │       └── version_service.py # Version management
│   │
│   ├── operations/               # Complex workflows
│   │   ├── __init__.py
│   │   └── version_operations.py # Version operations (suggest, compare, etc.)
│   │
│   └── steps/                    # Workflow steps for TUI
│       ├── __init__.py
│       ├── select_app_step.py    # Interactive app selection
│       ├── prompt_version_step.py # Interactive version input
│       └── create_version_step.py # Create version in ASC
│
├── workflows/                    # YAML workflow definitions
│   └── create-app-version.yaml
│
└── tests/                        # Test suite
    ├── __init__.py
    ├── conftest.py               # Pytest fixtures
    ├── services/
    │   ├── test_app_service.py
    │   └── test_version_service.py
    └── operations/
        └── test_version_operations.py
```

## Layer Responsibilities

### 1. Models Layer (`models/`)

**Purpose**: Data representation

- **network.py**: DTOs faithful to Apple's API
  - `AppResponse`: App resource from API
  - `AppStoreVersionResponse`: Version resource from API
  - Matches JSON-API spec (type, id, attributes, relationships)

- **view.py**: Optimized for terminal UI
  - `AppView`: Simplified app for selection
  - `VersionView`: Full version with display methods
  - `VersionSummaryView`: Compact version for lists
  - `VersionCreationRequest`: Input validation

- **mappers.py**: Conversion between layers
  - `NetworkToViewMapper`: Converts API responses to view models

**Example:**
```python
# API response → Network model → View model
api_data = {"type": "apps", "id": "123", "attributes": {...}}
app_response = AppResponse(**api_data)
app_view = NetworkToViewMapper.app_to_view(app_response)
print(app_view.display_name())  # "MyApp (com.example.app)"
```

### 2. Clients Layer (`clients/`)

**Purpose**: API interaction

#### 2a. Network (`clients/network/`)

Low-level HTTP client:
- JWT token generation & caching
- HTTP request execution (GET, POST, PATCH, DELETE)
- Error handling
- **No business logic**

```python
api = AppStoreConnectAPI(key_id, issuer_id, p8_path)
response = api.get("/apps", query_params={"limit": 10})
```

#### 2b. Services (`clients/services/`)

Business logic for resources:

- **app_service.py**:
  - `list_apps()`: Fetch all apps
  - `get_app()`: Get specific app
  - `find_app_by_bundle_id()`: Search by bundle ID

- **version_service.py**:
  - `list_versions()`: Fetch versions for app
  - `create_version()`: Create new version
  - `delete_version()`: Delete version
  - `version_exists()`: Check for conflicts

```python
app_service = AppService(api)
apps = app_service.list_apps()  # Returns List[AppResponse]
```

#### 2c. Facade (`clients/appstore_client.py`)

**Main entry point** - combines all services:

- Simple, high-level API
- Returns view models (not network models)
- Convenience methods
- Error handling

```python
client = AppStoreConnectClient(key_id, issuer_id, p8_path)
apps = client.list_apps()  # Returns List[AppView] ✅
```

### 3. Operations Layer (`operations/`)

**Purpose**: Complex business workflows

- **version_operations.py**:
  - `suggest_next_version()`: Auto-increment logic
  - `compare_versions()`: Semantic versioning comparison
  - `validate_version_creation()`: Pre-creation checks
  - `create_version_interactive()`: Smart conflict resolution

```python
ops = VersionOperations(client)
next_ver = ops.suggest_next_version(app_id, increment="minor")
# "1.2.3" → "1.3.0"
```

### 4. Steps Layer (`steps/`)

**Purpose**: Interactive TUI workflows

Each step:
- Receives `WorkflowContext`
- Interacts with user via `ctx.textual`
- Calls client/operations
- Saves results to `ctx.data`
- Returns `Success` or `Error`

**Steps:**
1. `select_app_step`: List apps → user selects → save to context
2. `prompt_version_step`: Show existing → suggest next → validate input
3. `create_version_step`: Create version → display success

### 5. Workflows (`workflows/`)

**Purpose**: Declarative step orchestration

YAML files define:
- Step sequence
- Parameter passing
- Dependencies (`requires`)
- Default values

```yaml
steps:
  - id: select_app
    step: select_app_step

  - id: prompt_version
    step: prompt_version_step
    requires: [app_id]

  - id: create_version
    step: create_version_step
    requires: [app_id, version_string]
```

## Data Flow

### Example: Create Version Workflow

```
User runs workflow
    ↓
1. select_app_step
    → client.list_apps()
        → app_service.list_apps()
            → api.get("/apps")
        ← List[AppResponse]
        → NetworkToViewMapper.apps_to_view()
    ← List[AppView]
    → Display to user
    → Save selected app to ctx.data
    ↓
2. prompt_version_step
    → operations.get_versions_summary_table()
    → operations.suggest_next_version()
    → Display existing + suggestion
    → User inputs version
    → client.version_exists() for validation
    → Save version_string to ctx.data
    ↓
3. create_version_step
    → Build VersionCreationRequest
    → client.create_version(request)
        → version_service.create_version()
            → api.post("/appStoreVersions", payload)
        ← AppStoreVersionResponse
        → NetworkToViewMapper.version_to_view()
    ← VersionView
    → Display success
```

## Error Handling

### Exception Hierarchy

```
AppStoreConnectError (base)
├── AuthenticationError          # JWT/credentials issues
├── APIError                     # HTTP errors (with status_code)
│   ├── ResourceNotFoundError    # 404
│   └── VersionConflictError     # 409
├── ValidationError              # Input validation
└── ConfigurationError           # Plugin config issues
```

### Where Errors are Raised

- **network/**: `AuthenticationError`, `APIError`
- **services/**: `ResourceNotFoundError`, `VersionConflictError`
- **operations/**: `ValidationError`
- **steps/**: Catch and convert to `Error` results

## Testing Strategy

### Unit Tests

- **services/**: Mock `AppStoreConnectAPI`
- **operations/**: Mock `AppStoreConnectClient`
- Focus on business logic, not HTTP

### Fixtures (`conftest.py`)

- `mock_api_client`: Mocked HTTP client
- `sample_app_response`: Sample API data
- `sample_version_response`: Sample version data

### Test Coverage

```bash
pytest --cov=titan_plugin_appstore
# Target: >90% coverage
```

## Extension Points

### Adding a New Resource (e.g., Builds)

1. **Models**:
   - Add `BuildResponse` to `network.py`
   - Add `BuildView` to `view.py`
   - Add mapper to `mappers.py`

2. **Service**:
   - Create `clients/services/build_service.py`
   - Implement `list_builds()`, `get_build()`, etc.

3. **Facade**:
   - Add methods to `appstore_client.py`

4. **Operations** (if needed):
   - Create `operations/build_operations.py`

5. **Steps** (if needed):
   - Create `steps/select_build_step.py`

6. **Tests**:
   - Add `tests/services/test_build_service.py`

### Adding a New Step

1. Create `steps/my_new_step.py`
2. Follow signature: `def my_new_step(ctx: WorkflowContext) -> WorkflowResult`
3. Use `ctx.textual` for UI
4. Use `client` for API calls
5. Save results to `ctx.data`
6. Export from `steps/__init__.py`

### Adding a New Workflow

1. Create `workflows/my-workflow.yaml`
2. Define steps sequence
3. Set parameter defaults
4. Specify dependencies

## Best Practices

### Do's ✅

- Use view models in steps (not network models)
- Use operations for complex logic
- Add type hints everywhere
- Write tests for new features
- Use Pydantic for validation
- Cache expensive operations

### Don'ts ❌

- Don't put business logic in steps
- Don't expose raw API responses to TUI
- Don't skip error handling
- Don't hardcode credentials
- Don't ignore type errors
- Don't skip tests

## Performance

### Optimizations

- JWT token caching (20 min expiry)
- Minimal API calls (use filters)
- Lazy loading where possible

### Rate Limiting

Apple's API has rate limits:
- ~1000 requests/hour typical
- Monitor via response headers
- Implement backoff if needed

## Security

### Credentials Storage

- Never commit `.p8` files
- Store in `.appstore_connect/` (gitignored)
- Use JSON for config (not hardcoded)

### API Keys

- Individual Keys: No issuer_id
- Team Keys: Requires issuer_id
- Both use ES256 JWT

## Versioning

Plugin follows SemVer:
- **MAJOR**: Breaking API changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes

Current: `1.0.0`
