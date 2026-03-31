---
name: titan-testing
description: Write comprehensive tests for Titan CLI plugins - unit tests, fixtures, mocks, and coverage strategies. Use when creating tests or improving test coverage.
keywords: testing, unit tests, fixtures, mocks, coverage, pytest, test strategy
---

# Titan Testing Skill

Complete guide for writing comprehensive tests for Titan CLI plugins following the 5-layer architecture.

## When to Use This Skill

Invoke this skill when the user requests:
- **Test creation**: "Write tests for X", "Create test suite for Y"
- **Coverage improvement**: "Improve test coverage", "Add missing tests"
- **Test refactoring**: "Update tests for new architecture", "Migrate tests to pytest"
- **Test fixtures**: "Create test fixtures for Z", "Add mock data"
- **Test debugging**: "Fix failing tests", "Why is this test failing?"

## Testing Philosophy

### Core Principles

1. **Test What Matters**: Focus on behavior, not implementation
2. **100% Coverage Target**: Services and Operations must have complete coverage
3. **Fast Feedback**: Tests should run in milliseconds, not seconds
4. **Isolated Tests**: No external dependencies (APIs, databases, files)
5. **Readable Tests**: Tests are documentation - make them clear

### Testing Pyramid for Titan CLI

```
           /\
          /  \  E2E (Workflow Integration)
         /    \  - Rare, expensive
        /------\
       /        \  Integration (Service Tests)
      /          \  - With mocked Network layer
     /            \  - Test data transformations
    /--------------\
   /                \  Unit (Operations & Mappers)
  /                  \  - Pure functions
 /____________________\  - Fast, comprehensive
```

**Distribution Target**:
- **70%** Unit tests (Operations, Mappers, Validators)
- **25%** Integration tests (Services)
- **5%** E2E tests (Steps, Workflows)

## What to Test (By Layer)

### Network Layer (Low Priority)

**Usually NOT tested** - thin wrapper around HTTP/CLI.

**When to test**:
- Complex request building
- Custom retry logic
- Error parsing

**Example**:
```python
# Usually skip testing this layer
class NotionAPI:
    def make_request(self, method: str, endpoint: str, **kwargs):
        response = self.session.request(method, url, **kwargs)
        return response.json()
```

### Services Layer (HIGH Priority - 100% Coverage)

**MUST test** - contains all data transformation logic.

**What to test**:
- ✅ Network call → Network model parsing
- ✅ Network model → UI model mapping
- ✅ Error handling (API errors, validation errors)
- ✅ Edge cases (empty responses, missing fields)

