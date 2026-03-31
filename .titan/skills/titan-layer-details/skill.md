---
name: titan-layer-details
description: Deep dive into each of the 5 architectural layers - detailed responsibilities, capabilities, and constraints for Steps, Operations, Client, Services, and Network. Use when user says "what can Layer X do", "layer constraints", "layer details", "what must Steps do", "what can't Services do", or asks for "detailed layer guide", "layer responsibilities deep dive".
keywords: layers, architecture details, responsibilities, constraints, layer boundaries, what can do, what cannot do
metadata:
  author: MasOrange
  version: 1.0.0
---

# Titan CLI - Layer-by-Layer Deep Dive

Complete breakdown of each layer's responsibilities in the 5-layer architecture.

---

## Overview

The 5-layer architecture separates concerns across clearly defined boundaries:

```
Steps (UI) → Operations (Logic) → Client (Facade) → Services (Data) → Network (HTTP/CLI)
```

Each layer has **specific responsibilities** and **strict boundaries**. This document details what each layer MUST do, CAN do, and MUST NOT do.

---

## Layer 1: Steps (UI/UX)

**Purpose**: Orchestrate user experience and workflow execution.

### Core Responsibilities

**1. User Interaction**
- Display information (`ctx.textual.text()`, `.success_text()`, `.error_text()`)
- Get user input (`ctx.textual.ask_text()`, `.ask_confirm()`, `.ask_selection()`)
- Mount complex widgets (Panel, Table, Markdown)

**2. Workflow Orchestration**
- Call operations/client methods
- Pattern match `ClientResult`
- Return `WorkflowResult` (Success/Error/Skip/Exit)

**3. State Management**
- Read context: `ctx.get("key", "default")`
- Write metadata: `return Success("msg", metadata={...})`

**4. Step Lifecycle**
```python
def my_step(ctx: WorkflowContext) -> WorkflowResult:
    ctx.textual.begin_step("Step Name")
    # ... work ...
    ctx.textual.end_step("success")  # or "error"
    return Success("Message")
```

### What Steps MUST Do

✅ **Pattern match ALL ClientResult**:
```python
match result:
    case ClientSuccess(data=item):
        # Use item
    case ClientError(error_message=err):
        # Handle error
```

✅ **Begin and end every step**:
```python
ctx.textual.begin_step("Name")
ctx.textual.end_step("success" | "error")
```

✅ **Return WorkflowResult**:
```python
return Success("msg", metadata={...})
return Error("msg", code=...)
return Skip("msg")
return Exit("msg")
```

### What Steps MUST NOT Do

❌ **NO business logic** - Delegate to operations:
```python
# ❌ BAD
for item in items:
    if item.status == "pending" and item.priority > 3:
        filtered.append(item)

# ✅ GOOD
filtered = filter_high_priority_pending(items)
```

❌ **NO try/except for ClientResult** - Use pattern matching:
```python
# ❌ BAD
try:
    result = ctx.client.get_item()
    item = result.data
except Exception as e:
    ...

# ✅ GOOD
match ctx.client.get_item():
    case ClientSuccess(data=item):
        ...
    case ClientError(error_message=err):
        ...
```

❌ **NO importing Services or Network**:
```python
# ❌ BAD
from ..clients.services import ResourceService

# ✅ GOOD
from ..operations import fetch_resources
# Or use ctx.client
```

❌ **NO data transformation** - Data comes pre-formatted:
```python
# ❌ BAD
ui_items = [UIItem(id=item["id"], name=item["name"]) for item in raw]

# ✅ GOOD
match ctx.client.get_items():
    case ClientSuccess(data=ui_items):  # Already UIItem objects
        for item in ui_items:
            ctx.textual.text(item.name)
```

### Return Types

- **Success**: Step completed successfully, continue workflow
- **Skip**: Nothing to do (not an error), continue workflow
- **Error**: Step failed, stop workflow (unless `on_error: continue`)
- **Exit**: User cancelled, stop immediately (cleanup may not run)

