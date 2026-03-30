# Titan Builder Skill - Complete Examples

Real-world examples of using the Titan Builder skill to create plugins, workflows, and steps.

---

## Example 1: Create a Notion Plugin

### User Request
> "Create a Notion plugin for Titan CLI that can create pages and databases"

### Generated Structure

```
plugins/titan-plugin-notion/
├── pyproject.toml
├── README.md
├── titan_plugin_notion/
│   ├── __init__.py
│   ├── plugin.py
│   ├── models/
│   │   ├── network/
│   │   │   ├── __init__.py
│   │   │   ├── page.py          # NetworkPage
│   │   │   └── database.py      # NetworkDatabase
│   │   ├── view/
│   │   │   ├── __init__.py
│   │   │   └── view.py          # UIPage, UIDatabase
│   │   ├── mappers/
│   │   │   ├── __init__.py
│   │   │   ├── page_mapper.py
│   │   │   └── database_mapper.py
│   │   └── formatting.py
│   ├── clients/
│   │   ├── network/
│   │   │   ├── __init__.py
│   │   │   └── notion_api.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── page_service.py
│   │   │   └── database_service.py
│   │   └── notion_client.py
│   ├── operations/
│   │   ├── __init__.py
│   │   └── page_operations.py
│   ├── steps/
│   │   ├── __init__.py
│   │   ├── create_page_step.py
│   │   └── create_database_step.py
│   └── workflows/
│       └── create-page.yaml
└── tests/
    ├── conftest.py
    ├── services/
    │   ├── test_page_service.py
    │   └── test_database_service.py
    └── operations/
        └── test_page_operations.py
```

### Key Files

**models/network/page.py**:
```python
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class NetworkPage:
    """
    Network model for Notion Page (faithful to API response).

    Matches Notion API structure exactly.
    """
    id: str
    created_time: str
    last_edited_time: str
    archived: bool
    properties: Dict[str, Any]
    url: str
    parent: Dict[str, Any]
```

**models/view/view.py**:
```python
from dataclasses import dataclass


@dataclass
class UIPage:
    """
    UI model for Notion Page (optimized for display).

    Pre-formatted fields for terminal rendering.
    """
    id: str
    title: str
    status_icon: str           # 📄, 🗑️
    created_display: str       # "2 days ago"
    last_edited_display: str   # "5 minutes ago"
    url: str
    parent_name: str
```

**models/mappers/page_mapper.py**:
```python
from ..network import NetworkPage
from ..view import UIPage
from ..formatting import format_timestamp


def from_network_page(network: NetworkPage) -> UIPage:
    """Convert NetworkPage to UIPage."""
    # Extract title from properties
    title = "Untitled"
    if "title" in network.properties:
        title_prop = network.properties["title"]
        if isinstance(title_prop, list) and len(title_prop) > 0:
            title = title_prop[0].get("plain_text", "Untitled")

    # Status icon
    status_icon = "🗑️" if network.archived else "📄"

    # Parent name
    parent_name = "Workspace"
    if network.parent.get("type") == "database_id":
        parent_name = f"Database ({network.parent['database_id'][:8]}...)"

    return UIPage(
        id=network.id,
        title=title,
        status_icon=status_icon,
        created_display=format_timestamp(network.created_time),
        last_edited_display=format_timestamp(network.last_edited_time),
        url=network.url,
        parent_name=parent_name,
    )
```

**clients/network/notion_api.py**:
```python
import requests
from typing import Dict, List, Any


class NotionAPIError(Exception):
    """Exception for Notion API errors."""
    def __init__(self, message: str, status_code: int = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotionAPI:
    """Notion API client."""

    API_VERSION = "2022-06-28"

    def __init__(self, api_token: str):
        self.base_url = "https://api.notion.com/v1"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_token}",
            "Notion-Version": self.API_VERSION,
            "Content-Type": "application/json",
        })

    def make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any] | List[Any]:
        """Make HTTP request to Notion API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}

        except requests.exceptions.RequestException as e:
            status_code = e.response.status_code if hasattr(e, 'response') else None
            raise NotionAPIError(str(e), status_code=status_code)
```

