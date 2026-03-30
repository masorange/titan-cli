---
name: titan-builder
description: Build Titan CLI plugins, workflows, steps, and hooks following the official 5-layer architecture (Network, Services, Client, Operations, Steps). Generates complete plugin scaffolds with models, tests, and proper separation of concerns. Use when creating new plugins, extending workflows, or implementing custom steps for Titan CLI.
---

# Titan Builder Skill

Complete skill for building Titan CLI plugins, workflows, steps, and hooks following the official 5-layer architecture.

## When to Use This Skill

Invoke this skill when the user requests:
- **New plugin creation**: "Create a Slack plugin", "I need a Jira plugin"
- **Workflow creation**: "Create a workflow for X", "Add a deployment workflow"
- **Custom steps**: "Add a step that does X", "Create a step for Y"
- **Workflow extension**: "Extend the commit-ai workflow", "Add hooks to PR workflow"
- **Plugin scaffolding**: "Scaffold a new plugin for Z"

## Core Architecture Principles

### 5-Layer Architecture (Official Plugins Only)

```
Steps (UI) → Operations (Logic) → Client (Facade) → Services (Data) → Network (HTTP/CLI)
```

**CRITICAL**: This architecture is **MANDATORY for official plugins** (Git, GitHub, Jira). Custom user steps can use any pattern as long as they follow `WorkflowContext → WorkflowResult`.

**📖 [Complete Layer-by-Layer Guide](LAYER_DETAILS.md)** — Deep dive into each layer's responsibilities, patterns, and examples.

#### Layer Responsibilities (Quick Reference)

| Layer | Returns | Responsibility | Can Import | Cannot Import |
|-------|---------|----------------|------------|---------------|
| **Steps** | `WorkflowResult` | UI orchestration, user interaction | `operations/`, `ctx.textual` | `services/`, `network/` |
| **Operations** | `UIModel` or raises | Business logic, pure functions | `clients/*_client.py` (facade only) | `services/`, `network/`, `ctx.textual` |
| **Client** | `ClientResult[UIModel]` | Public API facade | `services/`, `network/` | Operations should not be called from here |
| **Services** | `ClientResult[UIModel]` | Data access (Network → UI) | `network/`, `models/` | `operations/`, `steps/` |
| **Network** | `dict`/`list` | HTTP/CLI communication | `requests`, `subprocess` | Everything else |

**For detailed examples of what each layer MUST and MUST NOT do, see [LAYER_DETAILS.md](LAYER_DETAILS.md)**

### Result Wrapper Pattern

All Client/Service methods return `ClientResult[T]`:

```python
from titan_cli.core.result import ClientSuccess, ClientError, ClientResult

# Service method
def get_resource(id: str) -> ClientResult[UIResource]:
    try:
        data = self.network.make_request("GET", f"/resource/{id}")
        network_model = NetworkResource(**data)
        ui_model = from_network_resource(network_model)
        return ClientSuccess(data=ui_model, message="Resource retrieved")
    except APIError as e:
        return ClientError(error_message=str(e), error_code="API_ERROR")
```

**Steps MUST use pattern matching**:
```python
result = ctx.client.get_resource("123")
match result:
    case ClientSuccess(data=resource):
        ctx.textual.text(f"Found: {resource.name}")
        return Success("Done")
    case ClientError(error_message=err):
        ctx.textual.error_text(f"Failed: {err}")
        return Error(err)
```

## Plugin Structure

### Complete Plugin Scaffold