**Critical**: Use `Skip` (not `Exit`) after resource creation to guarantee cleanup.

---

## Layer 2: Operations (Business Logic)

**Purpose**: Pure, testable business logic independent of UI or data access.

### Core Responsibilities

**1. Complex Filtering and Searching**
```python
def find_resources_by_criteria(
    client: ResourceClient,
    name: str = None,
    status: str = None,
    min_priority: int = None
) -> List[UIResource]:
    """Find resources matching criteria."""
    result = client.list_resources()

    match result:
        case ClientSuccess(data=resources):
            filtered = resources
            if name:
                filtered = [r for r in filtered if name.lower() in r.name.lower()]
            if status:
                filtered = [r for r in filtered if r.status == status]
            if min_priority is not None:
                filtered = [r for r in filtered if r.priority >= min_priority]
            return filtered

        case ClientError(error_message=err):
            raise OperationError(f"Failed to fetch: {err}")
```

**2. Multi-Step Business Processes**
```python
def create_resource_with_validation(
    client: ResourceClient,
    name: str,
    type_id: str
) -> UIResource:
    """Create resource with validation."""
    # Check uniqueness
    existing = client.get_resource_by_name(name)
    match existing:
        case ClientSuccess(data=_):
            raise OperationError(f"Resource '{name}' already exists")
        case ClientError(error_code="NOT_FOUND"):
            pass  # Good

    # Validate type
    types_result = client.list_types()
    match types_result:
        case ClientSuccess(data=types):
            if not any(t.id == type_id for t in types):
                raise OperationError(f"Invalid type: {type_id}")
        case ClientError(error_message=err):
            raise OperationError(f"Failed to validate type: {err}")

    # Create
    result = client.create_resource(name, type_id)
    match result:
        case ClientSuccess(data=resource):
            return resource
        case ClientError(error_message=err):
            raise OperationError(f"Failed to create: {err}")
```

**3. Data Transformation and Calculations**
```python
def calculate_resource_score(resource: UIResource) -> int:
    """Calculate resource score based on multiple factors."""
    score = 0
    score += resource.priority * 10
    if resource.status == "Active":
        score += 50
    if resource.assigned_to:
        score += 20
    return score
```

### What Operations MUST Do

✅ **Be pure functions** - No side effects:
```python
def filter_resources(resources: List[UIResource], status: str) -> List[UIResource]:
    """Pure function - same input = same output."""
    return [r for r in resources if r.status == status]
```

✅ **Work with UI models** - Never Network models:
```python
def process_resource(resource: UIResource) -> UIResource:  # ✅ UI model
    ...
```

✅ **Return data directly or raise**:
```python
def get_resource(client: Client, id: str) -> UIResource:  # Returns UIResource
    result = client.get_resource(id)
    match result:
        case ClientSuccess(data=resource):
            return resource  # ✅ Return data
        case ClientError(error_message=err):
            raise OperationError(err)  # ✅ Or raise
```

✅ **Pattern match ClientResult** when calling client:
```python
result = client.get_resource(id)
match result:
    case ClientSuccess(data=item):
        return item
    case ClientError(error_message=err):
        raise OperationError(err)
```

### What Operations MUST NOT Do

❌ **NO returning ClientResult**:
```python
# ❌ BAD - Operations don't return ClientResult
def get_resource(client: Client, id: str) -> ClientResult[UIResource]:
    return client.get_resource(id)

# ✅ GOOD - Return data or raise
def get_resource(client: Client, id: str) -> UIResource:
    match client.get_resource(id):
        case ClientSuccess(data=resource):
            return resource
        case ClientError(error_message=err):
            raise OperationError(err)
```

❌ **NO UI dependencies**:
```python
# ❌ BAD
def process_resource(ctx: WorkflowContext, id: str):
    ctx.textual.text("Processing...")

# ✅ GOOD
def process_resource(client: Client, id: str) -> UIResource:
    # No ctx, no UI
```

