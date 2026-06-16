# PoEditor Plugin for Titan CLI

PoEditor integration plugin for Titan CLI with translation management capabilities.

## Features

- **List Projects**: Display all accessible PoEditor projects
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

### Configuration

Add to `.titan/config.toml` in your project:

```toml
[plugins.poeditor]
enabled = true
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

### Upload Terms

Upload terms and translations to a PoEditor project:

```bash
titan workflow run poeditor:upload-terms
```

**Note**: This workflow requires `terms_map` and `translations_by_language` to be set in the workflow context before running. These are typically set by previous steps in a custom workflow.

### Delete Term

Delete a term from a PoEditor project (with confirmation):

```bash
titan workflow run poeditor:delete-term
```

**Note**: This workflow requires `term_key` to be set in the workflow context before running. The step will ask for confirmation (type 'DELETE') before proceeding.

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

### `upload_terms_step`

Uploads terms and translations to a PoEditor project.

**Inputs**:
- `selected_project_id` (str): PoEditor project ID
- `terms_map` (dict[str, str]): Dict mapping term keys to source language values
- `translations_by_language` (dict[str, dict[str, str]]): Dict mapping language codes to translations
- `source_language` (str, optional): Source language code (default: "en")

**Outputs**:
- `terms_added` (int): Number of terms added
- `languages_updated` (int): Number of languages updated
- `uploaded_keys` (list[str]): List of uploaded term keys

### `delete_term_step`

Deletes a term from a PoEditor project (requires confirmation).

**Inputs**:
- `selected_project_id` (str): PoEditor project ID
- `term_key` (str): The term key to delete

**Outputs**:
- `deleted_term_key` (str): The term key that was deleted
- `deleted_count` (int): Number of terms deleted (should be 1)

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

### Create Terms with Translations

```python
result = client.create_terms_with_translations(
    project_id="123456",
    terms_map={"home_title": "Home", "settings_title": "Settings"},
    translations_by_language={
        "es": {"home_title": "Inicio", "settings_title": "Ajustes"},
        "fr": {"home_title": "Accueil", "settings_title": "Paramètres"}
    },
    source_language="en"
)
```

Returns: `ClientResult[TermsWithTranslationsResult]`

### Delete Term

```python
result = client.delete_term(
    project_id="123456",
    term_key="home_title"
)
```

Returns: `ClientResult[dict]` with deletion info

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
