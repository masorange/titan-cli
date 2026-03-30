# Layer-by-Layer Deep Dive

**Complete breakdown of each layer's responsibilities in the 5-layer architecture**

This document provides granular detail on what each layer does, doesn't do, and how layers interact.

---

## Table of Contents

1. [Layer 1: Steps (UI/UX)](#layer-1-steps-uiux)
2. [Layer 2: Operations (Business Logic)](#layer-2-operations-business-logic)
3. [Layer 3: Client (Public Facade)](#layer-3-client-public-facade)
4. [Layer 4: Services (Data Access)](#layer-4-services-data-access)
5. [Layer 5: Network (HTTP/CLI)](#layer-5-network-httpcli)
6. [Data Flow Examples](#data-flow-examples)
7. [Layer Interaction Rules](#layer-interaction-rules)

---

## Layer 1: Steps (UI/UX)

**Purpose**: Orchestrate the user experience and workflow execution.

### Core Responsibilities

#### 1. User Interaction
```python
# Displaying information
ctx.textual.text("Processing...")
ctx.textual.bold_text("Important Message")
ctx.textual.success_text("✓ Completed")
ctx.textual.error_text("✗ Failed")
ctx.textual.warning_text("⚠ Warning")
ctx.textual.dim_text("(optional detail)")

# Getting user input
name = ctx.textual.ask_text("Enter name:")
confirmed = ctx.textual.ask_confirm("Proceed?")
index = ctx.textual.ask_selection("Choose:", ["Option 1", "Option 2"])

# Displaying complex content
ctx.textual.markdown(long_formatted_content)
ctx.textual.mount(Panel("Info", panel_type="info"))
ctx.textual.mount(Table(headers, rows))
```

#### 2. Workflow Orchestration
```python
def my_step(ctx: WorkflowContext) -> WorkflowResult:
    # ALWAYS start with this
    ctx.textual.begin_step("Step Name")

    # 1. Get parameters from context
    param1 = ctx.get("param1")
    param2 = ctx.get("param2", "default")

    # 2. Call client/operations
    result = ctx.client.do_something(param1)

    # 3. Pattern match the result
    match result:
        case ClientSuccess(data=item):
            # Display success
            ctx.textual.success_text("Success!")
            ctx.textual.end_step("success")
            return Success("Done", metadata={"item_id": item.id})

        case ClientError(error_message=err):
            # Display error
            ctx.textual.error_text(f"Failed: {err}")
            ctx.textual.end_step("error")
            return Error(err)
```

#### 3. State Management
```python
# Read from context
value = ctx.get("key")
value = ctx.get("key", "default")

# Write to context (via metadata)
return Success("Done", metadata={
    "created_id": "123",
    "created_url": "https://...",
    "status": "active"
})
# These values become available in ctx.data for subsequent steps
```

#### 4. Step Lifecycle
```python
def my_step(ctx: WorkflowContext) -> WorkflowResult:
    # 1. ALWAYS begin
    ctx.textual.begin_step("My Step")

    # 2. Do work...

    # 3. ALWAYS end (with status)
    ctx.textual.end_step("success")  # or "error"

    # 4. ALWAYS return a result
    return Success("Message")  # or Error(), Skip(), Exit()
```

### What Steps MUST Do

✅ **Pattern match ALL ClientResult**:
```python
# ✅ REQUIRED
match result:
    case ClientSuccess(data=item):
        ...
    case ClientError(error_message=err):
        ...
```

✅ **Begin and end every step**:
```python
ctx.textual.begin_step("Name")
# ... work ...
ctx.textual.end_step("success" | "error")
```

✅ **Return WorkflowResult**:
```python
return Success("msg", metadata={...})
return Error("msg", code=...)
return Skip("msg", metadata={...})
return Exit("msg")
```

### What Steps MUST NOT Do

❌ **NO business logic**:
```python
# ❌ BAD - Complex logic in step
for item in items:
    if item.status == "pending" and item.priority > 3:
        filtered.append(item)

# ✅ GOOD - Call operation
filtered = filter_high_priority_pending(items)
```

❌ **NO try/except for ClientResult**:
```python
# ❌ BAD
try:
    result = ctx.client.get_item()
    item = result.data  # Assumes success
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
from ..clients.network import ResourceAPI

# ✅ GOOD
from ..operations import fetch_resources
# Use ctx.client instead
```

❌ **NO data transformation**:
```python
# ❌ BAD - Mapping in step
ui_items = [
    UIItem(
        id=item["id"],
        name=item["name"],
        status_icon=get_icon(item["status"])
    )
    for item in raw_items
]

# ✅ GOOD - Data comes pre-formatted
result = ctx.client.get_items()
match result:
    case ClientSuccess(data=ui_items):  # Already UIItem objects
        for item in ui_items:
            ctx.textual.text(f"{item.status_icon} {item.name}")
```

### Step Patterns

#### Pattern: Simple Fetch and Display
```python
def list_resources_step(ctx: WorkflowContext) -> WorkflowResult:
    """List all resources."""
    ctx.textual.begin_step("List Resources")

    result = ctx.client.list_resources()

    match result:
        case ClientSuccess(data=resources, message=msg):
            ctx.textual.success_text(msg)

            for resource in resources:
                ctx.textual.text(f"{resource.status_icon} {resource.name}")

            ctx.textual.end_step("success")
            return Success(msg, metadata={"count": len(resources)})

        case ClientError(error_message=err, error_code=code):
            ctx.textual.error_text(f"Failed: {err}")
            if code == "NOT_AUTHENTICATED":
                ctx.textual.text("Check your credentials")
            ctx.textual.end_step("error")
            return Error(err)
```

#### Pattern: User Selection
```python
def select_resource_step(ctx: WorkflowContext) -> WorkflowResult:
    """Select a resource from list."""
    ctx.textual.begin_step("Select Resource")

    # Fetch options
    result = ctx.client.list_resources()

    match result:
        case ClientSuccess(data=resources):
            if not resources:
                ctx.textual.info_text("No resources found")
                ctx.textual.end_step("success")
                return Skip("No resources")

            # Show selection
            options = [f"{r.status_icon} {r.name}" for r in resources]
            index = ctx.textual.ask_selection("Select resource:", options)

            if index is None:
                ctx.textual.end_step("success")
                return Success("Cancelled")

            selected = resources[index]

            ctx.textual.success_text(f"Selected: {selected.name}")
            ctx.textual.end_step("success")

            return Success(
                f"Resource selected: {selected.name}",
                metadata={"resource_id": selected.id, "resource_name": selected.name}
            )

        case ClientError(error_message=err):
            ctx.textual.error_text(f"Failed: {err}")
            ctx.textual.end_step("error")
            return Error(err)
```

#### Pattern: Complex Logic (Uses Operation)
```python
def process_resources_step(ctx: WorkflowContext) -> WorkflowResult:
    """Process resources with complex filtering."""
    ctx.textual.begin_step("Process Resources")

    try:
        # Operation handles complex logic
        processed = process_pending_resources(
            client=ctx.client,
            user_email=ctx.get("user_email"),
            priority_min=3
        )

        ctx.textual.success_text(f"Processed {len(processed)} resources")

        for resource in processed:
            ctx.textual.text(f"✓ {resource.name}")

        ctx.textual.end_step("success")
        return Success(f"Processed {len(processed)} resources")

    except OperationError as e:
        ctx.textual.error_text(str(e))
        ctx.textual.end_step("error")
        return Error(str(e))
```

---

## Layer 2: Operations (Business Logic)

**Purpose**: Pure, testable business logic independent of UI or data access.

### Core Responsibilities

#### 1. Complex Filtering and Searching
```python
def find_resource_by_criteria(
    client: ResourceClient,
    name: str = None,
    status: str = None,
    min_priority: int = None
) -> List[UIResource]:
    """
    Find resources matching criteria.

    Args:
        client: ResourceClient instance
        name: Filter by name (case-insensitive, partial match)
        status: Filter by exact status
        min_priority: Minimum priority level

    Returns:
        List of matching UIResource objects

    Raises:
        OperationError: If fetch fails
    """
    # Get all resources
    result = client.list_resources()

    match result:
        case ClientSuccess(data=resources):
            # Apply filters
            filtered = resources

            if name:
                filtered = [r for r in filtered if name.lower() in r.name.lower()]

            if status:
                filtered = [r for r in filtered if r.status == status]

            if min_priority is not None:
                filtered = [r for r in filtered if r.priority >= min_priority]

            return filtered

        case ClientError(error_message=err):
            raise OperationError(f"Failed to fetch resources: {err}")
```

#### 2. Multi-Step Business Processes
```python
def create_resource_with_validation(
    client: ResourceClient,
    name: str,
    resource_type: str,
    owner_email: str
) -> UIResource:
    """
    Create resource with full validation.

    Business rules:
    1. Validate name is unique
    2. Verify resource type exists
    3. Validate owner email format
    4. Create resource
    5. Auto-assign owner

    Args:
        client: ResourceClient instance
        name: Resource name (must be unique)
        resource_type: Type name (must exist)
        owner_email: Owner email (must be valid format)

    Returns:
        Created UIResource

    Raises:
        OperationError: If validation fails or creation fails
    """
    # Step 1: Check uniqueness
    existing_result = client.get_resource_by_name(name)
    match existing_result:
        case ClientSuccess(data=existing):
            raise OperationError(f"Resource '{name}' already exists")
        case ClientError(error_code="NOT_FOUND"):
            pass  # Good - doesn't exist
        case ClientError(error_message=err):
            raise OperationError(f"Failed to check uniqueness: {err}")

    # Step 2: Validate type
    types_result = client.list_resource_types()
    match types_result:
        case ClientSuccess(data=types):
            type_obj = next((t for t in types if t.name == resource_type), None)
            if not type_obj:
                available = [t.name for t in types]
                raise OperationError(
                    f"Type '{resource_type}' not found. Available: {', '.join(available)}"
                )
        case ClientError(error_message=err):
            raise OperationError(f"Failed to get types: {err}")

    # Step 3: Validate email
    if not validate_email_format(owner_email):
        raise OperationError(f"Invalid email format: {owner_email}")

    # Step 4: Create
    create_result = client.create_resource(
        name=name,
        type_id=type_obj.id
    )

    match create_result:
        case ClientSuccess(data=resource):
            # Step 5: Assign owner
            assign_result = client.assign_resource(resource.id, owner_email)

            match assign_result:
                case ClientSuccess():
                    # Refresh to get updated data
                    refresh_result = client.get_resource(resource.id)
                    match refresh_result:
                        case ClientSuccess(data=updated):
                            return updated
                        case ClientError(error_message=err):
                            # Resource created but fetch failed
                            raise OperationError(f"Created but failed to fetch: {err}")

                case ClientError(error_message=err):
                    # Resource created but assignment failed
                    raise OperationError(f"Created but failed to assign: {err}")

        case ClientError(error_message=err):
            raise OperationError(f"Failed to create resource: {err}")
```

#### 3. Data Aggregation and Analysis
```python
def calculate_resource_statistics(
    client: ResourceClient,
    project_id: str
) -> ResourceStatistics:
    """
    Calculate statistics for project resources.

    Args:
        client: ResourceClient instance
        project_id: Project ID

    Returns:
        ResourceStatistics object with counts and percentages

    Raises:
        OperationError: If fetch fails
    """
    # Get resources
    result = client.list_project_resources(project_id)

    match result:
        case ClientSuccess(data=resources):
            total = len(resources)

            if total == 0:
                return ResourceStatistics(
                    total=0,
                    active=0,
                    paused=0,
                    failed=0,
                    active_percent=0.0,
                    paused_percent=0.0,
                    failed_percent=0.0
                )

            # Count by status
            active = sum(1 for r in resources if r.status == "Active")
            paused = sum(1 for r in resources if r.status == "Paused")
            failed = sum(1 for r in resources if r.status == "Failed")

            return ResourceStatistics(
                total=total,
                active=active,
                paused=paused,
                failed=failed,
                active_percent=round(active / total * 100, 1),
                paused_percent=round(paused / total * 100, 1),
                failed_percent=round(failed / total * 100, 1)
            )

        case ClientError(error_message=err):
            raise OperationError(f"Failed to fetch resources: {err}")
```

#### 4. Validation and Business Rules
```python
def validate_resource_name(name: str) -> tuple[bool, str | None]:
    """
    Validate resource name against business rules.

    Rules:
    - 3-50 characters
    - Alphanumeric, hyphens, underscores only
    - Must start with letter
    - No consecutive hyphens

    Args:
        name: Resource name to validate

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if valid
        - error_message: None if valid, description if invalid
    """
    if not name or not name.strip():
        return False, "Name cannot be empty"

    name = name.strip()

    if len(name) < 3:
        return False, "Name must be at least 3 characters"

    if len(name) > 50:
        return False, "Name cannot exceed 50 characters"

    if not name[0].isalpha():
        return False, "Name must start with a letter"

    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', name):
        return False, "Name can only contain letters, numbers, hyphens, and underscores"

    if '--' in name:
        return False, "Name cannot contain consecutive hyphens"

    return True, None
```

### What Operations MUST Do

✅ **Return data types directly**:
```python
# ✅ CORRECT
def get_active_resources(client: Client) -> List[UIResource]:
    result = client.list_resources()
    match result:
        case ClientSuccess(data=resources):
            return [r for r in resources if r.status == "Active"]
        case ClientError(error_message=err):
            raise OperationError(err)
```

✅ **Raise exceptions on errors**:
```python
# ✅ CORRECT
if not found:
    raise OperationError("Resource not found")
```

✅ **Work with UI models**:
```python
# ✅ CORRECT
def process_resources(resources: List[UIResource]) -> List[UIResource]:
    return sorted(resources, key=lambda r: r.priority)
```

✅ **Be pure functions (no side effects)**:
```python
# ✅ CORRECT - No print, no file writes, no global state
def calculate_total(items: List[Item]) -> int:
    return sum(item.value for item in items)
```

### What Operations MUST NOT Do

❌ **NO returning ClientResult**:
```python
# ❌ BAD
def get_resources(client) -> ClientResult[List[UIResource]]:
    return client.list_resources()  # Just wrapping

# ✅ GOOD
def get_resources(client) -> List[UIResource]:
    result = client.list_resources()
    match result:
        case ClientSuccess(data=resources):
            return resources
        case ClientError(error_message=err):
            raise OperationError(err)
```

❌ **NO UI dependencies**:
```python
# ❌ BAD
def process_resources(ctx: WorkflowContext, resources):
    ctx.textual.text("Processing...")  # NO!

# ✅ GOOD
def process_resources(resources: List[UIResource]) -> List[UIResource]:
    # Pure logic only
    return [r for r in resources if r.status == "Active"]
```

❌ **NO importing Services or Network**:
```python
# ❌ BAD
from ..clients.services import ResourceService
from ..clients.network import ResourceAPI

# ✅ GOOD
from ..clients import ResourceClient  # Only the facade
```

❌ **NO side effects**:
```python
# ❌ BAD
def process_item(item: UIItem) -> UIItem:
    print(f"Processing {item.name}")  # Side effect!
    item.processed = True  # Mutation!
    return item

# ✅ GOOD
def process_item(item: UIItem) -> UIItem:
    # Return new object, no mutation
    return UIItem(
        id=item.id,
        name=item.name,
        processed=True
    )
```

---

## Layer 3: Client (Public Facade)

**Purpose**: Provide a clean, unified public API. Delegates ALL work to internal Services.

### Core Responsibilities

#### 1. Simple Delegation
```python
class ResourceClient:
    """
    Resource Client Facade.

    Public API for resource management. All methods delegate to internal services.
    """

    def __init__(self, base_url: str, api_token: str):
        # Internal (private) dependencies
        self._network = ResourceAPI(base_url, api_token)
        self._resource_service = ResourceService(self._network)
        self._project_service = ProjectService(self._network)

    # Public API - simple delegation
    def get_resource(self, resource_id: str) -> ClientResult[UIResource]:
        """Get resource by ID."""
        return self._resource_service.get_resource(resource_id)

    def list_resources(self, project_id: str = None) -> ClientResult[List[UIResource]]:
        """List all resources."""
        return self._resource_service.list_resources(project_id)

    def create_resource(
        self,
        name: str,
        type_id: str,
        project_id: str = None
    ) -> ClientResult[UIResource]:
        """Create new resource."""
        return self._resource_service.create_resource(name, type_id, project_id)

    def update_resource(
        self,
        resource_id: str,
        name: str = None,
        status: str = None
    ) -> ClientResult[UIResource]:
        """Update resource."""
        return self._resource_service.update_resource(resource_id, name, status)

    def delete_resource(self, resource_id: str) -> ClientResult[None]:
        """Delete resource."""
        return self._resource_service.delete_resource(resource_id)

    # Projects
    def list_projects(self) -> ClientResult[List[UIProject]]:
        """List all projects."""
        return self._project_service.list_projects()

    def get_project(self, project_id: str) -> ClientResult[UIProject]:
        """Get project by ID."""
        return self._project_service.get_project(project_id)
```

#### 2. Parameter Validation (Optional, Basic Only)
```python
def get_resource(self, resource_id: str) -> ClientResult[UIResource]:
    """Get resource by ID."""
    # Basic validation - only check for None/empty
    if not resource_id or not resource_id.strip():
        return ClientError(
            error_message="Resource ID is required",
            error_code="MISSING_PARAMETER"
        )

    return self._resource_service.get_resource(resource_id)
```

#### 3. Default Values (Optional)
```python
class ResourceClient:
    def __init__(
        self,
        base_url: str,
        api_token: str,
        default_project_id: str = None
    ):
        self._network = ResourceAPI(base_url, api_token)
        self._resource_service = ResourceService(self._network)
        self.default_project_id = default_project_id

    def list_resources(self, project_id: str = None) -> ClientResult[List[UIResource]]:
        """List resources for project."""
        # Use default if not provided
        pid = project_id or self.default_project_id

        if not pid:
            return ClientError(
                error_message="Project ID not provided",
                error_code="MISSING_PROJECT_ID"
            )

        return self._resource_service.list_resources(pid)
```

### What Client MUST Do

✅ **Return ClientResult[UIModel]**:
```python
# ✅ CORRECT
def get_resource(...) -> ClientResult[UIResource]:
    return self._resource_service.get_resource(...)
```

✅ **Delegate to Services**:
```python
# ✅ CORRECT - Thin delegation
def list_resources(...) -> ClientResult[List[UIResource]]:
    return self._resource_service.list_resources(...)
```

✅ **Validate basic parameters (optional)**:
```python
# ✅ CORRECT - Basic None checks
if not resource_id:
    return ClientError(error_message="ID required", error_code="MISSING_PARAM")
```

### What Client MUST NOT Do

❌ **NO business logic**:
```python
# ❌ BAD - Searching in Client
def get_resource_by_name(self, name: str) -> ClientResult[UIResource]:
    all_resources = self._resource_service.list_resources()

    match all_resources:
        case ClientSuccess(data=resources):
            # ❌ Searching here is business logic
            found = next((r for r in resources if r.name == name), None)
            if found:
                return ClientSuccess(data=found)
            return ClientError(error_message="Not found")

# ✅ GOOD - Let Service handle it
def get_resource_by_name(self, name: str) -> ClientResult[UIResource]:
    return self._resource_service.get_resource_by_name(name)
```

❌ **NO mapping/transformation**:
```python
# ❌ BAD - Mapping in Client
def get_resources(self) -> ClientResult[List[UIResource]]:
    result = self._resource_service.get_resources()

    match result:
        case ClientSuccess(data=resources):
            # ❌ Transforming data here
            sorted_resources = sorted(resources, key=lambda r: r.name)
            return ClientSuccess(data=sorted_resources)

# ✅ GOOD - Return as-is or use Operation
def get_resources(self) -> ClientResult[List[UIResource]]:
    return self._resource_service.get_resources()  # Service returns sorted
```

❌ **NO HTTP calls**:
```python
# ❌ BAD - HTTP in Client
def get_resource(self, id: str) -> ClientResult[UIResource]:
    response = requests.get(f"{self.base_url}/resources/{id}")  # NO!

# ✅ GOOD - Delegate to Service
def get_resource(self, id: str) -> ClientResult[UIResource]:
    return self._resource_service.get_resource(id)
```

❌ **NO parsing**:
```python
# ❌ BAD - Parsing in Client
def get_resource(self, id: str) -> ClientResult[UIResource]:
    result = self._resource_service.get_resource_raw(id)
    resource = UIResource(**result)  # NO!

# ✅ GOOD - Service returns parsed
def get_resource(self, id: str) -> ClientResult[UIResource]:
    return self._resource_service.get_resource(id)  # Already UIResource
```

---

## Layer 4: Services (Data Access)

**Purpose**: Handle data fetching, parsing Network models, mapping to UI models, and wrapping in ClientResult.

### Core Responsibilities

#### 1. Network → NetworkModel → UIModel → Result
```python
class ResourceService:
    """Resource service (internal data access)."""

    def __init__(self, network: ResourceAPI):
        self.network = network

    def get_resource(self, resource_id: str) -> ClientResult[UIResource]:
        """
        Get resource by ID (internal).

        Process:
        1. Network call → raw JSON
        2. Parse to NetworkResource
        3. Map to UIResource
        4. Wrap in ClientResult

        Args:
            resource_id: Resource ID

        Returns:
            ClientSuccess with UIResource or ClientError
        """
        try:
            # 1. Network call (returns dict)
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

        except ResourceAPIError as e:
            # Determine error code
            error_code = "NOT_FOUND" if e.status_code == 404 else "API_ERROR"

            return ClientError(
                error_message=str(e),
                error_code=error_code
            )
```

#### 2. List Operations
```python
def list_resources(self, project_id: str) -> ClientResult[List[UIResource]]:
    """
    List all resources for project (internal).

    Args:
        project_id: Project ID

    Returns:
        ClientSuccess with list of UIResource or ClientError
    """
    try:
        # Network call
        data = self.network.make_request("GET", f"projects/{project_id}/resources")

        # Parse list of network models
        network_resources = [NetworkResource(**item) for item in data]

        # Map to UI models
        ui_resources = [from_network_resource(nr) for nr in network_resources]

        return ClientSuccess(
            data=ui_resources,
            message=f"Found {len(ui_resources)} resources"
        )

    except ResourceAPIError as e:
        return ClientError(
            error_message=str(e),
            error_code="API_ERROR"
        )
```

#### 3. Create/Update Operations
```python
def create_resource(
    self,
    name: str,
    type_id: str,
    project_id: str
) -> ClientResult[UIResource]:
    """
    Create resource (internal).

    Args:
        name: Resource name
        type_id: Resource type ID
        project_id: Project ID

    Returns:
        ClientSuccess with created UIResource or ClientError
    """
    try:
        # Build payload
        payload = {
            "name": name,
            "typeId": type_id,
            "projectId": project_id
        }

        # Network call
        data = self.network.make_request("POST", "resources", json=payload)

        # Parse and map
        network_resource = NetworkResource(**data)
        ui_resource = from_network_resource(network_resource)

        return ClientSuccess(
            data=ui_resource,
            message=f"Resource '{name}' created"
        )

    except ResourceAPIError as e:
        error_code = "CONFLICT" if e.status_code == 409 else "API_ERROR"
        return ClientError(
            error_message=str(e),
            error_code=error_code
        )
```

#### 4. Search with Business Logic (Advanced)
```python
def get_resource_by_name(self, name: str) -> ClientResult[UIResource]:
    """
    Get resource by name (internal).

    Business logic: Search all resources for exact match.

    Args:
        name: Resource name (case-sensitive)

    Returns:
        ClientSuccess with UIResource or ClientError with NOT_FOUND
    """
    try:
        # Get all resources (in real app, use API search endpoint)
        data = self.network.make_request("GET", "resources")

        # Parse to network models
        network_resources = [NetworkResource(**item) for item in data]

        # Search for match
        found = next(
            (nr for nr in network_resources if nr.name == name),
            None
        )

        if not found:
            return ClientError(
                error_message=f"Resource '{name}' not found",
                error_code="NOT_FOUND"
            )

        # Map to UI
        ui_resource = from_network_resource(found)

        return ClientSuccess(
            data=ui_resource,
            message=f"Resource '{name}' found"
        )

    except ResourceAPIError as e:
        return ClientError(
            error_message=str(e),
            error_code="API_ERROR"
        )
```

### What Services MUST Do

✅ **Return ClientResult[UIModel]**:
```python
# ✅ CORRECT
def get_resource(...) -> ClientResult[UIResource]:
    # ... process ...
    return ClientSuccess(data=ui_resource)
```

✅ **Parse Network models**:
```python
# ✅ CORRECT
data = self.network.make_request("GET", "resource/123")
network_resource = NetworkResource(**data)  # Parse to Network model
```

✅ **Map to UI models**:
```python
# ✅ CORRECT
ui_resource = from_network_resource(network_resource)  # Map to UI
```

✅ **Catch BASE exception class**:
```python
# ✅ CORRECT
try:
    ...
except ResourceAPIError as e:  # Base class - catches all API errors
    return ClientError(...)
```

✅ **Set appropriate error codes**:
```python
# ✅ CORRECT
except ResourceAPIError as e:
    if e.status_code == 404:
        error_code = "NOT_FOUND"
    elif e.status_code == 401:
        error_code = "NOT_AUTHENTICATED"
    elif e.status_code == 403:
        error_code = "FORBIDDEN"
    else:
        error_code = "API_ERROR"

    return ClientError(error_message=str(e), error_code=error_code)
```

### What Services MUST NOT Do

❌ **NO returning Network models**:
```python
# ❌ BAD
def get_resource(...) -> ClientResult[NetworkResource]:
    network_resource = NetworkResource(**data)
    return ClientSuccess(data=network_resource)  # NO!

# ✅ GOOD
def get_resource(...) -> ClientResult[UIResource]:
    network_resource = NetworkResource(**data)
    ui_resource = from_network_resource(network_resource)  # Map to UI
    return ClientSuccess(data=ui_resource)
```

❌ **NO catching specific exception subclasses**:
```python
# ❌ BAD - Only catches NotFoundError
try:
    ...
except ResourceNotFoundError as e:  # Misses other errors!
    return ClientError(...)

# ✅ GOOD - Catches all errors
try:
    ...
except ResourceAPIError as e:  # Base class
    return ClientError(...)
```

❌ **NO UI logic**:
```python
# ❌ BAD - Formatting for display in Service
def get_resource(...) -> ClientResult[dict]:
    data = self.network.make_request(...)
    return ClientSuccess(data={
        "display": f"📄 {data['name']} - {data['status']}"  # NO!
    })

# ✅ GOOD - Return structured UI model
def get_resource(...) -> ClientResult[UIResource]:
    data = self.network.make_request(...)
    network = NetworkResource(**data)
    ui = from_network_resource(network)  # Mapper handles formatting
    return ClientSuccess(data=ui)
```

---

## Layer 5: Network (HTTP/CLI)

**Purpose**: Pure communication with external systems. Returns raw data.

### Core Responsibilities

#### 1. HTTP Communication
```python
import requests
from typing import Dict, List, Any


class ResourceAPIError(Exception):
    """Exception for API errors."""
    def __init__(self, message: str, status_code: int = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ResourceAPI:
    """
    Resource API client.

    Low-level HTTP communication. Returns raw JSON.
    """

    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        })

    def make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any] | List[Any]:
        """
        Make HTTP request.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., "resources/123")
            **kwargs: Additional arguments for requests.request()

        Returns:
            Raw JSON response (dict or list)

        Raises:
            ResourceAPIError: On HTTP error
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()

            # Return JSON if content, empty dict otherwise
            return response.json() if response.content else {}

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if hasattr(e, 'response') else None
            raise ResourceAPIError(str(e), status_code=status_code)

        except requests.exceptions.RequestException as e:
            raise ResourceAPIError(f"Request failed: {str(e)}")
```

#### 2. CLI Communication
```python
import subprocess
from typing import List, Any


class GitCommandError(Exception):
    """Exception for git command errors."""
    def __init__(self, message: str, returncode: int = None):
        self.message = message
        self.returncode = returncode
        super().__init__(message)


class GitCLI:
    """
    Git CLI client.

    Low-level command execution. Returns raw output.
    """

    def run_command(
        self,
        args: List[str],
        cwd: str = None,
        timeout: int = 30
    ) -> str:
        """
        Run git command.

        Args:
            args: Command arguments (e.g., ["git", "status", "--short"])
            cwd: Working directory
            timeout: Timeout in seconds

        Returns:
            Command stdout as string

        Raises:
            GitCommandError: On command failure
        """
        try:
            result = subprocess.run(
                args,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=True
            )

            return result.stdout

        except subprocess.CalledProcessError as e:
            raise GitCommandError(
                f"Command failed: {' '.join(args)}\nError: {e.stderr}",
                returncode=e.returncode
            )

        except subprocess.TimeoutExpired:
            raise GitCommandError(
                f"Command timed out: {' '.join(args)}",
                returncode=-1
            )

        except FileNotFoundError:
            raise GitCommandError(
                f"Command not found: {args[0]}",
                returncode=-1
            )
```

### What Network MUST Do

✅ **Return raw data (dict/list/str)**:
```python
# ✅ CORRECT
def make_request(...) -> Dict[str, Any] | List[Any]:
    response = requests.get(...)
    return response.json()  # Raw JSON
```

✅ **Raise exceptions on errors**:
```python
# ✅ CORRECT
if response.status_code >= 400:
    raise ResourceAPIError("Request failed", status_code=response.status_code)
```

✅ **Handle timeouts and network errors**:
```python
# ✅ CORRECT
try:
    response = self.session.request(method, url, timeout=30)
except requests.exceptions.Timeout:
    raise ResourceAPIError("Request timed out")
except requests.exceptions.ConnectionError:
    raise ResourceAPIError("Connection failed")
```

### What Network MUST NOT Do

❌ **NO parsing to models**:
```python
# ❌ BAD - Parsing in Network layer
def make_request(...) -> NetworkResource:
    data = response.json()
    return NetworkResource(**data)  # NO!

# ✅ GOOD - Return raw
def make_request(...) -> Dict[str, Any]:
    return response.json()
```

❌ **NO business logic**:
```python
# ❌ BAD - Filtering in Network layer
def make_request(...) -> List[Dict]:
    data = response.json()
    return [item for item in data if item["status"] == "active"]  # NO!

# ✅ GOOD - Return all
def make_request(...) -> List[Dict]:
    return response.json()
```

❌ **NO mapping or transformation**:
```python
# ❌ BAD - Transforming in Network
def make_request(...) -> Dict:
    data = response.json()
    return {
        "id": data["resourceId"],  # Renaming fields
        "name": data["resourceName"].upper()  # Transforming
    }

# ✅ GOOD - Return as-is
def make_request(...) -> Dict:
    return response.json()
```

---

## Data Flow Examples

### Example 1: Simple Fetch

```
User Request: "Show me resource ABC-123"

┌─────────────────┐
│  Step           │  ctx.textual.begin_step("Get Resource")
│                 │  result = ctx.client.get_resource("ABC-123")
│                 │  match result:
│                 │    case ClientSuccess(data=resource):
│                 │      ctx.textual.text(f"{resource.name}")
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Client         │  def get_resource(id) -> ClientResult[UIResource]:
│  (Facade)       │    return self._resource_service.get_resource(id)
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Service        │  1. data = self.network.make_request("GET", "resources/ABC-123")
│  (Data Access)  │  2. network = NetworkResource(**data)
│                 │  3. ui = from_network_resource(network)
│                 │  4. return ClientSuccess(data=ui)
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Network        │  response = requests.get("https://api.../resources/ABC-123")
│  (HTTP)         │  return response.json()
└─────────────────┘

Returns: {"id": "ABC-123", "name": "Resource Name", "status": "active", ...}
```

### Example 2: Complex Operation

```
User Request: "Find high-priority pending resources for user@example.com"

┌─────────────────┐
│  Step           │  try:
│                 │    resources = find_user_pending_resources(
│                 │      client=ctx.client,
│                 │      user_email="user@example.com",
│                 │      min_priority=3
│                 │    )
│                 │    for r in resources:
│                 │      ctx.textual.text(r.name)
│                 │  except OperationError as e:
│                 │    ctx.textual.error_text(str(e))
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Operation      │  result = client.list_user_resources(user_email)
│  (Business      │  match result:
│   Logic)        │    case ClientSuccess(data=resources):
│                 │      filtered = [r for r in resources
│                 │                   if r.status == "Pending"
│                 │                   and r.priority >= min_priority]
│                 │      return sorted(filtered, key=lambda x: x.priority, reverse=True)
│                 │    case ClientError(error_message=err):
│                 │      raise OperationError(err)
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Client         │  def list_user_resources(email) -> ClientResult[List[UIResource]]:
│  (Facade)       │    return self._resource_service.list_user_resources(email)
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Service        │  data = self.network.make_request("GET", f"users/{email}/resources")
│  (Data Access)  │  network_resources = [NetworkResource(**item) for item in data]
│                 │  ui_resources = [from_network_resource(nr) for nr in network_resources]
│                 │  return ClientSuccess(data=ui_resources)
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Network        │  response = requests.get("https://api.../users/user@example.com/resources")
│  (HTTP)         │  return response.json()
└─────────────────┘

Returns: [{"id": "1", "status": "pending", "priority": 5, ...}, ...]
```

---

## Layer Interaction Rules

### Allowed Imports

| Layer | Can Import | Cannot Import |
|-------|-----------|---------------|
| Steps | `operations/`, Client facade | Services, Network |
| Operations | Client facade only | Services, Network, Steps |
| Client | Services, Network | Operations, Steps |
| Services | Network, Models | Client, Operations, Steps |
| Network | Standard libs (requests, subprocess) | Everything else |

### Data Types by Layer

| Layer | Returns | Works With |
|-------|---------|------------|
| Steps | `WorkflowResult` | `UIModel` |
| Operations | `UIModel` or raises | `UIModel` |
| Client | `ClientResult[UIModel]` | `UIModel` |
| Services | `ClientResult[UIModel]` | `NetworkModel` → `UIModel` |
| Network | `dict`/`list`/`str` | Raw data |

---

**Last Updated**: 2026-03-27
**Version**: 2.0
**Status**: Complete Reference