```
plugins/titan-plugin-{name}/
├── pyproject.toml
├── README.md
├── titan_plugin_{name}/
│   ├── __init__.py
│   ├── plugin.py                    # Plugin registration
│   │
│   ├── models/                      # DATA MODELS (3 sub-layers)
│   │   ├── __init__.py
│   │   ├── network/                 # Network layer - API responses
│   │   │   ├── __init__.py
│   │   │   ├── resource.py          # NetworkResource (faithful to API)
│   │   │   └── ...
│   │   ├── view/                    # View layer - UI models
│   │   │   ├── __init__.py
│   │   │   └── view.py              # UIResource (optimized for display)
│   │   ├── mappers/                 # Mappers - network → view
│   │   │   ├── __init__.py
│   │   │   └── resource_mapper.py   # from_network_resource()
│   │   └── formatting.py            # Shared formatting utils
│   │
│   ├── clients/                     # CLIENT LAYER
│   │   ├── __init__.py
│   │   ├── network/                 # Low-level API executors
│   │   │   ├── __init__.py
│   │   │   └── {name}_api.py        # NameAPI class
│   │   ├── services/                # Business logic services (PRIVATE)
│   │   │   ├── __init__.py
│   │   │   └── resource_service.py  # ResourceService
│   │   └── {name}_client.py         # Public facade
│   │
│   ├── operations/                  # OPERATIONS (pure business logic)
│   │   ├── __init__.py
│   │   └── resource_operations.py   # Pure functions
│   │
│   ├── steps/                       # STEPS (UI orchestration)
│   │   ├── __init__.py
│   │   └── {step_name}_step.py
│   │
│   └── workflows/                   # WORKFLOWS (YAML)
│       └── {workflow-name}.yaml
│
└── tests/
    ├── __init__.py
    ├── conftest.py                  # Shared fixtures
    ├── services/                    # Service tests (MANDATORY)
    │   └── test_resource_service.py
    ├── operations/                  # Operation tests (MANDATORY)
    │   └── test_resource_operations.py
    └── steps/
        └── test_{step_name}_step.py
```

## Implementation Guidelines

### Step 1: Create Plugin Scaffold

**pyproject.toml**:
```toml
[project]
name = "titan-plugin-{name}"
version = "0.1.0"
description = "Titan CLI plugin for {Name}"
requires-python = ">=3.11"
dependencies = [
    "titan-cli>=0.1.0",
    "requests>=2.31.0",  # If HTTP API
]

[project.entry-points."titan.plugins"]
{name} = "titan_plugin_{name}.plugin:plugin_instance"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**plugin.py**:
```python
"""
{Name} Plugin for Titan CLI

Provides {description}.
"""

from titan_cli.core.plugin import Plugin
from .clients import {Name}Client


class {Name}Plugin(Plugin):
    """Plugin for {Name} integration."""

    def __init__(self):
        super().__init__(
            name="{name}",
            version="0.1.0",
            description="{description}",
        )

    def get_workflow_dir(self) -> Path:
        """Return the workflows directory."""
        return Path(__file__).parent / "workflows"

    def get_steps_module(self):
        """Return the steps module for this plugin."""
        from . import steps
        return steps

    def create_client(self, config: dict):
        """Create and return the {Name} client."""
        return {Name}Client(
            base_url=config.get("base_url"),
            api_token=config.get("api_token"),
        )


plugin_instance = {Name}Plugin()
```

### Step 2: Define Models (Network → View)

**models/network/resource.py**:
```python
"""Network models - faithful to API responses."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class NetworkResource:
    """
    Network model for Resource (faithful to API response).

    This model matches the API structure exactly.
    """
    id: str
    name: str
    status: str
    created_at: str
    # ... other fields exactly as API returns
```

**models/view/view.py**:
```python
"""View models - optimized for UI display."""

from dataclasses import dataclass


@dataclass
class UIResource:
    """
    UI model for Resource (optimized for display).

    Pre-formatted fields for rendering.
    """
    id: str
    name: str
    status_icon: str      # ✅, ⏸️, ❌
    status_display: str   # "Active", "Paused", "Failed"
    created_display: str  # "2 hours ago"
```

**models/mappers/resource_mapper.py**:
```python
"""Mappers for converting network models to view models."""

from ..network import NetworkResource
from ..view import UIResource
from ..formatting import format_timestamp, get_status_icon


def from_network_resource(network: NetworkResource) -> UIResource:
    """
    Convert NetworkResource to UIResource.

    Args:
        network: Network model from API

    Returns:
        UI model optimized for display
    """
    return UIResource(
        id=network.id,
        name=network.name,
        status_icon=get_status_icon(network.status),
        status_display=network.status.capitalize(),
        created_display=format_timestamp(network.created_at),
    )
```

### Step 3: Implement Network Layer

**clients/network/{name}_api.py**:
```python
"""Network layer - pure HTTP/CLI communication."""

import requests
from typing import Dict, List, Any


class {Name}APIError(Exception):
    """Exception raised for {Name} API errors."""
    def __init__(self, message: str, status_code: int = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class {Name}API:
    """
    {Name} API client.

    Low-level HTTP communication. Returns raw JSON.
    """

    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Authorization": f"Bearer {api_token}",
        })

    def make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any] | List[Any]:
        """
        Make HTTP request to API.

        Returns:
            Raw JSON response (dict or list)

        Raises:
            {Name}APIError: On HTTP error
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}

        except requests.exceptions.RequestException as e:
            status_code = e.response.status_code if hasattr(e, 'response') else None
            raise {Name}APIError(str(e), status_code=status_code)