**clients/services/page_service.py**:
```python
from typing import List
from titan_cli.core.result import ClientResult, ClientSuccess, ClientError
from ..network import NotionAPI, NotionAPIError
from ...models import NetworkPage, UIPage, from_network_page


class PageService:
    """Page service (internal)."""

    def __init__(self, network: NotionAPI):
        self.network = network

    def create_page(
        self,
        parent_id: str,
        title: str,
        properties: dict = None
    ) -> ClientResult[UIPage]:
        """Create a new page."""
        try:
            # Build request payload
            payload = {
                "parent": {"database_id": parent_id},
                "properties": properties or {
                    "title": {
                        "title": [{"text": {"content": title}}]
                    }
                }
            }

            # Network call
            data = self.network.make_request("POST", "pages", json=payload)

            # Parse → Map → Wrap
            network_page = NetworkPage(**data)
            ui_page = from_network_page(network_page)

            return ClientSuccess(
                data=ui_page,
                message=f"Page '{title}' created"
            )

        except NotionAPIError as e:
            error_code = "NOT_FOUND" if e.status_code == 404 else "API_ERROR"
            return ClientError(
                error_message=str(e),
                error_code=error_code
            )

    def get_page(self, page_id: str) -> ClientResult[UIPage]:
        """Get page by ID."""
        try:
            data = self.network.make_request("GET", f"pages/{page_id}")
            network_page = NetworkPage(**data)
            ui_page = from_network_page(network_page)

            return ClientSuccess(
                data=ui_page,
                message=f"Page retrieved"
            )

        except NotionAPIError as e:
            error_code = "NOT_FOUND" if e.status_code == 404 else "API_ERROR"
            return ClientError(error_message=str(e), error_code=error_code)
```

**clients/notion_client.py**:
```python
from typing import List
from titan_cli.core.result import ClientResult
from .services import PageService, DatabaseService
from .network import NotionAPI
from ..models import UIPage, UIDatabase


class NotionClient:
    """Notion Client Facade."""

    def __init__(self, api_token: str):
        self._network = NotionAPI(api_token)
        self._page_service = PageService(self._network)
        self._database_service = DatabaseService(self._network)

    def create_page(
        self,
        parent_id: str,
        title: str,
        properties: dict = None
    ) -> ClientResult[UIPage]:
        """Create a new page."""
        return self._page_service.create_page(parent_id, title, properties)

    def get_page(self, page_id: str) -> ClientResult[UIPage]:
        """Get page by ID."""
        return self._page_service.get_page(page_id)
```

**steps/create_page_step.py**:
```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.core.result import ClientSuccess, ClientError


def create_page_step(ctx: WorkflowContext) -> WorkflowResult:
    """Create a Notion page."""
    ctx.textual.begin_step("Create Notion Page")

    # Get parameters
    parent_id = ctx.get("parent_database_id")
    if not parent_id:
        ctx.textual.error_text("No parent database ID provided")
        ctx.textual.end_step("error")
        return Error("Missing parent_database_id")

    # Prompt for title
    title = ctx.textual.ask_text("Page title:")
    if not title:
        ctx.textual.end_step("success")
        return Success("Cancelled")

    # Create page
    result = ctx.notion.create_page(parent_id, title)

    match result:
        case ClientSuccess(data=page, message=msg):
            ctx.textual.success_text(msg)
            ctx.textual.text(f"{page.status_icon} {page.title}")
            ctx.textual.text(f"URL: {page.url}")
            ctx.textual.end_step("success")
            return Success(msg, metadata={"page_id": page.id, "url": page.url})

        case ClientError(error_message=err):
            ctx.textual.error_text(f"Failed to create page: {err}")
            ctx.textual.end_step("error")
            return Error(err)
```

**workflows/create-page.yaml**:
```yaml
name: "Create Notion Page"
description: "Create a new page in a Notion database"

params:
  parent_database_id: ""

steps:
  - id: create
    name: "Create Page"
    plugin: notion
    step: create_page_step
    params:
      parent_database_id: "${parent_database_id}"
```

