# Quick Start Guide

Get started with the App Store Connect plugin in 5 minutes.

## Prerequisites

- Python 3.8+
- App Store Connect API Key (Team or Individual)
- Titan CLI installed

## 1. Installation

```bash
cd plugins/titan-plugin-appstore
pip install -e .
```

**Verify installation:**
```bash
python -c "from titan_plugin_appstore import AppStoreConnectClient; print('✅ Installed')"
```

## 2. Get API Credentials

### Option A: Team Key (Organizations)

1. Go to [App Store Connect](https://appstoreconnect.apple.com/)
2. Navigate to **Users and Access** → **Keys**
3. Create or select an API Key
4. Download the `.p8` private key file
5. Note the **Key ID** and **Issuer ID**

### Option B: Individual Key (Personal Accounts)

1. Same as Team Key steps 1-4
2. **Skip Issuer ID** (not needed for individual keys)

## 3. Configure Credentials

Create `.appstore_connect/credentials.json` in your project root:

### Team Key
```json
{
  "issuer_id": "123e4567-e89b-12d3-a456-426614174000",
  "key_id": "ABC123XYZ",
  "private_key_path": ".appstore_connect/AuthKey_ABC123XYZ.p8"
}
```

### Individual Key
```json
{
  "issuer_id": "",
  "key_id": "ABC123XYZ",
  "private_key_path": ".appstore_connect/AuthKey_ABC123XYZ.p8"
}
```

Copy your `.p8` file:
```bash
cp ~/Downloads/AuthKey_ABC123XYZ.p8 .appstore_connect/
```

## 4. Test Connection

```python
from titan_plugin_appstore import AppStoreConnectClient

# Initialize client
client = AppStoreConnectClient(
    key_id="ABC123XYZ",
    issuer_id="your-issuer-id",  # Or "" for Individual Keys
    private_key_path=".appstore_connect/AuthKey_ABC123XYZ.p8"
)

# Test connection
apps = client.list_apps()
print(f"✅ Found {len(apps)} apps:")
for app in apps:
    print(f"  - {app.display_name()}")
```

## 5. Use Workflows

### Create a new version

```bash
titan run workflows/create-app-version.yaml --version_string="1.2.3"
```

**Interactive workflow:**
1. Selects app from your account
2. Shows existing versions
3. Suggests next version number
4. Validates input
5. Creates version in App Store Connect

## 6. Programmatic Usage

### List Apps
```python
from titan_plugin_appstore import AppStoreConnectClient

client = AppStoreConnectClient.from_credentials_file(
    ".appstore_connect/credentials.json"
)

apps = client.list_apps()
for app in apps:
    print(app.display_name())
```

### List Versions
```python
app_id = "123456789"
versions = client.list_versions(app_id, platform="IOS")

for version in versions:
    print(f"{version.version_string} - {version.format_state()}")
```

### Create Version
```python
from titan_plugin_appstore.models.view import VersionCreationRequest

request = VersionCreationRequest(
    app_id="123456789",
    version_string="1.2.3",
    platform="IOS",
    release_type="MANUAL"
)

created = client.create_version(request)
print(f"✅ Created: {created.version_string}")
print(f"   ID: {created.id}")
print(f"   State: {created.format_state()}")
```

### Advanced: Version Suggestions
```python
from titan_plugin_appstore.operations import VersionOperations

ops = VersionOperations(client)

# Get latest version
latest = client.get_latest_version("123456789")
print(f"Latest: {latest.version_string}")

# Suggest next version
next_patch = ops.suggest_next_version("123456789", increment="patch")
next_minor = ops.suggest_next_version("123456789", increment="minor")
next_major = ops.suggest_next_version("123456789", increment="major")

print(f"Next patch: {next_patch}")  # 1.2.4
print(f"Next minor: {next_minor}")  # 1.3.0
print(f"Next major: {next_major}")  # 2.0.0
```

## Common Tasks

### Check if version exists
```python
exists = client.version_exists("123456789", "1.2.3", platform="IOS")
if exists:
    print("❌ Version already exists")
else:
    print("✅ Version available")
```

### Get version summary table
```python
ops = VersionOperations(client)
table = ops.get_versions_summary_table("123456789", limit=5)
for line in table:
    print(line)
```

Output:
```
Existing Versions:
------------------------------------------------------------
🟢 1.2.3     READY_FOR_SALE            (created 2026-03-09)
🔵 1.2.2     IN_REVIEW                 (created 2026-03-05)
⚪ 1.2.1     PREPARE_FOR_SUBMISSION    (created 2026-03-01)
```

## Troubleshooting

### "Authentication failed"
- Verify Key ID and Issuer ID are correct
- Check `.p8` file path is correct and file exists
- For Individual Keys, ensure `issuer_id` is `""` or `null`

### "Version already exists"
- Check existing versions: `client.list_versions(app_id)`
- Use a different version number
- Delete existing version if needed

### "Import errors"
```bash
# Reinstall plugin
pip uninstall titan-plugin-appstore
cd plugins/titan-plugin-appstore
pip install -e .
```

## Next Steps

- Read [README.md](./README.md) for full documentation
- See [STRUCTURE.md](./STRUCTURE.md) for architecture
- Check [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md) for migration
- Review [TEST_RESULTS.md](./TEST_RESULTS.md) for test coverage

## Support

- **Documentation**: See `docs/` folder
- **Examples**: Check `tests/` for usage examples
- **Issues**: GitHub issues
- **Questions**: Team Slack

---

**Ready to go!** 🚀

Start creating versions in App Store Connect with clean, type-safe Python code.