```

### Step 4: Implement Services (PRIVATE)

**clients/services/resource_service.py**:
```python
"""Resource service (internal data access layer)."""

from typing import List
from titan_cli.core.result import ClientResult, ClientSuccess, ClientError
from ..network import {Name}API, {Name}APIError
from ...models import NetworkResource, UIResource, from_network_resource


class ResourceService:
    """
    Resource service (PRIVATE - only used by Client).

    Handles: Network call → Parse → Map → Wrap Result
    """

    def __init__(self, network: {Name}API):
        self.network = network

    def get_resource(self, resource_id: str) -> ClientResult[UIResource]:
        """
        Get resource by ID.

        Returns:
            ClientSuccess with UIResource or ClientError
        """
        try:
            # 1. Network call
            data = self.network.make_request("GET", f"resources/{resource_id}")

            # 2. Parse to Network model
            network_resource = NetworkResource(**data)

            # 3. Map to UI model
            ui_resource = from_network_resource(network_resource)

            # 4. Wrap in Result
            return ClientSuccess(
                data=ui_resource,
                message=f"Resource {resource_id} retrieved"
            )

        except {Name}APIError as e:
            error_code = "NOT_FOUND" if e.status_code == 404 else "API_ERROR"
            return ClientError(
                error_message=str(e),
                error_code=error_code
            )

    def list_resources(self) -> ClientResult[List[UIResource]]:
        """
        List all resources.

        Returns:
            ClientSuccess with list of UIResource or ClientError
        """
        try:
            data = self.network.make_request("GET", "resources")

            # Parse list of network models
            network_resources = [NetworkResource(**item) for item in data]

            # Map to UI models
            ui_resources = [from_network_resource(r) for r in network_resources]

            return ClientSuccess(
                data=ui_resources,
                message=f"Found {len(ui_resources)} resources"
            )

        except {Name}APIError as e:
            return ClientError(
                error_message=str(e),
                error_code="API_ERROR"
            )
```

**⚠️ CRITICAL**: Services MUST catch the **BASE exception class**:
```python
# ✅ CORRECT
except {Name}APIError as e:  # Base class - catches ALL API errors

# ❌ WRONG
except {Name}NotFoundError as e:  # Only catches one type
```

### Step 5: Implement Client (Public Facade)

**clients/{name}_client.py**:
```python
"""
{Name} Client Facade.

Public API for {name} plugin.
"""

from typing import List
from titan_cli.core.result import ClientResult
from .services import ResourceService
from .network import {Name}API
from ..models import UIResource


class {Name}Client:
    """
    {Name} Client.

    Public API for {name} plugin. Delegates to internal services.
    """

    def __init__(self, base_url: str, api_token: str):
        # Internal (private) dependencies
        self._network = {Name}API(base_url, api_token)
        self._resource_service = ResourceService(self._network)

    # Public API - delegates to services
    def get_resource(self, resource_id: str) -> ClientResult[UIResource]:
        """Get resource by ID."""
        return self._resource_service.get_resource(resource_id)

    def list_resources(self) -> ClientResult[List[UIResource]]:
        """List all resources."""
        return self._resource_service.list_resources()