**tests/services/test_page_service.py**:
```python
import pytest
from unittest.mock import Mock
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_notion.clients.services import PageService
from titan_plugin_notion.clients.network import NotionAPIError


@pytest.fixture
def mock_network():
    return Mock()


@pytest.fixture
def page_service(mock_network):
    return PageService(mock_network)


class TestCreatePage:
    def test_create_page_success(self, page_service, mock_network):
        """Should create page and return ClientSuccess."""
        mock_network.make_request.return_value = {
            "id": "page-123",
            "created_time": "2024-01-01T00:00:00Z",
            "last_edited_time": "2024-01-01T00:00:00Z",
            "archived": False,
            "properties": {
                "title": [{"plain_text": "Test Page"}]
            },
            "url": "https://notion.so/page-123",
            "parent": {"type": "database_id", "database_id": "db-456"}
        }

        result = page_service.create_page("db-456", "Test Page")

        assert isinstance(result, ClientSuccess)
        assert result.data.id == "page-123"
        assert result.data.title == "Test Page"
        assert result.data.status_icon == "📄"

    def test_create_page_not_found(self, page_service, mock_network):
        """Should return ClientError when database not found."""
        mock_network.make_request.side_effect = NotionAPIError(
            "Database not found",
            status_code=404
        )

        result = page_service.create_page("invalid", "Test")

        assert isinstance(result, ClientError)
        assert result.error_code == "NOT_FOUND"
```

---

## Example 2: Custom Deployment Workflow

### User Request
> "Create a deployment workflow that runs tests, builds Docker image, and deploys to Kubernetes"

### Generated Files

**.titan/workflows/deploy.yaml**:
```yaml
name: "Deploy to Kubernetes"
description: "Complete deployment pipeline with tests, build, and deploy"

hooks:
  - before_tests
  - after_tests
  - before_build
  - after_build
  - before_deploy
  - after_deploy

params:
  environment: "staging"
  docker_registry: "gcr.io/my-project"
  k8s_namespace: "default"
  run_tests: true
  skip_build: false

steps:
  # Pre-flight checks
  - id: validate_env
    name: "Validate Environment"
    plugin: project
    step: validate_environment
    params:
      environment: "${environment}"

  # Testing phase
  - hook: before_tests

  - id: run_tests
    name: "Run Tests"
    plugin: project
    step: run_tests
    on_error: fail
    params:
      skip: "${run_tests}"

  - hook: after_tests

  # Build phase
  - hook: before_build

  - id: build_docker
    name: "Build Docker Image"
    plugin: project
    step: build_docker_image
    on_error: fail
    params:
      registry: "${docker_registry}"
      skip: "${skip_build}"

  - hook: after_build

  # Deploy phase
  - hook: before_deploy

  - id: deploy_k8s
    name: "Deploy to Kubernetes"
    plugin: project
    step: deploy_to_kubernetes
    on_error: fail
    params:
      environment: "${environment}"
      namespace: "${k8s_namespace}"

  - hook: after_deploy

  # Verification
  - id: verify
    name: "Verify Deployment"
    plugin: project
    step: verify_deployment
    on_error: continue
    params:
      namespace: "${k8s_namespace}"

  - id: notify
    name: "Send Notification"
    plugin: project
    step: send_slack_notification
    on_error: continue
```

**.titan/steps/run_tests.py**:
```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip
import subprocess


def run_tests(ctx: WorkflowContext) -> WorkflowResult:
    """Run test suite."""
    ctx.textual.begin_step("Run Tests")

    # Check if should skip
    if ctx.get("skip", False):
        ctx.textual.info_text("Tests skipped (skip=true)")
        ctx.textual.end_step("success")
        return Skip("Tests skipped")

    ctx.textual.loading_text("Running pytest...")

    try:
        # Run pytest
        result = subprocess.run(
            ["pytest", "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            ctx.textual.success_text("All tests passed ✓")
            ctx.textual.text(result.stdout)
            ctx.textual.end_step("success")
            return Success("Tests passed")
        else:
            ctx.textual.error_text("Tests failed ✗")
            ctx.textual.text(result.stdout)
            ctx.textual.end_step("error")
            return Error("Tests failed", code=result.returncode)

    except subprocess.TimeoutExpired:
        ctx.textual.error_text("Tests timed out after 5 minutes")
        ctx.textual.end_step("error")
        return Error("Test timeout")

    except FileNotFoundError:
        ctx.textual.error_text("pytest not found. Install with: pip install pytest")
        ctx.textual.end_step("error")
        return Error("pytest not installed")
```

