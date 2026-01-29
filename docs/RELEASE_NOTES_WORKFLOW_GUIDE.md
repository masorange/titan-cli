# Release Notes Workflow - Implementation Guide

Complete guide to implement the automated release notes workflow in Ragnarok projects (iOS and Android).

---

## Summary

The workflow automates:

1. **Git branch management** - Creates/switches to `release-notes/{version}` branch from `develop`
2. **JIRA query** - Searches issues for fixVersion using centralized queries
3. **AI generation** - Creates multi-brand release notes in Spanish
4. **File creation** - Generates `.md` following project nomenclature
5. **iOS update** - Modifies `LatestPublishers.md` with version and user
6. **Automatic commit** - Commits changes with standard message

---

## Implementation by Project

### Step 1: Copy Workflow to Project

**For iOS:**
```bash
cd /path/to/ragnarok-ios
mkdir -p .titan/workflows
cp /path/to/titan-cli/examples/ragnarok-ios-release-notes-workflow.yaml \
   .titan/workflows/generate-release-notes.yaml
```

**For Android:**
```bash
cd /path/to/ragnarok-android
mkdir -p .titan/workflows
cp /path/to/titan-cli/examples/ragnarok-android-release-notes-workflow.yaml \
   .titan/workflows/generate-release-notes.yaml
```

---

### Step 2: Configure Project Paths

Edit `.titan/workflows/generate-release-notes.yaml` and update parameters:

```yaml
params:
  project_key: "ECAPP"
  platform: "iOS"  # or "Android"
  notes_directory: "docs/release-notes/ios"  # UPDATE with actual path
```

**How to find the correct path:**

```bash
# Search for release notes directories
find . -type d -name "*release*" -o -name "*ReleaseNotes*"

# Search for existing release notes .md files
find . -name "release-notes-*.md"
```

---

### Step 3: Configure LatestPublishers.md (iOS Only)

**Typical location:** `docs/LatestPublishers.md`

**Expected format:**
```markdown
# Latest Publishers

| Publisher | Latest Version |
|-----------|----------------|
| John Doe  | [4 - 26.4.0]   |
| Jane Smith| [3 - 26.3.0]   |
```

The workflow will automatically update the line for the user executing the command.

**Verify Git username:**
```bash
git config user.name
# Must match the name in LatestPublishers.md
```

---

## Workflow Usage

### Execution

```bash
cd /path/to/ragnarok-ios  # or ragnarok-android
titan workflow run generate-release-notes
```

Or from Claude Code:
```bash
/generate-release-notes
```

### Interactive Flow

1. **Select platform** → iOS or Android
2. **List versions** → Shows unreleased JIRA versions
3. **Select version** → Numbered menu (1, 2, 3...)
4. **Create/switch branch** → `release-notes/26.4.0`
5. **Search issues** → JIRA query with fixVersion
6. **Generate notes** → AI transforms summaries to Spanish
7. **Discover directory** → Searches or uses configured path
8. **Create file** → `release-notes-26.4.0.md`
9. **Update LatestPublishers** → iOS only
10. **Commit** → `docs: Add release notes for 26.4.0`

---

## Generated File Structure

### iOS

```
ragnarok-ios/
├── docs/
│   ├── release-notes/
│   │   └── ios/
│   │       └── release-notes-26.4.0.md  # New
│   └── LatestPublishers.md              # Updated
└── .titan/
    └── workflows/
        └── generate-release-notes.yaml
```

### Android

```
ragnarok-android/
├── docs/
│   └── release-notes/
│       └── android/
│           └── release-notes-26.4.0.md  # New
└── .titan/
    └── workflows/
        └── generate-release-notes.yaml
```

---

## Workflow Customization

### Change File Name Pattern

Edit `create_notes_file` step:

```yaml
- id: create_notes_file
  command: |
    # Change pattern here
    FILENAME="release-notes-${fix_version}.md"  # Current pattern
    # FILENAME="RN-${fix_version}.md"          # Alternative
    # FILENAME="v${fix_version}-notes.md"      # Alternative
```

### Change File Format

```yaml
- id: create_notes_file
  command: |
    cat > "$FILEPATH" << 'EOF'
# Release Notes ${fix_version} - iOS

**Date:** $(date +"%Y-%m-%d")
**Version:** ${fix_version}
**Build:** TBD

## Changes

${release_notes}

## Testing Notes

- Test on iOS 15+
- Verify brand-specific features

EOF
```

### Add Validations