```

### Step 6: Create Operations (Optional)

**operations/resource_operations.py**:
```python
"""
Resource Operations

Pure business logic for resource functionality.
UI-agnostic, easily testable.
"""

from typing import List
from ..clients import {Name}Client
from ..models import UIResource


class OperationError(Exception):
    """Exception raised by operations."""
    pass


def fetch_active_resources(client: {Name}Client) -> List[UIResource]:
    """
    Fetch and filter active resources.

    Business logic:
    - Fetch all resources
    - Filter by status = "active"
    - Sort by name

    Args:
        client: {Name}Client instance

    Returns:
        List of active UIResource objects

    Raises:
        OperationError: If fetch fails
    """
    result = client.list_resources()

    match result:
        case ClientSuccess(data=resources):
            # Apply business logic
            active = [r for r in resources if r.status_display == "Active"]
            return sorted(active, key=lambda r: r.name)

        case ClientError(error_message=msg):
            raise OperationError(f"Failed to fetch resources: {msg}")


__all__ = ["fetch_active_resources", "OperationError"]
```

### Step 7: Implement Steps

**steps/list_resources_step.py**:
```python
"""List resources step."""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.core.result import ClientSuccess, ClientError


def list_resources_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    List all resources.

    Simple step - calls client directly, uses pattern matching.
    """
    ctx.textual.begin_step("List Resources")

    # Call client
    result = ctx.{name}.list_resources()

    # Pattern matching is MANDATORY
    match result:
        case ClientSuccess(data=resources, message=msg):
            ctx.textual.success_text(msg)

            # Display resources
            for resource in resources:
                ctx.textual.text(
                    f"{resource.status_icon} {resource.name} - {resource.status_display}"
                )

            ctx.textual.end_step("success")
            return Success(msg, metadata={"resource_count": len(resources)})

        case ClientError(error_message=err):
            ctx.textual.error_text(f"Failed to list resources: {err}")
            ctx.textual.end_step("error")
            return Error(err)


def list_active_resources_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    List active resources only.

    Complex step - uses operation for filtering logic.
    """
    ctx.textual.begin_step("List Active Resources")

    try:
        # Import operation
        from ..operations import fetch_active_resources

        # Operation returns UI models directly
        resources = fetch_active_resources(ctx.{name})

        if not resources:
            ctx.textual.info_text("No active resources found")
            ctx.textual.end_step("success")
            return Success("No active resources")

        for resource in resources:
            ctx.textual.text(f"✅ {resource.name}")

        ctx.textual.end_step("success")
        return Success(f"Found {len(resources)} active resources")

    except Exception as e:
        ctx.textual.error_text(str(e))
        ctx.textual.end_step("error")
        return Error(str(e))
```

### Step 8: Create Workflows

**workflows/list-resources.yaml**:
```yaml
name: "List Resources"
description: "List all resources from {Name}"

steps:
  - id: list_all
    name: "List All Resources"
    plugin: {name}
    step: list_resources_step

  - id: list_active
    name: "List Active Resources Only"
    plugin: {name}
    step: list_active_resources_step
```

**workflows/manage-resource.yaml** (with hooks):
```yaml
name: "Manage Resource"
description: "Create or update a resource with hooks for validation"

hooks:
  - before_create
  - after_create

params:
  resource_name: ""
  resource_type: "default"

steps:
  - id: validate_input
    name: "Validate Input"
    plugin: {name}
    step: validate_resource_input

  - hook: before_create

  - id: create_resource
    name: "Create Resource"
    plugin: {name}
    step: create_resource_step
    params:
      name: "${resource_name}"
      type: "${resource_type}"

  - hook: after_create

  - id: confirm
    name: "Confirm Creation"
    plugin: {name}
    step: confirm_resource_created
