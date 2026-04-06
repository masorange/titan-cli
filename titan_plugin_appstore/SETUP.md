# App Store Connect Plugin - Setup Guide

Complete guide to configure and use the App Store Connect plugin with Titan CLI.

## 📋 Prerequisites

1. **App Store Connect Access**
   - Apple Developer account with access to App Store Connect
   - Permission to manage apps (App Manager or Admin role)

2. **Titan CLI Installation**
   - Titan CLI v0.1.4 or higher
   - Git plugin enabled (required dependency)

3. **Python Environment**
   - Python 3.10+
   - Required packages (installed with plugin):
     - `requests >= 2.31.0`
     - `pydantic >= 2.0.0`
     - `PyJWT >= 2.8.0`
     - `cryptography >= 41.0.0`

## 🚀 Quick Start

### Step 1: Install the Plugin

```bash
# Install from the plugins directory
cd plugins/titan-plugin-appstore
pip install -e .

# Or with Poetry
poetry install
```

### Step 2: Generate App Store Connect API Credentials

1. **Go to App Store Connect API Keys**
   - Navigate to: https://appstoreconnect.apple.com/access/api
   - Click **"Keys"** tab under **"Integrations"**

2. **Create a New API Key**
   - Click the **"+"** button
   - Name: `Titan CLI` (or any name you prefer)
   - Access: Select **"App Manager"** (minimum required)
   - Click **"Generate"**

3. **Download and Save the Key**
   - **Download** the `.p8` file (you can ONLY do this once!)
   - **Copy** the **Key ID** (e.g., `ABC123XYZ4`)
   - **Copy** the **Issuer ID** (e.g., `12345678-1234-1234-1234-123456789012`)

4. **Store the Private Key Securely**
   ```bash
   # Create secure directory
   mkdir -p ~/.appstore

   # Move the downloaded key
   mv ~/Downloads/AuthKey_ABC123XYZ4.p8 ~/.appstore/

   # Set restrictive permissions
   chmod 600 ~/.appstore/AuthKey_ABC123XYZ4.p8
   ```

### Step 3: Find Your App IDs

#### Option A: Via App Store Connect Web

1. Go to https://appstoreconnect.apple.com/apps
2. Click on your app
3. Go to **"App Information"** in the left sidebar
4. Look for **"Apple ID"** (numeric, e.g., `1234567890`)

#### Option B: Via Bundle ID (easier)

You'll use your app's bundle ID (e.g., `com.example.myapp`) in the config.
The plugin will automatically look up the App ID for you.

### Step 4: Configure Titan

#### 4.1 Enable the Plugin

Add to your project's `.titan/config.toml`:

```toml
[plugins.appstore]
enabled = true
```

#### 4.2 Configure Your Apps

Add app configuration to `.titan/config.toml`:

```toml
[plugins.appstore.config]
default_app = "myapp"  # Default app to use

[plugins.appstore.config.apps.myapp]
app_id = "1234567890"
bundle_id = "com.example.myapp"
default_locale = "es-ES"
locales = ["es-ES", "ca", "en-US"]
```

**Multiple Apps Example:**

```toml
[plugins.appstore.config]
default_app = "jazztel"

[plugins.appstore.config.apps.jazztel]
app_id = "1234567890"
bundle_id = "com.orange.sp.jazztel"
default_locale = "es-ES"
locales = ["es-ES", "ca", "en-US"]

[plugins.appstore.config.apps.yoigo]
app_id = "0987654321"
bundle_id = "com.masmovil.yoigo"
default_locale = "es-ES"
locales = ["es-ES", "ca", "en-US"]
```

#### 4.3 Set Secrets

Store credentials securely using Titan's secrets manager:

```bash
# Set API Key ID
titan secrets set appstore_key_id "ABC123XYZ4"

# Set Issuer ID
titan secrets set appstore_issuer_id "12345678-1234-1234-1234-123456789012"

# Set path to private key
titan secrets set appstore_private_key_path "~/.appstore/AuthKey_ABC123XYZ4.p8"
```

**Verify secrets are set:**

```bash
titan secrets list
```

You should see:
```
appstore_key_id: ***
appstore_issuer_id: ***
appstore_private_key_path: ***
```

### Step 5: Verify Setup

Test that everything is configured correctly:

```bash
# Launch Titan TUI
titan

# Navigate to "Workflows" → "App Store" → "Create Version"
# The plugin should load without errors
```

## 📖 Configuration Reference

### App Configuration Schema

```toml
[plugins.appstore.config.apps.{app_name}]
app_id = "string"           # Required: App Store Connect App ID
bundle_id = "string"        # Required: iOS bundle identifier
default_locale = "string"   # Optional: Default locale (default: "es-ES")
locales = ["array"]         # Optional: Supported locales (default: ["es-ES", "ca", "en-US"])
```

### Supported Locales

The plugin supports all 37 App Store Connect locales:

**Common Locales:**
- `es-ES` - Spanish (Spain)
- `ca` - Catalan
- `en-US` - English (US)
- `en-GB` - English (UK)
- `fr-FR` - French (France)
- `de-DE` - German (Germany)
- `it` - Italian
- `pt-PT` - Portuguese (Portugal)
- `pt-BR` - Portuguese (Brazil)

**Full list:** See `config.example.toml` for complete list of 37 locales.

### Required Secrets

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `appstore_key_id` | API Key ID from App Store Connect | `ABC123XYZ4` |
| `appstore_issuer_id` | Issuer ID from App Store Connect | `12345678-...` |
| `appstore_private_key_path` | Path to .p8 private key file | `~/.appstore/AuthKey_ABC123XYZ4.p8` |