```yaml
- id: validate_directory
  name: "Validate Directory Exists"
  command: |
    if [ ! -d "${notes_directory}" ]; then
      echo "ERROR: Directory ${notes_directory} does not exist"
      echo "Create it with: mkdir -p ${notes_directory}"
      exit 1
    fi
```

---

## Troubleshooting

### Error: "Git client not available"

**Solution:**
```bash
# Verify Git is installed
which git

# Verify Titan configuration
titan plugins list | grep git
```

### Error: "JIRA client not available"

**Solution:**
```bash
# Verify JIRA configuration
titan plugins list | grep jira

# Verify credentials
cat ~/.titan/config.toml | grep jira
```

### Error: "Release notes directory not found"

**Solution:**
1. Search for actual directory:
   ```bash
   find . -name "release-notes-*.md"
   ```

2. Update parameter in workflow:
   ```yaml
   params:
     notes_directory: "actual/path/found"
   ```

### Error: "LatestPublishers.md not found"

**For iOS** (required file):
1. Create file if it doesn't exist:
   ```bash
   mkdir -p docs
   cat > docs/LatestPublishers.md << 'EOF'
   # Latest Publishers

   | Publisher | Latest Version |
   |-----------|----------------|
   | $(git config user.name) | [0 - 0.0.0] |
   EOF
   ```

**For Android** (optional file):
- Workflow shows WARNING but continues

### Incorrect Branch

If workflow creates branch from wrong branch:

```bash
# Delete incorrect branch
git branch -D release-notes/26.4.0

# Switch to develop and update
git checkout develop
git pull

# Execute workflow again
```

---

## Output Example

### Generated File (release-notes-26.4.0.md)

```markdown
# Release Notes 26.4.0 - iOS

**Date:** 2026-01-19
**Version:** 26.4.0

*🟣 Yoigo*
- Bloqueado el acceso al recargador a usuarios pospago (ECAPP-12154)
- Añadida nueva sección de consentimientos (ECAPP-12058)

*🟡 MASMOVIL*
- Bloqueado el acceso al recargador a usuarios pospago (ECAPP-12154)
- Correcciones de textos (ECAPP-12215)

*🔴 Jazztel*
- Bloqueado el acceso al recargador a usuarios pospago (ECAPP-12154)
```

### Updated LatestPublishers.md

```markdown
# Latest Publishers

| Publisher | Latest Version |
|-----------|----------------|
| Roberto Pedraza | [4 - 26.4.0]   |  # Updated
| Jane Smith     | [3 - 26.3.0]   |
```

### Created Commit

```
commit abc1234567890def
Author: Roberto Pedraza <rpedraza@example.com>
Date:   Sun Jan 19 15:30:00 2026

    docs: Add release notes for 26.4.0

    - Created release-notes-26.4.0.md
    - Updated LatestPublishers.md (Week 4)
```

---

## CI/CD Integration

### GitHub Actions

```yaml
name: Generate Release Notes

on:
  workflow_dispatch:
    inputs:
      version:
        description: 'Fix Version (e.g., 26.4.0)'
        required: true

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Titan CLI
        run: |
          pip install titan-cli
          titan plugins install

      - name: Generate Release Notes
        run: |
          titan workflow run generate-release-notes
        env:
          JIRA_API_TOKEN: ${{ secrets.JIRA_API_TOKEN }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}

      - name: Create Pull Request
        uses: peter-evans/create-pull-request@v5
        with:
          branch: release-notes/${{ inputs.version }}
          title: "docs: Release notes for ${{ inputs.version }}"
```

---

## References

- [Workflow Examples](../examples/) - Complete workflow examples
- [JIRA Plugin](../plugins/titan-plugin-jira/) - JIRA plugin with steps
- [Git Plugin](../plugins/titan-plugin-git/) - Git plugin with steps
- [Saved Queries](../plugins/titan-plugin-jira/titan_plugin_jira/utils/saved_queries.py) - Centralized JQLs

---

## Implementation Checklist

- [ ] Workflow copied to `.titan/workflows/generate-release-notes.yaml`
- [ ] `notes_directory` parameter updated with correct path
- [ ] Release notes directory exists in project
- [ ] (iOS) `LatestPublishers.md` exists and has correct format
- [ ] (iOS) Git username matches LatestPublishers.md
- [ ] JIRA and Git plugins configured
- [ ] JIRA credentials available
- [ ] AI API Key configured (Claude or Gemini)
- [ ] Workflow tested with test version
- [ ] Commit generated correctly

---

**Last updated:** 2026-01-19
**Version:** 1.0.0