```

### Step 9: Write Tests (MANDATORY)

**tests/services/test_resource_service.py**:
```python
"""Tests for ResourceService."""

import pytest
from unittest.mock import Mock
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_{name}.clients.services import ResourceService
from titan_plugin_{name}.clients.network import {Name}APIError


@pytest.fixture
def mock_network():
    """Create mock network."""
    return Mock()


@pytest.fixture
def resource_service(mock_network):
    """Create ResourceService with mock network."""
    return ResourceService(mock_network)


class TestGetResource:
    """Tests for get_resource method."""

    def test_get_resource_success(self, resource_service, mock_network):
        """Should return ClientSuccess with UIResource."""
        # Mock network response
        mock_network.make_request.return_value = {
            "id": "123",
            "name": "Test Resource",
            "status": "active",
            "created_at": "2024-01-01T00:00:00Z"
        }

        result = resource_service.get_resource("123")

        # Verify result type
        assert isinstance(result, ClientSuccess)
        assert result.data.id == "123"
        assert result.data.name == "Test Resource"
        assert result.data.status_icon == "✅"

    def test_get_resource_not_found(self, resource_service, mock_network):
        """Should return ClientError with NOT_FOUND code."""
        mock_network.make_request.side_effect = {Name}APIError(
            "Not found",
            status_code=404
        )

        result = resource_service.get_resource("999")

        assert isinstance(result, ClientError)
        assert result.error_code == "NOT_FOUND"

    def test_get_resource_api_error(self, resource_service, mock_network):
        """Should return ClientError with API_ERROR code."""
        mock_network.make_request.side_effect = {Name}APIError(
            "Server error",
            status_code=500
        )

        result = resource_service.get_resource("123")

        assert isinstance(result, ClientError)
        assert result.error_code == "API_ERROR"
```

**tests/operations/test_resource_operations.py**:
```python
"""Tests for resource operations."""

import pytest
from unittest.mock import Mock
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_{name}.operations import fetch_active_resources, OperationError
from titan_plugin_{name}.models import UIResource


@pytest.fixture
def mock_client():
    """Create mock client."""
    return Mock()


class TestFetchActiveResources:
    """Tests for fetch_active_resources operation."""

    def test_fetch_filters_active_only(self, mock_client):
        """Should filter and return only active resources."""
        # Mock client response
        mock_client.list_resources.return_value = ClientSuccess(data=[
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
        ])

        result = fetch_active_resources(mock_client)

        # Should only return active ones, sorted by name
        assert len(result) == 2
        assert result[0].name == "Active 1"
        assert result[1].name == "Active 2"
        assert all(r.status_display == "Active" for r in result)

    def test_fetch_raises_on_error(self, mock_client):
        """Should raise OperationError when client fails."""
        mock_client.list_resources.return_value = ClientError(
            error_message="API error",
            error_code="API_ERROR"
        )

        with pytest.raises(OperationError, match="Failed to fetch resources"):
            fetch_active_resources(mock_client)
```

**Target: 100% test coverage on Services and Operations**

## Extending Workflows (Hooks)

### Base Workflow (in plugin)

**plugins/titan-plugin-{name}/workflows/deploy.yaml**:
```yaml
name: "Deploy Application"
description: "Deploy application with customizable hooks"

hooks:
  - before_deploy
  - after_deploy

params:
  environment: "staging"

steps:
  - id: validate
    name: "Validate Environment"
    plugin: {name}
    step: validate_environment

  - hook: before_deploy

  - id: deploy
    name: "Deploy to ${environment}"
    plugin: {name}
    step: deploy_step
    params:
      env: "${environment}"

  - hook: after_deploy

  - id: verify
    name: "Verify Deployment"
    plugin: {name}
    step: verify_deployment
```

### Extended Workflow (in project)

**.titan/workflows/deploy.yaml**:
```yaml
name: "Deploy with Tests and Notifications"
description: "Extended deployment with pre/post hooks"
extends: "plugin:{name}/deploy"