❌ **NO importing Services or Network**:
```python
# ❌ BAD
from ..clients.services import ResourceService

# ✅ GOOD
from ..clients.resource_client import ResourceClient  # Facade only
```

### Return Types

- **UIModel** - Return the data directly (e.g., `UIResource`, `List[UIResource]`)
- **Raise exception** - `raise OperationError("reason")` on failure
- **Never ClientResult** - That's for Client/Services only

---

## Layer 3: Client (Public Facade)

**Purpose**: Provide clean, unified public API. Delegates ALL work to Services.

### Core Responsibilities

**1. Simple Delegation**
```python
class ResourceClient:
    """Public API facade."""

    def __init__(self, base_url: str, api_token: str):
        self._network = ResourceAPI(base_url, api_token)
        self._resource_service = ResourceService(self._network)

    def get_resource(self, id: str) -> ClientResult[UIResource]:
        """Get resource by ID."""
        return self._resource_service.get_resource(id)

    def list_resources(self) -> ClientResult[List[UIResource]]:
        """List all resources."""
        return self._resource_service.list_resources()
```

**2. Basic Parameter Validation** (Optional)
```python
def get_resource(self, id: str) -> ClientResult[UIResource]:
    """Get resource by ID."""
    if not id or not id.strip():
        return ClientError(
            error_message="Resource ID is required",
            error_code="MISSING_PARAMETER"
        )
    return self._resource_service.get_resource(id)
```

**3. Default Values** (Optional)
```python
def __init__(self, base_url: str, api_token: str, default_project_id: str = None):
    self._network = ResourceAPI(base_url, api_token)
    self._service = ResourceService(self._network)
    self.default_project_id = default_project_id

def list_resources(self, project_id: str = None) -> ClientResult[List[UIResource]]:
    """List resources."""
    pid = project_id or self.default_project_id
    if not pid:
        return ClientError(error_message="Project ID required")
    return self._service.list_resources(pid)
```

### What Client MUST Do

✅ **Delegate to Services** - ALL logic in services:
```python
def get_resource(self, id: str) -> ClientResult[UIResource]:
    return self._resource_service.get_resource(id)  # Just delegate
```

✅ **Return ClientResult[UIModel]**:
```python
def get_resource(self, id: str) -> ClientResult[UIResource]:  # ✅ UI model
    ...
```

✅ **Keep services private**:
```python
def __init__(self, ...):
    self._resource_service = ResourceService(...)  # ✅ Private (underscore)
```

### What Client MUST NOT Do

❌ **NO business logic** - Delegate to services:
```python
# ❌ BAD - Logic in client
def get_active_resources(self) -> ClientResult[List[UIResource]]:
    result = self._service.list_resources()
    match result:
        case ClientSuccess(data=resources):
            active = [r for r in resources if r.status == "Active"]
            return ClientSuccess(data=active)

# ✅ GOOD - Delegate to service
def get_active_resources(self) -> ClientResult[List[UIResource]]:
    return self._service.get_active_resources()
```

❌ **NO data mapping** - Services do the mapping:
```python
# ❌ BAD - Mapping in client
def get_resource(self, id: str) -> ClientResult[UIResource]:
    data = self._network.get_resource(id)
    network = NetworkResource(**data)
    ui = from_network_resource(network)  # ❌ Mapping
    return ClientSuccess(data=ui)

# ✅ GOOD - Service handles mapping
def get_resource(self, id: str) -> ClientResult[UIResource]:
    return self._service.get_resource(id)  # ✅ Just delegate
```

❌ **NO returning Network models**:
```python
# ❌ BAD
def get_resource(self, id: str) -> ClientResult[NetworkResource]:  # Network model
    ...

# ✅ GOOD
def get_resource(self, id: str) -> ClientResult[UIResource]:  # UI model
    ...
```

### Return Types

- **Always ClientResult[UIModel]** - E.g., `ClientResult[UIResource]`, `ClientResult[List[UIResource]]`
- **Never Network models** - Always UI models
- **Never plain dict** - Always typed models

---

## Layer 4: Services (Data Access)