**.titan/steps/build_docker_image.py**:
```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip
import subprocess
import os


def build_docker_image(ctx: WorkflowContext) -> WorkflowResult:
    """Build Docker image."""
    ctx.textual.begin_step("Build Docker Image")

    if ctx.get("skip", False):
        ctx.textual.info_text("Build skipped")
        ctx.textual.end_step("success")
        return Skip("Build skipped")

    registry = ctx.get("registry", "localhost:5000")

    # Get version from git tag or commit
    try:
        version_result = subprocess.run(
            ["git", "describe", "--tags", "--always"],
            capture_output=True,
            text=True,
            check=True
        )
        version = version_result.stdout.strip()
    except subprocess.CalledProcessError:
        version = "latest"

    image_name = f"{registry}/my-app:{version}"

    ctx.textual.info_text(f"Building image: {image_name}")
    ctx.textual.loading_text("Running docker build...")

    try:
        # Build image
        build_result = subprocess.run(
            ["docker", "build", "-t", image_name, "."],
            capture_output=True,
            text=True,
            timeout=600
        )

        if build_result.returncode != 0:
            ctx.textual.error_text("Docker build failed")
            ctx.textual.text(build_result.stderr)
            ctx.textual.end_step("error")
            return Error("Build failed")

        ctx.textual.success_text(f"Image built: {image_name}")

        # Push image
        ctx.textual.loading_text("Pushing image to registry...")
        push_result = subprocess.run(
            ["docker", "push", image_name],
            capture_output=True,
            text=True,
            timeout=600
        )

        if push_result.returncode != 0:
            ctx.textual.error_text("Docker push failed")
            ctx.textual.text(push_result.stderr)
            ctx.textual.end_step("error")
            return Error("Push failed")

        ctx.textual.success_text(f"Image pushed to {registry}")
        ctx.textual.end_step("success")

        return Success(
            f"Built and pushed {image_name}",
            metadata={"image": image_name, "version": version}
        )

    except subprocess.TimeoutExpired:
        ctx.textual.error_text("Build timed out")
        ctx.textual.end_step("error")
        return Error("Build timeout")

    except FileNotFoundError:
        ctx.textual.error_text("Docker not found. Install Docker first.")
        ctx.textual.end_step("error")
        return Error("Docker not installed")
```