**Example test file**:
```python
# tests/services/test_resource_service.py
import pytest
from unittest.mock import Mock
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_example.clients.services import ResourceService
from titan_plugin_example.clients.network import ExampleAPIError


@pytest.fixture
def mock_network():
    """Create mock network layer."""
    return Mock()


@pytest.fixture
def resource_service(mock_network):
    """Create ResourceService with mocked network."""
    return ResourceService(mock_network)


class TestGetResource:
    """Tests for get_resource method."""

    def test_success_returns_ui_model(self, resource_service, mock_network):
        """Should return ClientSuccess with UIResource."""
        # Arrange: Mock network response
        mock_network.make_request.return_value = {
            "id": "123",
            "name": "Test Resource",
            "status": "active",
            "created_at": "2024-01-01T00:00:00Z"
        }

        # Act: Call service
        result = resource_service.get_resource("123")

        # Assert: Verify result type and data
        assert isinstance(result, ClientSuccess)
        assert result.data.id == "123"
        assert result.data.name == "Test Resource"
        assert result.data.status_icon == "✅"  # UI model has formatted fields
        assert result.data.status_display == "Active"

    def test_not_found_returns_error(self, resource_service, mock_network):
        """Should return ClientError with NOT_FOUND code."""
        # Arrange: Mock 404 error
        mock_network.make_request.side_effect = ExampleAPIError(
            "Resource not found",
            status_code=404
        )

        # Act
        result = resource_service.get_resource("999")

        # Assert
        assert isinstance(result, ClientError)
        assert result.error_code == "NOT_FOUND"
        assert "not found" in result.error_message.lower()

    def test_api_error_returns_error(self, resource_service, mock_network):
        """Should return ClientError with API_ERROR code."""
        # Arrange: Mock 500 error
        mock_network.make_request.side_effect = ExampleAPIError(
            "Internal server error",
            status_code=500
        )

        # Act
        result = resource_service.get_resource("123")

        # Assert
        assert isinstance(result, ClientError)
        assert result.error_code == "API_ERROR"

    def test_malformed_response_returns_error(self, resource_service, mock_network):
        """Should handle malformed API responses gracefully."""
        # Arrange: Missing required field
        mock_network.make_request.return_value = {
            "id": "123"
            # Missing "name", "status", "created_at"
        }

        # Act
        result = resource_service.get_resource("123")

        # Assert: Should catch parsing error
        assert isinstance(result, ClientError)


class TestListResources:
    """Tests for list_resources method."""

    def test_empty_list_returns_success(self, resource_service, mock_network):
        """Should handle empty responses."""
        mock_network.make_request.return_value = []

        result = resource_service.list_resources()

        assert isinstance(result, ClientSuccess)
        assert len(result.data) == 0

    def test_multiple_resources_all_mapped(self, resource_service, mock_network):
        """Should map all resources to UI models."""
        mock_network.make_request.return_value = [
            {"id": "1", "name": "Resource 1", "status": "active", "created_at": "2024-01-01T00:00:00Z"},
            {"id": "2", "name": "Resource 2", "status": "paused", "created_at": "2024-01-02T00:00:00Z"},
        ]

        result = resource_service.list_resources()

        assert isinstance(result, ClientSuccess)
        assert len(result.data) == 2
        assert all(hasattr(r, "status_icon") for r in result.data)  # UI models
```

### Operations Layer (HIGH Priority - 100% Coverage)

**MUST test** - contains all business logic.

**What to test**:
- ✅ Filtering, sorting, searching logic
- ✅ Validation rules
- ✅ Complex calculations
- ✅ Error handling (raises OperationError)
- ✅ Edge cases (empty inputs, invalid data)