params:
  environment: "production"
  notify_channel: "#deployments"

hooks:
  before_deploy:
    - id: run_tests
      name: "Run Integration Tests"
      plugin: project
      step: run_integration_tests
      on_error: fail

    - id: backup_db
      name: "Backup Database"
      plugin: project
      step: backup_database
      on_error: fail

  after_deploy:
    - id: smoke_tests
      name: "Run Smoke Tests"
      plugin: project
      step: run_smoke_tests
      on_error: continue

    - id: notify_slack
      name: "Notify Team"
      plugin: project
      step: notify_slack
      params:
        channel: "${notify_channel}"
      on_error: continue
```

## Custom Project Steps (Simple Pattern)

For custom user steps (not official plugins), you can use a simpler pattern:

**.titan/steps/my_custom_step.py**:
```python
"""Custom project step - simple pattern (no 5-layer architecture required)."""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip


def my_custom_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Custom step for project-specific logic.

    User steps can use ANY pattern - the only requirement is:
    WorkflowContext → WorkflowResult
    """
    ctx.textual.begin_step("My Custom Step")

    # Your logic here (can be inline for simple steps)
    value = ctx.get("some_param", "default")

    if not value:
        ctx.textual.warning_text("No value provided")
        ctx.textual.end_step("success")
        return Skip("Nothing to do")

    # Do something
    ctx.textual.info_text(f"Processing: {value}")

    # Call external services, run shell commands, etc.
    # ...

    ctx.textual.success_text("Done!")
    ctx.textual.end_step("success")
    return Success("Completed", metadata={"result": value})
```

**.titan/workflows/custom-workflow.yaml**:
```yaml
name: "My Custom Workflow"

params:
  some_param: "default_value"

steps:
  - id: my_step
    name: "My Custom Step"
    plugin: project  # ← Uses .titan/steps/
    step: my_custom_step
    params:
      some_param: "${some_param}"
```

## Implementation Checklist

When building a new plugin, ensure:

### Models
- [ ] Network models in `models/network/` (faithful to API)
- [ ] UI models in `models/view/` (pre-formatted for display)
- [ ] Mappers in `models/mappers/` (network → view conversion)
- [ ] Formatting utilities in `models/formatting.py`

### Services
- [ ] All methods return `ClientResult[UIModel]`
- [ ] Catch BASE exception class (not specific subclasses)
- [ ] Process: Network call → Parse → Map → Wrap Result
- [ ] Services are PRIVATE (only Client imports them)

### Client
- [ ] Simple facade delegating to services
- [ ] All methods return `ClientResult[UIModel]`
- [ ] NO business logic

### Steps
- [ ] **MANDATORY**: Pattern matching for all `ClientResult`
- [ ] NO direct `.data` access
- [ ] Clear, specific error messages
- [ ] Use `ctx.textual` for all UI

### Operations (if needed)
- [ ] Work with UI models, NOT dicts
- [ ] Pure functions (no side effects)
- [ ] Well-typed parameters and return values
- [ ] NO `ctx.textual` or UI dependencies

### Tests
- [ ] Service tests: 100% coverage
- [ ] Operation tests: 100% coverage
- [ ] Use mocks, not real API calls
- [ ] Test both success and error paths

### Workflows
- [ ] Clear name and description
- [ ] Declare hooks if extensible
- [ ] Use `${variable}` substitution for params
- [ ] Use `on_error: continue` for cleanup guarantee

## Common Patterns

### Pattern: Guaranteed Cleanup

```yaml
steps:
  # Early steps: Exit OK (no resources yet)
  - id: select_item
    plugin: {name}
    step: select_item_step
    # If returns Exit here → no problem

  # After resource creation: use Skip (not Exit) + on_error: continue
  - id: create_resource
    plugin: {name}
    step: create_resource_step
    on_error: continue  # ← Continue even if fails

  - id: do_work
    plugin: {name}
    step: work_step
    on_error: continue  # ← Returns Skip if nothing to do

  - id: cleanup  # ← ALWAYS runs
    plugin: {name}
    step: cleanup_step
```

### Pattern: Multi-Step Workflow with Nested Call

```yaml
name: "Complete Workflow"

steps:
  # Call another workflow first
  - id: prerequisite
    name: "Run Prerequisite Workflow"
    workflow: "plugin:{name}/prepare"

  # Then continue with main steps
  - id: main_work
    plugin: {name}
    step: main_step

  - id: finalize
    plugin: {name}
    step: finalize_step
```

### Pattern: Conditional Execution

```python
def conditional_step(ctx: WorkflowContext) -> WorkflowResult:
    """Step that may skip based on conditions."""
    ctx.textual.begin_step("Conditional Step")

    feature_enabled = ctx.get("feature_enabled", False)

    if not feature_enabled:
        ctx.textual.info_text("Feature not enabled, skipping")
        ctx.textual.end_step("success")
        return Skip("Feature disabled")

    # Continue with work...
    ctx.textual.end_step("success")
    return Success("Completed")
```

## Critical Rules Summary

1. **Official plugins**: MUST follow 5-layer architecture
2. **Custom steps**: Can use any pattern (just need `WorkflowContext → WorkflowResult`)
3. **Pattern matching**: MANDATORY for all `ClientResult` in steps
4. **Services**: Catch BASE exception class, not specific subclasses
5. **Operations**: Pure functions, NO UI dependencies
6. **Tests**: 100% coverage for Services and Operations
7. **Cleanup**: Use `Skip` (not `Exit`) after resource creation
8. **Hooks**: Declare in base workflow, implement in extending workflow

## ⚠️ CRITICAL: Common Mistakes to Avoid

Before generating ANY code, review the **[Common Mistakes & Anti-Patterns](COMMON_MISTAKES.md)** document. It contains 10 critical errors found in real code reviews:

### Top 5 Must-Avoid Mistakes:

1. **❌ Operations returning `ClientResult`** → ✅ Return `T` or raise
2. **❌ Client returning `NetworkModel`** → ✅ Return `UIModel`
3. **❌ Business logic in Client** → ✅ Move to Service or Operation
4. **❌ Using `try/except` for `ClientResult` in Steps** → ✅ Use `match/case`
5. **❌ Calling API multiple times** → ✅ Single call with complete data

**Read the full document before coding**: `.titan/skills/titan-builder/COMMON_MISTAKES.md`

### Validation Checklist (Run Before Submitting Code)

- [ ] Operations return `T` or raise (NOT `ClientResult[T]`)
- [ ] Client returns `ClientResult[UIModel]` (NOT `NetworkModel`)
- [ ] Client has NO business logic (search, filter, validate → Service/Operation)
- [ ] Client has NO mapping (Network→UI happens in Service)
- [ ] Steps use `match`/`case` for `ClientResult` (NO `try`/`except`)
- [ ] Docstrings have NO `>>>` examples (write tests instead)
- [ ] Steps call API once per data (include all needed data in response)
- [ ] Steps use `bold_text()` for headers (NOT `markdown()`)
- [ ] Validation checks ALL constraints (min, max, format)
- [ ] None handling uses explicit checks (NOT `dict.pop()` assumptions)

## Documentation Index

### Architecture & Patterns
- **[Layer Details](LAYER_DETAILS.md)** ⭐ — Complete breakdown of each layer (800+ lines)
- **[Common Mistakes](COMMON_MISTAKES.md)** ⚠️ — 10 critical errors to avoid
- **[Examples](EXAMPLES.md)** — Real-world plugin examples

### Project Docs
- `.claude/docs/plugin-architecture.md` — Official architecture overview
- `.claude/docs/workflows.md` — Workflow system guide
- `.claude/docs/operations.md` — Operations pattern guide

### Code References
- `plugins/titan-plugin-{github,git,jira}/` — Reference implementations

**Remember**: When building official plugins, follow the 5-layer architecture strictly. For custom project steps, keep it simple!