**.titan/steps/deploy_to_kubernetes.py**:
```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
import subprocess


def deploy_to_kubernetes(ctx: WorkflowContext) -> WorkflowResult:
    """Deploy to Kubernetes cluster."""
    ctx.textual.begin_step("Deploy to Kubernetes")

    environment = ctx.get("environment", "staging")
    namespace = ctx.get("namespace", "default")
    image = ctx.get("image")  # From previous step metadata

    if not image:
        ctx.textual.error_text("No image specified (missing from build step?)")
        ctx.textual.end_step("error")
        return Error("No image to deploy")

    ctx.textual.info_text(f"Deploying to {environment} ({namespace})")
    ctx.textual.text(f"Image: {image}")

    # Confirm deployment
    if environment == "production":
        confirm = ctx.textual.ask_confirm(
            f"Deploy {image} to PRODUCTION?",
            default=False
        )
        if not confirm:
            ctx.textual.info_text("Deployment cancelled")
            ctx.textual.end_step("success")
            return Success("Cancelled by user")

    ctx.textual.loading_text("Applying Kubernetes manifests...")

    try:
        # Update deployment with new image
        result = subprocess.run(
            [
                "kubectl", "set", "image",
                f"deployment/my-app",
                f"my-app={image}",
                f"-n", namespace
            ],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            ctx.textual.error_text("kubectl command failed")
            ctx.textual.text(result.stderr)
            ctx.textual.end_step("error")
            return Error("Deployment failed")

        ctx.textual.success_text("Deployment updated")

        # Wait for rollout
        ctx.textual.loading_text("Waiting for rollout to complete...")
        rollout_result = subprocess.run(
            [
                "kubectl", "rollout", "status",
                f"deployment/my-app",
                f"-n", namespace,
                "--timeout=5m"
            ],
            capture_output=True,
            text=True,
            timeout=360
        )

        if rollout_result.returncode == 0:
            ctx.textual.success_text("Deployment successful ✓")
            ctx.textual.end_step("success")
            return Success(
                f"Deployed to {environment}",
                metadata={"deployed_image": image, "namespace": namespace}
            )
        else:
            ctx.textual.error_text("Rollout failed or timed out")
            ctx.textual.text(rollout_result.stderr)
            ctx.textual.end_step("error")
            return Error("Rollout failed")

    except subprocess.TimeoutExpired:
        ctx.textual.error_text("Deployment timed out")
        ctx.textual.end_step("error")
        return Error("Timeout")

    except FileNotFoundError:
        ctx.textual.error_text("kubectl not found. Install kubectl first.")
        ctx.textual.end_step("error")
        return Error("kubectl not installed")
```

---

## Example 3: Extend Git Plugin Workflow

### User Request
> "Extend the commit-ai workflow to run Black formatter before committing"

### Generated Files

**.titan/workflows/commit-ai.yaml**:
```yaml
name: "Commit with AI and Formatting"
description: "Extended commit workflow with Black formatter"
extends: "plugin:git/commit-ai"

hooks:
  before_commit:
    - id: format_python
      name: "Format Python Files"
      plugin: project
      step: run_black_formatter
      on_error: continue
```

**.titan/steps/run_black_formatter.py**:
```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Skip, Error
import subprocess


def run_black_formatter(ctx: WorkflowContext) -> WorkflowResult:
    """Run Black formatter on staged Python files."""
    ctx.textual.begin_step("Format Python Files")

    # Get staged Python files
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            check=True
        )

        staged_files = result.stdout.strip().split('\n')
        python_files = [f for f in staged_files if f.endswith('.py')]

        if not python_files:
            ctx.textual.info_text("No Python files staged")
            ctx.textual.end_step("success")
            return Skip("No Python files to format")

        ctx.textual.info_text(f"Found {len(python_files)} Python file(s)")

        # Run Black
        ctx.textual.loading_text("Running Black formatter...")
        format_result = subprocess.run(
            ["black", "--check", *python_files],
            capture_output=True,
            text=True
        )

        if format_result.returncode == 0:
            ctx.textual.success_text("All files already formatted ✓")
            ctx.textual.end_step("success")
            return Success("Files formatted")

        # Files need formatting
        ctx.textual.warning_text("Some files need formatting")

        should_format = ctx.textual.ask_confirm(
            "Format files with Black now?",
            default=True
        )

        if not should_format:
            ctx.textual.info_text("Formatting skipped")
            ctx.textual.end_step("success")
            return Success("User skipped formatting")

        # Apply formatting
        apply_result = subprocess.run(
            ["black", *python_files],
            capture_output=True,
            text=True
        )

        if apply_result.returncode == 0:
            ctx.textual.success_text("Files formatted ✓")

            # Re-stage formatted files
            subprocess.run(["git", "add", *python_files], check=True)
            ctx.textual.info_text("Formatted files re-staged")

            ctx.textual.end_step("success")
            return Success("Files formatted and staged")
        else:
            ctx.textual.error_text("Black failed")
            ctx.textual.text(apply_result.stderr)
            ctx.textual.end_step("error")
            return Error("Formatting failed")

    except subprocess.CalledProcessError as e:
        ctx.textual.error_text(f"Git command failed: {e}")
        ctx.textual.end_step("error")
        return Error(str(e))

    except FileNotFoundError:
        ctx.textual.error_text("Black not found. Install with: pip install black")
        ctx.textual.end_step("error")
        return Error("Black not installed")
```