**Example test file**:
```python
# tests/operations/test_resource_operations.py
import pytest
from unittest.mock import Mock
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_example.operations import (
    fetch_active_resources,
    validate_resource_name,
    OperationError
)
from titan_plugin_example.models import UIResource


@pytest.fixture
def mock_client():
    """Create mock client."""
    return Mock()


@pytest.fixture
def sample_resources():
    """Sample UI resources for testing."""
    return [
        UIResource(
            id="1", name="Active 1",
            status_icon="✅", status_display="Active",
            created_display="2h ago"
        ),
        UIResource(
            id="2", name="Paused 1",
            status_icon="⏸️", status_display="Paused",
            created_display="1h ago"
        ),
        UIResource(
            id="3", name="Active 2",
            status_icon="✅", status_display="Active",
            created_display="3h ago"
        ),
    ]


class TestFetchActiveResources:
    """Tests for fetch_active_resources operation."""

    def test_filters_active_only(self, mock_client, sample_resources):
        """Should filter and return only active resources."""
        # Arrange
        mock_client.list_resources.return_value = ClientSuccess(
            data=sample_resources
        )

        # Act
        result = fetch_active_resources(mock_client)

        # Assert: Only active ones
        assert len(result) == 2
        assert all(r.status_display == "Active" for r in result)

    def test_sorts_by_name(self, mock_client, sample_resources):
        """Should sort resources alphabetically."""
        mock_client.list_resources.return_value = ClientSuccess(
            data=sample_resources
        )

        result = fetch_active_resources(mock_client)

        # Should be sorted: "Active 1", "Active 2"
        assert result[0].name == "Active 1"
        assert result[1].name == "Active 2"

    def test_empty_list_returns_empty(self, mock_client):
        """Should handle empty resource list."""
        mock_client.list_resources.return_value = ClientSuccess(data=[])

        result = fetch_active_resources(mock_client)

        assert len(result) == 0

    def test_all_inactive_returns_empty(self, mock_client):
        """Should return empty list when no active resources."""
        mock_client.list_resources.return_value = ClientSuccess(data=[
            UIResource(
                id="1", name="Paused",
                status_icon="⏸️", status_display="Paused",
                created_display="1h ago"
            ),
        ])

        result = fetch_active_resources(mock_client)

        assert len(result) == 0

    def test_raises_on_client_error(self, mock_client):
        """Should raise OperationError when client fails."""
        mock_client.list_resources.return_value = ClientError(
            error_message="API error",
            error_code="API_ERROR"
        )

        with pytest.raises(OperationError, match="Failed to fetch resources"):
            fetch_active_resources(mock_client)


class TestValidateResourceName:
    """Tests for validate_resource_name operation."""

    def test_valid_name_returns_true(self):
        """Should accept valid resource names."""
        assert validate_resource_name("MyResource") is True
        assert validate_resource_name("Resource_123") is True
        assert validate_resource_name("Test-Resource") is True

    def test_empty_name_raises(self):
        """Should reject empty names."""
        with pytest.raises(OperationError, match="cannot be empty"):
            validate_resource_name("")

    def test_too_short_raises(self):
        """Should reject names shorter than 3 characters."""
        with pytest.raises(OperationError, match="at least 3 characters"):
            validate_resource_name("ab")

    def test_too_long_raises(self):
        """Should reject names longer than 50 characters."""
        long_name = "a" * 51
        with pytest.raises(OperationError, match="cannot exceed 50 characters"):
            validate_resource_name(long_name)

    def test_invalid_characters_raise(self):
        """Should reject names with special characters."""
        with pytest.raises(OperationError, match="alphanumeric"):
            validate_resource_name("Resource@123")

        with pytest.raises(OperationError):
            validate_resource_name("Resource#Name")

    @pytest.mark.parametrize("name", [
        "Resource",
        "My-Resource",
        "Resource_123",
        "Test-Resource-Name",
        "ABC",
        "a" * 50,  # Max length
    ])
    def test_valid_names_parametrized(self, name):
        """Parametrized test for valid names."""
        assert validate_resource_name(name) is True
```

### Client Layer (LOW Priority)

**Usually NO tests needed** - just delegates to Services.

**Only test if**:
- Client has complex initialization logic
- Client aggregates multiple service calls

**Example** (when needed):
```python
# tests/test_client.py
def test_client_initializes_services():
    """Should initialize all internal services."""
    client = ExampleClient(base_url="https://api.example.com", api_token="token")

    # Verify internal services are created
    assert client._network is not None
    assert client._resource_service is not None
```

### Mappers (MEDIUM Priority)

**Test when mappers are complex** (conditional logic, calculations).

**Example**:
```python
# tests/mappers/test_resource_mapper.py
from titan_plugin_example.models import NetworkResource, UIResource
from titan_plugin_example.models.mappers import from_network_resource


class TestResourceMapper:
    """Tests for from_network_resource mapper."""

    def test_maps_all_fields(self):
        """Should map all Network fields to UI fields."""
        network = NetworkResource(
            id="123",
            name="Test",
            status="active",
            created_at="2024-01-01T00:00:00Z"
        )

        ui = from_network_resource(network)

        assert ui.id == "123"
        assert ui.name == "Test"
        assert ui.status_icon == "✅"
        assert ui.status_display == "Active"
        assert "ago" in ui.created_display  # Relative timestamp

    def test_archived_status_icon(self):
        """Should use correct icon for archived status."""
        network = NetworkResource(
            id="123",
            name="Test",
            status="archived",
            created_at="2024-01-01T00:00:00Z"
        )

        ui = from_network_resource(network)

        assert ui.status_icon == "🗑️"

    def test_handles_missing_optional_fields(self):
        """Should handle missing optional fields gracefully."""
        network = NetworkResource(
            id="123",
            name="Test",
            status="active",
            created_at="2024-01-01T00:00:00Z",
            description=None  # Optional field
        )

        ui = from_network_resource(network)

        assert ui.description == "No description"  # Default value
```

