# Titan Plugin: App Store Connect

Professional plugin for managing iOS apps and versions in Apple's App Store Connect.

## ✨ Features

- 🚀 **Version Management**: Create and manage app versions with smart YY.WW.0 versioning
- 📱 **Multi-App Support**: Select and manage multiple apps simultaneously
- 🏷️ **Brand Grouping**: Automatically groups apps by brand (Yoigo, Jazztel, Guuk, MasOrange)
- 🔐 **Secure Authentication**: JWT-based API authentication with App Store Connect
- ✅ **Smart Validation**: Version format validation and conflict detection
- 📅 **Week-Based Versioning**: Automatic version suggestions based on current year and ISO week
- 🎨 **Rich TUI**: Interactive terminal UI with checkboxes and visual feedback
- ⚡ **Interactive Workflows**: Setup wizard and version creation with guided steps

## 📦 Installation

### For Development (Recommended)

The plugin is installed in **editable mode** via symlink:

```bash
cd /path/to/titan-cli
poetry install
```

The plugin is automatically discovered from `ragnarok-ios/plugins/titan-plugin-appstore/` via symlink.

### Enable in Project

Add to your project's `.titan/config.toml`:

```toml
[plugins.appstore]
enabled = true
```

## 🔧 Configuration

### 1. Get API Credentials