---

## Example 4: AWS Lambda Plugin (Simplified)

### User Request
> "Create a simplified AWS Lambda plugin that can deploy functions"

### Key Implementation Files

**clients/network/aws_lambda_api.py**:
```python
import boto3
from botocore.exceptions import ClientError as BotoClientError


class AWSLambdaError(Exception):
    """Exception for AWS Lambda errors."""
    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class AWSLambdaAPI:
    """AWS Lambda API client using boto3."""

    def __init__(self, region: str = "us-east-1"):
        self.client = boto3.client('lambda', region_name=region)

    def get_function(self, function_name: str) -> dict:
        """Get function configuration."""
        try:
            response = self.client.get_function(FunctionName=function_name)
            return response
        except BotoClientError as e:
            raise AWSLambdaError(str(e), error_code=e.response['Error']['Code'])

    def update_function_code(
        self,
        function_name: str,
        zip_file: bytes
    ) -> dict:
        """Update function code."""
        try:
            response = self.client.update_function_code(
                FunctionName=function_name,
                ZipFile=zip_file
            )
            return response
        except BotoClientError as e:
            raise AWSLambdaError(str(e), error_code=e.response['Error']['Code'])
```

**steps/deploy_lambda_step.py**:
```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.core.result import ClientSuccess, ClientError
import zipfile
import io
import os


def deploy_lambda_step(ctx: WorkflowContext) -> WorkflowResult:
    """Deploy Lambda function."""
    ctx.textual.begin_step("Deploy Lambda Function")

    function_name = ctx.get("function_name")
    source_dir = ctx.get("source_dir", "./lambda")

    if not function_name:
        ctx.textual.error_text("No function_name provided")
        ctx.textual.end_step("error")
        return Error("Missing function_name")

    # Create deployment package
    ctx.textual.loading_text("Creating deployment package...")

    try:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, source_dir)
                    zip_file.write(file_path, arcname)

        zip_buffer.seek(0)
        zip_bytes = zip_buffer.read()

        ctx.textual.info_text(f"Package size: {len(zip_bytes) / 1024:.1f} KB")

        # Deploy
        ctx.textual.loading_text(f"Deploying to {function_name}...")

        result = ctx.aws_lambda.update_function_code(function_name, zip_bytes)

        match result:
            case ClientSuccess(data=function, message=msg):
                ctx.textual.success_text(msg)
                ctx.textual.text(f"Function: {function.function_name}")
                ctx.textual.text(f"Runtime: {function.runtime}")
                ctx.textual.text(f"Version: {function.version}")
                ctx.textual.end_step("success")
                return Success(msg, metadata={"function_arn": function.arn})

            case ClientError(error_message=err):
                ctx.textual.error_text(f"Deployment failed: {err}")
                ctx.textual.end_step("error")
                return Error(err)

    except FileNotFoundError:
        ctx.textual.error_text(f"Source directory not found: {source_dir}")
        ctx.textual.end_step("error")
        return Error(f"Directory not found: {source_dir}")

    except Exception as e:
        ctx.textual.error_text(f"Unexpected error: {e}")
        ctx.textual.end_step("error")
        return Error(str(e))
```

---

## Summary

These examples demonstrate:

1. **Complete Plugin Structure**: Network → Services → Client → Operations → Steps
2. **Pattern Matching**: All `ClientResult` handled with match/case
3. **Error Handling**: Proper exception catching and error codes
4. **UI Separation**: Business logic in operations/services, UI in steps
5. **Testing**: Complete test suites with mocks
6. **Workflows**: Declarative YAML with hooks and parameters
7. **Real-World Use Cases**: Notion, Docker, Kubernetes, AWS Lambda

All examples follow the official 5-layer architecture and best practices from the Titan Builder skill.
