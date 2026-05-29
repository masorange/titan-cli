# PoEditor Plugin for Titan CLI

PoEditor integration plugin for Titan CLI with translation management capabilities.

## Features

- **List Projects**: Display all accessible PoEditor projects
- **Import Translations**: Upload translation files to PoEditor projects
- **Type-Safe API**: All client methods return `ClientResult[T]` for explicit error handling
- **5-Layer Architecture**: Clean separation between network, services, client, operations, and steps

## Installation

### From PyPI (when published)

```bash
titan plugin install poeditor
```

### Development Mode

```bash
cd plugins/titan-plugin-poeditor
poetry install
cd ../..
make dev-install
```

## Configuration

### Global Configuration

Add to `~/.titan/config.toml`:

```toml
[plugins.poeditor]
enabled = true

[plugins.poeditor.config]
timeout = 30
```

### Project Configuration

Add to `.titan/config.toml` in your project:

```toml
[plugins.poeditor]
enabled = true

[plugins.poeditor.config]
default_project_id = "123456"  # Optional: default project to use
```

### API Token

The API token is stored securely in your system keychain. Configure it using the Titan CLI wizard:

```bash
titan configure --plugin poeditor
```

Or set it as an environment variable:

```bash
export POEDITOR_API_TOKEN="your-api-token"
```

## Available Workflows

### List Projects

Display all accessible PoEditor projects:

```bash
titan workflow run poeditor:list-projects
```

### Import Translations

Upload translation file to a project:

```bash
titan workflow run poeditor:import-translations --param project_id=123456 --param file_path=./translations/en.json --param language_code=en
```

Parameters:
- `project_id`: PoEditor project ID (optional - will prompt if not provided)
- `file_path`: Path to translation file (required)
- `language_code`: Language code (default: "en")
- `updating`: What to update - "terms", "terms_translations", or "translations" (default: "terms_translations")

## Workflow Steps

### `list_projects_step`

Lists all accessible PoEditor projects and displays them in a table.

**Outputs**:
- `poeditor_projects` (List[UIPoEditorProject]): All accessible projects

### `select_project_step`

Prompts user to select a project from a list.

**Inputs**:
- `poeditor_projects` (List[UIPoEditorProject]): Projects from previous step

**Outputs**:
- `selected_project_id` (str): Selected project ID
- `selected_project` (UIPoEditorProject): Selected project object

### `import_translations_step`

Uploads a translation file to a PoEditor project.

**Parameters**:
- `project_id` (str): PoEditor project ID
- `file_path` (str): Path to translation file
- `language_code` (str): Language code
- `updating` (str): What to update (default: "terms_translations")

**Outputs**:
- `upload_stats` (dict): Upload statistics (added, updated, deleted)

## Using the Client in Custom Steps

```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.core.result import ClientSuccess, ClientError

def my_custom_step(ctx: WorkflowContext) -> WorkflowResult:
    """Custom step using PoEditor client."""
    if not ctx.poeditor:
        return Error("PoEditor client not available")
    
    # List projects
    result = ctx.poeditor.list_projects()
    
    match result:
        case ClientSuccess(data=projects):
            # Success - work with projects
            for project in projects:
                print(f"Project: {project.name}")
            return Success(f"Found {len(projects)} projects")
        
        case ClientError(error_message=err, error_code=code):
            # Error - handle gracefully
            return Error(f"Failed: {err}")
```

## Client API

### List Projects

```python
result = client.list_projects()
```

Returns: `ClientResult[List[UIPoEditorProject]]`

### Get Project

```python
result = client.get_project(project_id="123456")
```

Returns: `ClientResult[UIPoEditorProject]`

### Upload File

```python
result = client.upload_file(
    project_id="123456",
    file_path="./translations/en.json",
    language_code="en",
    updating="terms_translations"
)
```

Returns: `ClientResult[dict]` with upload statistics

## Architecture

The plugin follows Titan CLI's 5-layer architecture:

```
Steps → Operations → Client → Services → Network
  ↓         ↓          ↓         ↓          ↓
 UI    Business    Public   Data Access   HTTP
       Logic       API
```

### Network Layer

- `PoEditorNetwork`: Pure HTTP/REST communication
- Returns raw JSON responses

### Services Layer

- `ProjectService`: Project operations (list, get)
- `UploadService`: File upload operations

### Client Layer

- `PoEditorClient`: Public facade
- Returns `ClientResult[T]` for type-safe error handling

### Operations Layer

- Pure helper functions for business logic
- `find_project_by_name()`, `calculate_overall_progress()`

### Steps Layer

- UI orchestration using `ctx.textual`
- Pattern match on `ClientResult` for error handling

## Models

### Network Models (API-Faithful)

- `NetworkPoEditorProject`: Faithful to API response structure
- `NetworkPoEditorLanguage`: Language data from API

### View Models (UI-Optimized)

- `UIPoEditorProject`: Pre-formatted for display with icons
- `UIPoEditorLanguage`: Ready for rendering

## Development

### Run Tests

```bash
cd plugins/titan-plugin-poeditor
poetry run pytest -v --cov
```

### Code Quality

The plugin follows best practices:
- Type hints throughout
- Pattern matching for error handling
- Structured logging
- Clean separation of concerns

## API Documentation

For detailed PoEditor API documentation, visit:
https://poeditor.com/docs/api

## Support

For issues or feature requests, please open an issue on the Titan CLI repository.

## License

Same as Titan CLI