### Steps (LOW Priority)

**Usually NO tests needed** - only orchestrates UI and calls operations.

**When to test**:
- Step has complex conditional logic
- Step transforms data before display

**Example** (rare):
```python
# tests/steps/test_list_resources_step.py
from unittest.mock import Mock, patch
from titan_cli.engine import WorkflowContext, Success, Error
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_example.steps import list_resources_step


def test_list_resources_displays_all():
    """Should display all resources from client."""
    # Create mock context
    ctx = Mock(spec=WorkflowContext)
    ctx.example = Mock()

    # Mock client response
    ctx.example.list_resources.return_value = ClientSuccess(
        data=[
            Mock(name="Resource 1", status_icon="✅"),
            Mock(name="Resource 2", status_icon="⏸️"),
        ],
        message="Found 2 resources"
    )

    # Execute step
    result = list_resources_step(ctx)

    # Verify result
    assert isinstance(result, Success)
    assert ctx.textual.text.call_count == 2  # Called for each resource


def test_list_resources_handles_error():
    """Should handle client errors gracefully."""
    ctx = Mock(spec=WorkflowContext)
    ctx.example = Mock()

    # Mock error response
    ctx.example.list_resources.return_value = ClientError(
        error_message="API error",
        error_code="API_ERROR"
    )

    result = list_resources_step(ctx)

    assert isinstance(result, Error)
    ctx.textual.error_text.assert_called_once()
```

## Test Fixtures and Mocks

### Shared Fixtures (conftest.py)

**tests/conftest.py**:
```python
"""Shared pytest fixtures for all tests."""

import pytest
from unittest.mock import Mock
from titan_plugin_example.models import UIResource, NetworkResource


@pytest.fixture
def mock_network():
    """Create mock network API client."""
    return Mock()


@pytest.fixture
def sample_network_resource():
    """Sample NetworkResource for testing."""
    return NetworkResource(
        id="test-123",
        name="Test Resource",
        status="active",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-02T00:00:00Z",
        metadata={"key": "value"}
    )


@pytest.fixture
def sample_ui_resource():
    """Sample UIResource for testing."""
    return UIResource(
        id="test-123",
        name="Test Resource",
        status_icon="✅",
        status_display="Active",
        created_display="2 days ago",
        updated_display="1 day ago"
    )


@pytest.fixture
def sample_network_resources():
    """List of sample NetworkResource objects."""
    return [
        NetworkResource(
            id=f"res-{i}",
            name=f"Resource {i}",
            status="active" if i % 2 == 0 else "paused",
            created_at="2024-01-01T00:00:00Z"
        )
        for i in range(1, 6)
    ]


@pytest.fixture
def mock_client():
    """Create mock client with common methods."""
    client = Mock()
    client.get_resource = Mock()
    client.list_resources = Mock()
    client.create_resource = Mock()
    return client


@pytest.fixture
def mock_context():
    """Create mock WorkflowContext."""
    ctx = Mock()
    ctx.get = Mock(return_value=None)
    ctx.textual = Mock()
    return ctx
```

### Parametrized Tests

Use `@pytest.mark.parametrize` for testing multiple inputs:

```python
@pytest.mark.parametrize("status,expected_icon", [
    ("active", "✅"),
    ("paused", "⏸️"),
    ("failed", "❌"),
    ("archived", "🗑️"),
    ("pending", "🕐"),
])
def test_status_icon_mapping(status, expected_icon):
    """Should map status to correct icon."""
    network = NetworkResource(
        id="1", name="Test",
        status=status,
        created_at="2024-01-01T00:00:00Z"
    )

    ui = from_network_resource(network)

    assert ui.status_icon == expected_icon


@pytest.mark.parametrize("name,should_raise", [
    ("Valid", False),
    ("", True),  # Empty
    ("ab", True),  # Too short
    ("a" * 51, True),  # Too long
    ("Invalid@Name", True),  # Special chars
    ("Valid-Name_123", False),
])
def test_name_validation(name, should_raise):
    """Parametrized validation tests."""
    if should_raise:
        with pytest.raises(OperationError):
            validate_resource_name(name)
    else:
        assert validate_resource_name(name) is True
```

## Testing ClientResult Pattern

### Testing Success Case

```python
def test_service_returns_success():
    """Should return ClientSuccess with data."""
    mock_network = Mock()
    mock_network.make_request.return_value = {"id": "1", "name": "Test"}

    service = ResourceService(mock_network)
    result = service.get_resource("1")

    # Verify type
    assert isinstance(result, ClientSuccess)

    # Verify data
    assert result.data.id == "1"
    assert result.data.name == "Test"

    # Verify message
    assert "retrieved" in result.message.lower()
```

### Testing Error Cases

```python
def test_service_returns_error_on_api_failure():
    """Should return ClientError when API fails."""
    mock_network = Mock()
    mock_network.make_request.side_effect = ExampleAPIError(
        "API error",
        status_code=500
    )

    service = ResourceService(mock_network)
    result = service.get_resource("1")

    # Verify type
    assert isinstance(result, ClientError)

    # Verify error details
    assert result.error_code == "API_ERROR"
    assert "API error" in result.error_message
```

### Testing Operations with ClientResult

```python
def test_operation_handles_success():
    """Should return data when client succeeds."""
    mock_client = Mock()
    mock_client.get_resource.return_value = ClientSuccess(
        data=UIResource(id="1", name="Test", ...)
    )

    # Operation extracts data directly
    result = get_resource_operation(mock_client, "1")

    assert result.id == "1"
    assert result.name == "Test"


def test_operation_raises_on_error():
    """Should raise OperationError when client fails."""
    mock_client = Mock()
    mock_client.get_resource.return_value = ClientError(
        error_message="Not found",
        error_code="NOT_FOUND"
    )

    # Operation raises exception
    with pytest.raises(OperationError, match="Not found"):
        get_resource_operation(mock_client, "invalid")
```

## Coverage Strategy

### Coverage Target

- **Services**: 100% (MANDATORY)
- **Operations**: 100% (MANDATORY)
- **Mappers**: 90%+ (recommended)
- **Network**: 50%+ (low priority)
- **Steps**: 30%+ (nice to have)

### Measuring Coverage

```bash
# Run with coverage
pytest --cov=titan_plugin_example --cov-report=term-missing --cov-report=html

# View HTML report
open htmlcov/index.html

# Fail if coverage below threshold
pytest --cov=titan_plugin_example --cov-fail-under=90
```

### Coverage Configuration (pytest.ini)

```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

[coverage:run]
source = titan_plugin_example
omit =
    */tests/*
    */__init__.py
    */plugin.py

[coverage:report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
```

## Testing Best Practices

### ✅ DO

1. **Use descriptive test names**:
   ```python
   # ✅ GOOD
   def test_get_resource_returns_ui_model_with_formatted_fields():
       ...

   # ❌ BAD
   def test_get_resource():
       ...
   ```

2. **Use AAA pattern** (Arrange, Act, Assert):
   ```python
   def test_filters_active_resources():
       # Arrange: Setup test data
       mock_client = Mock()
       mock_client.list_resources.return_value = ClientSuccess(data=[...])

       # Act: Execute operation
       result = fetch_active_resources(mock_client)

       # Assert: Verify outcome
       assert len(result) == 2
       assert all(r.status == "active" for r in result)
   ```