**Purpose**: Fetch data from Network layer and transform to UI models.

### Core Responsibilities

**1. Network → UI Transformation**
```python
class ResourceService:
    """Internal service - Network → UI transformation."""

    def __init__(self, network: ResourceAPI):
        self._network = network

    def get_resource(self, id: str) -> ClientResult[UIResource]:
        """Get resource by ID."""
        try:
            # 1. Call Network layer
            data = self._network.make_request("GET", f"/resources/{id}")

            # 2. Parse to Network model
            network_resource = NetworkResource(**data)

            # 3. Map to UI model
            ui_resource = from_network_resource(network_resource)

            # 4. Return wrapped
            return ClientSuccess(
                data=ui_resource,
                message="Resource retrieved"
            )
        except APIError as e:  # Catch BASE exception only
            return ClientError(
                error_message=str(e),
                error_code=getattr(e, "code", "API_ERROR")
            )
```

**2. Batch Transformations**
```python
def list_resources(self) -> ClientResult[List[UIResource]]:
    """List all resources."""
    try:
        data = self._network.make_request("GET", "/resources")

        # Parse all to Network models
        network_resources = [NetworkResource(**item) for item in data]

        # Map all to UI models
        ui_resources = [from_network_resource(nr) for nr in network_resources]

        return ClientSuccess(data=ui_resources)
    except APIError as e:
        return ClientError(error_message=str(e))
```

**3. Error Handling**
```python
try:
    data = self._network.make_request("GET", "/resource/123")
    # ... transformation ...
    return ClientSuccess(data=ui_resource)
except APIError as e:  # ✅ Catch BASE exception
    return ClientError(
        error_message=str(e),
        error_code="API_ERROR"
    )
except Exception as e:  # ✅ Catch-all for unexpected errors
    return ClientError(
        error_message=f"Unexpected error: {str(e)}",
        error_code="INTERNAL_ERROR"
    )
```

### What Services MUST Do

✅ **Transform Network → UI**:
```python
# 1. Network call
data = self._network.make_request(...)

# 2. Network model
network = NetworkResource(**data)

# 3. UI model
ui = from_network_resource(network)

# 4. Return wrapped
return ClientSuccess(data=ui)
```

✅ **Return ClientResult[UIModel]**:
```python
def get_resource(self, id: str) -> ClientResult[UIResource]:  # ✅ UI model
    ...
```

✅ **Catch base exceptions only**:
```python
try:
    ...
except APIError as e:  # ✅ Base exception
    return ClientError(...)
```

### What Services MUST NOT Do

❌ **NO business logic** - Just transformation:
```python
# ❌ BAD - Filtering in service
def get_active_resources(self) -> ClientResult[List[UIResource]]:
    data = self._network.make_request("GET", "/resources")
    resources = [from_network_resource(NetworkResource(**item)) for item in data]
    active = [r for r in resources if r.status == "Active"]  # ❌ Logic
    return ClientSuccess(data=active)

# ✅ GOOD - Fetch all, let operation filter
def list_resources(self) -> ClientResult[List[UIResource]]:
    data = self._network.make_request("GET", "/resources")
    resources = [from_network_resource(NetworkResource(**item)) for item in data]
    return ClientSuccess(data=resources)  # ✅ Just transform
```

❌ **NO returning Network models**:
```python
# ❌ BAD
def get_resource(self, id: str) -> ClientResult[NetworkResource]:
    ...

# ✅ GOOD
def get_resource(self, id: str) -> ClientResult[UIResource]:
    ...
```

❌ **NO specific exception catching**:
```python
# ❌ BAD - Too specific
try:
    ...
except requests.exceptions.Timeout as e:  # ❌ Too specific
    ...

# ✅ GOOD - Catch base class
try:
    ...
except APIError as e:  # ✅ Base exception
    ...
```

### Return Types

- **Always ClientResult[UIModel]** - Never Network models
- **Use mappers** - Call `from_network_*()` functions
- **Wrap in ClientSuccess/ClientError** - Never return raw data