## 🎯 Using the Plugin

### Via Titan TUI

1. Launch Titan: `titan`
2. Navigate to **"Workflows"**
3. Select **"App Store"** → **"Create Version"**
4. Follow the interactive prompts:
   - Select app (or auto-selected if only one)
   - Enter version number (e.g., `1.2.3`)
   - AI generates release notes (or enter manually)
   - Version is created in App Store Connect
   - Release notes are updated for all locales

### Via Workflow Command (Future)

```bash
titan workflow run appstore:create-version --app jazztel --version 1.2.3
```

## 🧪 Testing the Plugin

### Run Plugin Tests

```bash
cd plugins/titan-plugin-appstore

# Run all tests
pytest

# Run only critical tests (JWT + API client)
pytest -m critical

# Run with coverage
pytest --cov=titan_plugin_appstore --cov-report=html
```

### Manual Testing Checklist

- [ ] Plugin loads without errors in Titan TUI
- [ ] Credentials are validated (green status in TUI)
- [ ] Apps are listed correctly
- [ ] Version number validation works
- [ ] AI generates release notes (if AI configured)
- [ ] Version is created in App Store Connect
- [ ] Release notes are updated for all locales
- [ ] Error messages are clear and helpful

## 🔧 Troubleshooting

### Plugin Won't Load

**Error:** `Plugin not found: appstore`

**Solution:**
1. Ensure plugin is installed: `pip list | grep titan-plugin-appstore`
2. Check it's registered in `pyproject.toml`:
   ```toml
   [tool.poetry.plugins."titan.plugins"]
   appstore = "titan_plugin_appstore.plugin:AppStorePlugin"
   ```
3. Restart Titan: `titan`

### Authentication Failed

**Error:** `Authentication failed. Please check your API credentials`

**Possible Causes:**
1. **Wrong Key ID or Issuer ID**
   - Verify in App Store Connect: https://appstoreconnect.apple.com/access/api
   - Re-set secrets: `titan secrets set appstore_key_id "CORRECT_ID"`

2. **Private Key File Not Found**
   - Check path: `ls -la ~/.appstore/AuthKey_*.p8`
   - Verify secret: `titan secrets get appstore_private_key_path`
   - Ensure file has correct permissions: `chmod 600 ~/.appstore/AuthKey_*.p8`

3. **Private Key Malformed**
   - Re-download from App Store Connect (if possible)
   - Ensure file wasn't corrupted during download

4. **API Key Revoked**
   - Check if key still exists in App Store Connect
   - Create a new key if necessary

### App Not Found

**Error:** `App not found with bundle ID: com.example.app`

**Solution:**
1. Verify bundle ID in App Store Connect
2. Ensure the API key has access to this app
3. Try using the App ID directly instead:
   ```toml
   app_id = "1234567890"  # Use numeric App ID
   ```

### Version Already Exists

**Error:** `Version 1.0.0 already exists for this app`

**Solution:**
This is expected if you've already created this version. Use a new version number.

### Release Notes Too Long

**Error:** `whatsNew exceeds maximum length of 4000 characters`

**Solution:**
The plugin automatically truncates to 4000 characters. If you see this error, it means the API rejected it despite truncation. Manually shorten your release notes.

### AI Not Generating Notes

**Warning:** `AI not configured. Release notes will be entered manually`

**Solution:**
This is normal if you haven't configured AI in Titan. You can:
1. Enter release notes manually when prompted
2. Configure AI provider in Titan's main config
3. The workflow will continue regardless

### Partial Locale Failure

**Warning:** `2 of 3 locales updated, 1 failed`

**Solution:**
This is a partial success. Check the error message for the failed locale:
- May be an invalid locale code
- Locale might not be enabled for your app in App Store Connect
- Remove the failing locale from your config

## 📝 Best Practices

### Security

1. **Never commit secrets**
   - Use Titan's secrets manager
   - Add `.p8` files to `.gitignore`

2. **Rotate API keys periodically**
   - Generate new keys every 6-12 months
   - Revoke old keys after rotation

3. **Use restrictive permissions**
   - Use "App Manager" role instead of "Admin" if possible
   - Limit key access to only necessary apps

### Workflow

1. **Use semantic versioning**
   - Follow `MAJOR.MINOR.PATCH` format (e.g., `1.2.3`)
   - Match iOS app version exactly

2. **Review AI-generated notes**
   - Always review AI-generated release notes
   - Edit if necessary before accepting

3. **Test on staging first**
   - Use a test app for initial setup
   - Verify workflow before using on production apps

4. **Keep locales in sync**
   - Ensure all configured locales are enabled in App Store Connect
   - Remove unused locales from config

### Performance

1. **Enable Git plugin**
   - Required for commit analysis
   - Improves AI release notes quality

2. **Use default_app**
   - Set `default_app` if you primarily work with one app
   - Saves selection step each time

3. **Limit locale list**
   - Only include locales you actively maintain
   - Reduces API calls and processing time

## 🆘 Getting Help

### Documentation

- **Plugin README**: `README.md` in this directory
- **Tests README**: `tests/README.md`
- **Config Example**: `config.example.toml`

### Support

- **GitHub Issues**: https://github.com/masmovil/titan-cli/issues
- **Internal Slack**: #titan-cli-support (if applicable)

### Useful Links

- **App Store Connect**: https://appstoreconnect.apple.com
- **API Documentation**: https://developer.apple.com/documentation/appstoreconnectapi
- **Titan CLI Docs**: [Your internal docs URL]

---

**Setup Guide Version:** 1.0.0
**Last Updated:** 2026-02-04
**Compatible with:** Titan CLI v0.1.4+