1. Go to [App Store Connect](https://appstoreconnect.apple.com/)
2. Navigate to **Users and Access** → **Keys**
3. Create an API Key (or use existing)
4. Download the `.p8` private key file
5. Note the **Key ID** and **Issuer ID**

### 2. Run Setup Wizard

```bash
titan tui
# Select: Workflows → Setup App Store Connect
```

The wizard will guide you through:
- Entering Key ID
- Entering Issuer ID (optional for Individual Keys)
- Providing path to `.p8` file
- Verifying connection

Credentials are stored in `.appstore_connect/credentials.json`

### 3. Manual Configuration (Alternative)

Create `.appstore_connect/credentials.json`:

```json
{
  "issuer_id": "your-issuer-id-here",
  "key_id": "your-key-id-here",
  "private_key_path": ".appstore_connect/AuthKey_XXXXXXXXXX.p8"
}
```

**Note**: For Individual/Personal API Keys, omit `issuer_id` or set it to `""`.

## 🎯 Usage

### Create App Version Workflow

Launch Titan TUI and run the workflow:

```bash
cd /path/to/titan-cli
poetry run titan tui
# Select: Workflows → Create App Store Version
```

#### Workflow Steps:

1. **Select Apps** (Multi-selection)
   - Shows all apps from your App Store Connect account
   - All apps selected by default (use checkboxes)
   - Navigate: ↑/↓
   - Toggle: Space
   - Confirm: Click "Continue" button or press Enter
   - Cancel: Click "Cancel" button or press Escape

2. **View Versions by Brand**
   - Apps are automatically grouped by brand
   - Shows only the **latest version** for each brand
   - Displays version state and platform

3. **Enter Version Number**
   - See suggested version based on **YY.WW.0 format**
   - YY = Year (last 2 digits, e.g., 26 for 2026)
   - WW = ISO Week number (1-53)
   - Patch always starts at .0 for new releases
   - Example: If current is `26.10.1`, next is `26.11.0`

4. **Create Version**
   - Creates the version for all selected apps
   - Shows success confirmation with App Store Connect link

### Versioning Strategy

**Format**: `YY.WW.PATCH`

- **YY**: 2-digit year (26 = 2026, 27 = 2027)
- **WW**: ISO week number (current week of the year)
- **PATCH**: Always `.0` for new releases

**Examples**:
- Latest: `26.10.1` (2026, week 10, hotfix 1)
- Next: `26.11.0` (2026, week 11, new release)
- Hotfix: `26.11.1` (same week, patch increment)

**Logic**:
- New releases always increment the week and reset patch to `.0`
- Hotfixes (incrementing PATCH) handled in separate workflow
- Automatically suggests next week's version

### Brand Detection

Apps are automatically grouped by brand:

| Brand | Detection Pattern |
|-------|------------------|
| **Yoigo** | Name or bundle ID contains "yoigo" |
| **Jazztel** | Name or bundle ID contains "jazztel" |
| **Guuk** | Name or bundle ID contains "guuk" |
| **MasOrange** | Name or bundle ID contains "orange" or "masorange" |

When you select multiple apps from the same brand, versions are shown **once per brand**.

### Available Workflows

1. **Setup App Store Connect** (`setup-appstore-connect.yaml`)
   - Interactive wizard for initial configuration
   - Validates credentials and connection

2. **Create App Version** (`create-app-version.yaml`)
   - Full workflow for creating new versions
   - Multi-app support with brand grouping

## 🏗️ Architecture

```
titan_plugin_appstore/
├── models/
│   ├── network.py          # API DTOs (Apple's schema)
│   ├── view.py             # TUI-optimized models with brand detection
│   └── mappers.py          # Network ↔ View conversion
├── clients/
│   ├── network/
│   │   └── appstore_api.py # Low-level HTTP + JWT
│   ├── services/
│   │   ├── app_service.py  # App business logic
│   │   └── version_service.py # Version business logic
│   └── appstore_client.py  # High-level facade
├── operations/
│   └── version_operations.py # Complex workflows (YY.WW.0 logic)
├── steps/
│   ├── select_app_step.py       # Multi-select with checkboxes
│   ├── prompt_version_step.py   # Version input with brand grouping
│   ├── create_version_step.py   # Version creation
│   └── setup_wizard_step.py     # Interactive setup
├── credentials.py          # Credentials manager
└── exceptions.py           # Custom exceptions
```

### Design Principles

1. **Separation of Concerns**
   - Network models (DTOs) ≠ View models (TUI)
   - Mappers handle layer conversions

2. **Layered Architecture**
   - `network/` → HTTP + JWT
   - `services/` → Business logic
   - `operations/` → Complex workflows
   - `steps/` → TUI workflow steps

3. **Brand-Aware Operations**
   - Automatic brand detection from app metadata
   - Grouped version display
   - Multi-app version creation

## 🔌 API Reference

### AppStoreConnectClient

```python
from titan_plugin_appstore import AppStoreConnectClient

client = AppStoreConnectClient(
    key_id="ABC123XYZ",
    issuer_id="123e4567-e89b-12d3-a456-426614174000",  # Optional for Individual Keys
    private_key_path=".appstore_connect/AuthKey_ABC123XYZ.p8"
)

# List apps
apps = client.list_apps()
for app in apps:
    print(f"{app.name} - Brand: {app.get_brand()}")

# Get latest version
version = client.get_latest_version(app_id="123456789")

# Create version
from titan_plugin_appstore.models.view import VersionCreationRequest

request = VersionCreationRequest(
    app_id="123456789",
    version_string="26.11.0",  # YY.WW.PATCH format
    platform="IOS",
    release_type="MANUAL"
)
created = client.create_version(request)
```

### VersionOperations

```python
from titan_plugin_appstore.operations import VersionOperations

ops = VersionOperations(client)

# Smart version suggestion (YY.WW.0 logic)
suggested = ops.suggest_next_version(app_id="123456789")
# Returns: "26.11.0" if current week is 11

# Get version summary (only latest)
summary = ops.get_versions_summary_table(app_id="123456789", limit=1)
```

## 🧪 Testing

```bash
# Install dev dependencies
poetry install

# Run tests
pytest

# With coverage
pytest --cov=titan_plugin_appstore

# Run specific test
pytest tests/operations/test_version_operations.py -v
```

## 🐛 Troubleshooting

### Authentication Errors

- ✅ Verify Key ID and Issuer ID are correct
- ✅ Ensure `.p8` file path is correct and readable
- ✅ Check API key has not expired in App Store Connect
- ✅ For Individual Keys, set `issuer_id` to `""` or omit it

### "No apps selected" Error

- ✅ Make sure to click "Continue" button or press Enter
- ✅ At least one app must be checked in the selection list
- ✅ Restart TUI if buttons don't appear (`poetry run titan tui`)

### Version Already Exists

- ✅ Check existing versions in App Store Connect
- ✅ The plugin prevents duplicate versions
- ✅ Use a different version number or delete existing version

### API Rate Limits

- ✅ App Store Connect API has rate limits
- ✅ JWT tokens are cached (20 min expiry)
- ✅ Avoid excessive API calls in short periods

### Plugin Not Appearing in TUI

1. Verify symlink exists:
   ```bash
   ls -la /path/to/titan-cli/plugins/titan-plugin-appstore
   ```

2. Reinstall Titan CLI:
   ```bash
   cd /path/to/titan-cli
   poetry lock && poetry install
   ```

3. Check plugin is enabled in `.titan/config.toml`:
   ```toml
   [plugins.appstore]
   enabled = true
   ```

## 📝 Development Notes

### Version Numbering Rules

- **New releases**: Always use YY.WW.0 format (patch = 0)
- **Hotfixes**: Increment patch number (e.g., 26.11.0 → 26.11.1)
- **Week increments**: Always move to next week for new features
- **Year rollover**: When week > 53, increment year and reset to week 1

### Workflow Context

Steps communicate via `ctx.data`:

```python
def my_step(ctx: WorkflowContext) -> WorkflowResult:
    # Read params (set by workflow YAML)
    param = ctx.get("param_name", "default_value")

    # Write outputs (for next steps)
    ctx.data["output_key"] = value

    # Access Textual UI
    ctx.textual.text("Message")
    ctx.textual.ask_text("Question?", default="answer")
```

## 📄 License

MIT

## 🤝 Contributing

1. Follow existing architecture patterns
2. Add tests for new features
3. Update documentation
4. Use Black/Ruff for formatting
5. Test in TUI before committing

## 📚 References

- [App Store Connect API](https://developer.apple.com/documentation/appstoreconnectapi)
- [JWT Authentication](https://developer.apple.com/documentation/appstoreconnectapi/generating_tokens_for_api_requests)
- [Titan CLI Documentation](https://github.com/masorange/titan-cli)