---

## Layer 5: Network (HTTP/CLI)

**Purpose**: Low-level communication with external APIs or CLI tools.

### Core Responsibilities

**1. HTTP Requests**
```python
class ResourceAPI:
    """Low-level HTTP client."""

    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url
        self.api_token = api_token

    def make_request(
        self,
        method: str,
        endpoint: str,
        data: dict = None
    ) -> dict:
        """Make HTTP request and return raw JSON."""
        url = f"{self.base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self.api_token}"}

        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=data
        )

        if not response.ok:
            raise APIError(f"Request failed: {response.status_code}")

        return response.json()
```

**2. CLI Execution**
```python
class GitAPI:
    """Low-level Git CLI wrapper."""

    def run_command(self, args: List[str], cwd: str = None) -> dict:
        """Run git command and return parsed output."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True
            )
            return {"stdout": result.stdout, "stderr": result.stderr}
        except subprocess.CalledProcessError as e:
            raise APIError(f"Git command failed: {e.stderr}")
```

### What Network MUST Do

✅ **Return raw data** - dict or list:
```python
def get_resource(self, id: str) -> dict:  # ✅ Return dict
    response = requests.get(f"{self.base_url}/resources/{id}")
    return response.json()  # ✅ Raw dict
```

✅ **Raise on errors**:
```python
if not response.ok:
    raise APIError(f"Request failed: {response.status_code}")
```

### What Network MUST NOT Do

❌ **NO creating models** - Return raw data:
```python
# ❌ BAD
def get_resource(self, id: str) -> NetworkResource:
    data = requests.get(...).json()
    return NetworkResource(**data)  # ❌ Creating model

# ✅ GOOD
def get_resource(self, id: str) -> dict:
    return requests.get(...).json()  # ✅ Raw dict
```

❌ **NO transformation** - Just fetch:
```python
# ❌ BAD
def get_resource(self, id: str) -> dict:
    data = requests.get(...).json()
    data["formatted_name"] = data["name"].upper()  # ❌ Transform
    return data

# ✅ GOOD
def get_resource(self, id: str) -> dict:
    return requests.get(...).json()  # ✅ Raw
```

### Return Types

- **dict** - For single objects
- **list** - For collections
- **Raise APIError** - On failures

---

## Data Flow Examples

### Example 1: Simple Fetch

```
User: "Show me resource ABC-123"

Step → Client → Service → Network
 ↓       ↓        ↓         ↓
UI    Delegate  Transform  HTTP

┌─ Step ─────────────────────┐
│ result = ctx.client.        │
│   get_resource("ABC-123")   │
│                             │
│ match result:               │
│   case ClientSuccess(data): │
│     display(data.name)      │
└─────────────┬───────────────┘
              ↓
┌─ Client ────────────────────┐
│ def get_resource(id):       │
│   return self._service.     │
│     get_resource(id)        │
└─────────────┬───────────────┘
              ↓
┌─ Service ───────────────────┐
│ data = network.request()    │
│ network_model = Network(**) │
│ ui_model = mapper(network)  │
│ return Success(ui_model)    │
└─────────────┬───────────────┘
              ↓
┌─ Network ───────────────────┐
│ response = requests.get()   │
│ return response.json()      │
└─────────────────────────────┘

Returns: {"id": "ABC-123", "name": "...", ...}
```

### Example 2: Complex Operation

```
User: "Find pending resources for user@example.com"

Step → Operation → Client → Service → Network

┌─ Step ─────────────────────┐
│ try:                        │
│   resources = find_pending( │
│     client, "user@.com"     │
│   )                         │
│ except OperationError:      │
│   handle_error()            │
└─────────────┬───────────────┘
              ↓
┌─ Operation ─────────────────┐
│ result = client.list_user() │
│ match result:               │
│   case Success(data):       │
│     return [r for r in data │
│       if r.status=="Pending"]│
│   case Error(err):          │
│     raise OperationError()  │
└─────────────┬───────────────┘
              ↓
┌─ Client ────────────────────┐
│ return service.list_user()  │
└─────────────┬───────────────┘
              ↓
┌─ Service ───────────────────┐
│ data = network.request()    │
│ models = [map(item) for...] │
│ return Success(models)      │
└─────────────┬───────────────┘
              ↓
┌─ Network ───────────────────┐
│ return requests.get().json()│
└─────────────────────────────┘
```