3. **Test edge cases**:
   ```python
   # Empty inputs
   def test_handles_empty_list():
       ...

   # Null/None values
   def test_handles_none_values():
       ...

   # Boundary values
   def test_handles_max_length_input():
       ...
   ```

4. **Use pytest fixtures** for reusable setup:
   ```python
   @pytest.fixture
   def configured_service():
       network = Mock()
       return ResourceService(network)
   ```

5. **Mock external dependencies**:
   ```python
   # ✅ Mock HTTP calls
   mock_network.make_request.return_value = {...}

   # ✅ Mock time for consistent tests
   with patch('time.time', return_value=1234567890):
       ...
   ```

### ❌ DON'T

1. **❌ Don't use doctest examples**:
   ```python
   # ❌ WRONG - Doctest not executed
   def validate_input(value: str) -> int:
       """
       Validate input.

       >>> validate_input("123")
       123
       """
       return int(value)

   # ✅ CORRECT - Write real tests
   def validate_input(value: str) -> int:
       """Validate input value."""
       return int(value)

   # tests/test_validators.py
   def test_validate_input_converts_string_to_int():
       assert validate_input("123") == 123
   ```

2. **❌ Don't test implementation details**:
   ```python
   # ❌ BAD - testing internal method
   def test_service_calls_private_method():
       assert service._parse_response(...) == ...

   # ✅ GOOD - testing public behavior
   def test_service_returns_correct_data():
       result = service.get_resource("1")
       assert result.data.id == "1"
   ```

3. **❌ Don't use real API calls**:
   ```python
   # ❌ WRONG - slow, flaky, requires network
   def test_api_call():
       api = RealAPI("https://api.example.com")
       response = api.get("/resource")  # Real HTTP call
       assert response.status_code == 200

   # ✅ CORRECT - fast, reliable, no network
   def test_api_call():
       mock_network = Mock()
       mock_network.make_request.return_value = {"id": "1"}
       service = ResourceService(mock_network)
       result = service.get_resource("1")
       assert isinstance(result, ClientSuccess)
   ```

4. **❌ Don't test multiple things in one test**:
   ```python
   # ❌ BAD - testing too much
   def test_everything():
       assert service.get_resource("1").data.id == "1"
       assert service.list_resources().data == []
       assert service.create_resource("name").data.name == "name"

   # ✅ GOOD - one assertion per test
   def test_get_resource_returns_correct_id():
       result = service.get_resource("1")
       assert result.data.id == "1"

   def test_list_resources_returns_empty_list():
       result = service.list_resources()
       assert result.data == []
   ```

5. **❌ Don't use `try/except` in tests**:
   ```python
   # ❌ BAD - hides failures
   def test_raises_error():
       try:
           validate_input("invalid")
           assert False, "Should have raised"
       except ValueError:
           pass

   # ✅ GOOD - explicit assertion
   def test_raises_error():
       with pytest.raises(ValueError, match="invalid"):
           validate_input("invalid")
   ```

## Test Structure

### Directory Layout

```
tests/
├── conftest.py                  # Shared fixtures
├── __init__.py
│
├── services/                    # Service tests (MANDATORY)
│   ├── __init__.py
│   ├── test_resource_service.py
│   ├── test_metadata_service.py
│   └── test_search_service.py
│
├── operations/                  # Operation tests (MANDATORY)
│   ├── __init__.py
│   ├── test_resource_operations.py
│   ├── test_validation_operations.py
│   └── test_filter_operations.py
│
├── mappers/                     # Mapper tests (recommended)
│   ├── __init__.py
│   ├── test_resource_mapper.py
│   └── test_metadata_mapper.py
│
├── steps/                       # Step tests (optional)
│   ├── __init__.py
│   └── test_list_resources_step.py
│
└── fixtures/                    # Test data
    ├── __init__.py
    ├── sample_api_responses.py  # Mock API data
    └── sample_ui_models.py      # Mock UI models
```