---

## Layer Interaction Rules

### Import Rules

```
Steps         CAN import: operations/, ctx.client
              CANNOT import: services/, network/

Operations    CAN import: clients/*_client.py (facade only)
              CANNOT import: services/, network/, ctx.textual

Client        CAN import: services/, network/, models/
              CANNOT import: operations/, steps/

Services      CAN import: network/, models/
              CANNOT import: operations/, steps/, client/

Network       CAN import: requests, subprocess
              CANNOT import: Everything else
```

### Dependency Diagram

```
┌──────────┐
│  Steps   │  (UI orchestration)
└────┬─────┘
     │
     ├─────► Operations (business logic)
     │             │
     └─────────────┴──► Client (public facade)
                              │
                              └──► Services (data access)
                                        │
                                        └──► Network (HTTP/CLI)
```

**Flow**:
1. Steps call Operations or Client
2. Operations call Client (facade only)
3. Client delegates to Services
4. Services call Network and map to UI
5. Network returns raw data

---

## Summary

| Layer | Returns | Can Import | Cannot Import |
|-------|---------|------------|---------------|
| **Steps** | `WorkflowResult` | operations/, ctx.client | services/, network/ |
| **Operations** | `UIModel` or raises | client facade | services/, network/, ctx.textual |
| **Client** | `ClientResult[UIModel]` | services/, network/ | operations/, steps/ |
| **Services** | `ClientResult[UIModel]` | network/, models/ | operations/, steps/ |
| **Network** | `dict` / `list` | requests, subprocess | models/, services/ |

**Key Principles**:
1. **Steps**: UI only, no logic
2. **Operations**: Pure functions, no UI
3. **Client**: Just delegates, no logic
4. **Services**: Transform Network → UI
5. **Network**: Raw data only

For architectural overview, see [Plugin Architecture](../titan-plugin-architecture/skill.md).
For common mistakes, see [Antipatterns](../titan-antipatterns/skill.md).

---

## Quick Examples

### Example 1: User asks "What can Steps do?"

**User says**: "Can my step call the network layer directly?"

**What Claude explains**:
- Shows Layer 1: Steps section
- Lists what Steps MUST do (pattern matching, lifecycle)
- Lists what Steps MUST NOT do (no Services/Network imports)
- Provides correct alternative (use operations or ctx.client)

**Result**: Clear boundaries for Step layer

### Example 2: User asks "Should this go in Service or Operation?"

**User says**: "Where should I put this filtering logic?"

**What Claude explains**:
- Service: Network → UI transformation (data access)
- Operation: Business logic (filtering, validation)
- Shows both layers with examples
- Recommends Operation for filtering

**Result**: Logic placed in correct layer

### Example 3: User asks "What does each layer return?"

**User says**: "I'm confused about return types"

**What Claude shows**:
- Summary table with all 5 layers
- Return types for each (ClientResult, UIModel, dict, etc.)
- Import rules (who can import what)
- Data flow diagram

**Result**: Complete layer interaction guide

---

## Troubleshooting

### Issue: "Can I import X from Y layer?"
**Solution**: Check Layer Interaction Rules section. General rule: can import DOWN the stack, never UP.

### Issue: "Which layer should this code go in?"
**Checklist**:
- Talks to HTTP/CLI? → Network
- Transforms Network → UI? → Service
- Business logic? → Operation
- User interaction? → Step
- Just delegates? → Client

### Issue: "My layer is doing too much"
**Solution**: Likely mixing responsibilities. Review "What Layer X MUST NOT Do" for your layer.

---

**Version**: 1.0.0
**Last updated**: 2026-03-31