### Test File Template

```python
"""Tests for [module name]."""

import pytest
from unittest.mock import Mock, patch
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_example.clients.services import ResourceService
from titan_plugin_example.clients.network import ExampleAPIError


# Fixtures specific to this test file
@pytest.fixture
def mock_network():
    """Create mock network for ResourceService."""
    return Mock()


@pytest.fixture
def resource_service(mock_network):
    """Create ResourceService with mocked dependencies."""
    return ResourceService(mock_network)


# Test classes (group related tests)
class TestGetResource:
    """Tests for get_resource method."""

    def test_success_case(self, resource_service, mock_network):
        """Should return ClientSuccess when API succeeds."""
        # Arrange
        mock_network.make_request.return_value = {
            "id": "123",
            "name": "Test"
        }

        # Act
        result = resource_service.get_resource("123")

        # Assert
        assert isinstance(result, ClientSuccess)
        assert result.data.id == "123"

    def test_not_found_case(self, resource_service, mock_network):
        """Should return ClientError when resource not found."""
        mock_network.make_request.side_effect = ExampleAPIError(
            "Not found",
            status_code=404
        )

        result = resource_service.get_resource("999")

        assert isinstance(result, ClientError)
        assert result.error_code == "NOT_FOUND"

    # More tests...


class TestListResources:
    """Tests for list_resources method."""

    # Tests...
```

## CI/CD Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run tests with coverage
        run: |
          pytest --cov=titan_plugin_example \
                 --cov-report=xml \
                 --cov-report=term-missing \
                 --cov-fail-under=90

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

## Troubleshooting Tests

### Common Issues

**Issue: Import errors in tests**

```python
# ❌ WRONG - relative imports in tests
from ..clients import ResourceService

# ✅ CORRECT - absolute imports
from titan_plugin_example.clients import ResourceService
```

**Issue: Fixtures not found**

```python
# ✅ SOLUTION - Use conftest.py for shared fixtures
# tests/conftest.py
@pytest.fixture
def mock_client():
    return Mock()

# tests/test_something.py
def test_with_fixture(mock_client):  # Auto-discovered
    ...
```

**Issue: Tests pass locally but fail in CI**

```python
# ❌ PROBLEM - Hardcoded paths
def test_read_file():
    with open("/Users/me/data.json") as f:
        ...

# ✅ SOLUTION - Use Path and fixtures
from pathlib import Path

def test_read_file(tmp_path):
    data_file = tmp_path / "data.json"
    data_file.write_text('{"key": "value"}')
    ...
```

**Issue: Slow tests**

```python
# ❌ PROBLEM - Real API calls, sleep()
def test_api():
    response = requests.get("https://api.example.com")  # Slow!
    time.sleep(1)  # Very slow!

# ✅ SOLUTION - Mock everything
def test_api():
    mock_network = Mock()
    mock_network.make_request.return_value = {...}  # Instant!
```

## Summary

### Testing Checklist

When creating tests for a plugin:

- [ ] Services: 100% coverage
- [ ] Operations: 100% coverage
- [ ] Mappers: 90%+ coverage (if complex)
- [ ] All tests use mocks (no real API calls)
- [ ] Fixtures in `conftest.py` for reusable setup
- [ ] Test both success and error paths
- [ ] Test edge cases (empty, null, max values)
- [ ] Use parametrized tests for multiple inputs
- [ ] Use descriptive test names
- [ ] Follow AAA pattern (Arrange, Act, Assert)
- [ ] CI/CD integration configured
- [ ] Coverage reports generated

### Key Rules

1. **Services & Operations**: 100% coverage MANDATORY
2. **Mock everything**: No real HTTP calls, no file I/O, no databases
3. **Test behavior**: Not implementation details
4. **Fast tests**: Should run in milliseconds
5. **No doctests**: Write real pytest tests instead

---

**Version**: 1.0.0
**Last Updated**: 2026-03-31
**Status**: Production Ready
