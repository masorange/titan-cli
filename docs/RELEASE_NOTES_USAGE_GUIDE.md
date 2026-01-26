# Release Notes Workflow - Step-by-Step Usage Guide

Practical guide for using the release notes workflow from Titan CLI.

---

## Initial Setup (Once per project)

### Step 1: Navigate to project

```bash
# For iOS
cd /Users/rpedraza/Documents/MasMovil/ragnarok-ios

# Or for Android
cd /Users/rpedraza/Documents/MasMovil/ragnarok-android
```

### Step 2: Copy the workflow

**Option A: Copy manually**

```bash
# Create directory if it doesn't exist
mkdir -p .titan/workflows

# Copy corresponding template
# For iOS:
cp /Users/rpedraza/Documents/MasMovil/titan-cli/examples/ragnarok-ios-release-notes-workflow.yaml \
   .titan/workflows/generate-release-notes.yaml

# For Android:
cp /Users/rpedraza/Documents/MasMovil/titan-cli/examples/ragnarok-android-release-notes-workflow.yaml \
   .titan/workflows/generate-release-notes.yaml
```

**Option B: From Titan CLI**

```bash
# List available workflows in titan-cli
titan workflow list

# Copy to local project
titan workflow copy generate-release-notes-ios .titan/workflows/generate-release-notes.yaml
```

### Step 3: Find the release notes directory

```bash
# Search for current release notes files
find . -name "release-notes-*.md" -o -name "ReleaseNotes*.md"

# Example output:
# ./docs/release-notes/ios/release-notes-26.3.0.md
# ./docs/release-notes/ios/release-notes-26.2.0.md
```

**Take note of the directory path** (example: `docs/release-notes/ios`)

### Step 4: Configure the workflow

```bash
# Edit the workflow
vim .titan/workflows/generate-release-notes.yaml

# Or with VS Code
code .titan/workflows/generate-release-notes.yaml
```

**Update these parameters:**

```yaml
params:
  project_key: "ECAPP"           # Already configured
  platform: "iOS"                # Already configured (or "Android")
  notes_directory: "docs/release-notes/ios"  # CHANGE HERE
```

**Replace `docs/release-notes/ios` with the path you found in Step 3.**

### Step 5: Verify LatestPublishers.md (iOS Only)

```bash
# Find the file
find . -name "LatestPublishers.md"

# Example:
# ./docs/LatestPublishers.md

# View content
cat docs/LatestPublishers.md
```

**Must have this format:**

```markdown
# Latest Publishers

| Publisher | Latest Version |
|-----------|----------------|
| Roberto Pedraza | [3 - 26.3.0]  |
| Other User      | [2 - 26.2.0]  |
```

**Verify your Git name matches:**

```bash
git config user.name
# Must appear in the LatestPublishers.md table
```

If the file doesn't exist, create it:

```bash
cat > docs/LatestPublishers.md << 'EOF'
# Latest Publishers

| Publisher | Latest Version |
|-----------|----------------|
| $(git config user.name) | [0 - 0.0.0] |
EOF
```

---

## Setup Verification

```bash
# 1. Verify the workflow exists
ls -la .titan/workflows/generate-release-notes.yaml

# 2. Verify Titan detects it
titan workflow list
# Should display "generate-release-notes" in the list

# 3. Verify required plugins
titan plugins list
# Should show: jira, git (both with checkmark)

# 4. Verify JIRA configuration
cat ~/.titan/config.toml | grep -A 5 "\[jira\]"

# 5. Verify AI API key
cat ~/.titan/config.toml | grep -A 3 "\[ai\]"
```

---

## Workflow Usage

### Option 1: From Titan CLI

```bash
# Navigate to project
cd /Users/rpedraza/Documents/MasMovil/ragnarok-ios

# Execute workflow
titan workflow run generate-release-notes
```

### Option 2: From Claude Code (Recommended)

```bash
# Navigate to project
cd /Users/rpedraza/Documents/MasMovil/ragnarok-ios

# Execute skill
/generate-release-notes
```

---

## Complete Interactive Flow

### 1. Platform Selection

```
┌─ Select Platform ──────────────────────────────────┐
│                                                     │
│ Select platform (iOS or Android)                   │
│                                                     │
│ 1. iOS                                              │
│ 2. Android                                          │
│                                                     │
│ Select option [1-2]:                                │
└─────────────────────────────────────────────────────┘
```

**Action:** Type `1` (for iOS) or `2` (for Android) and press Enter

---

### 2. Version Listing

```
┌─ List Available Versions ──────────────────────────┐
│                                                     │
│ Found 5 unreleased versions                        │
│                                                     │
│ Unreleased Versions:                               │
│   • 26.5.0 - Week 5 2026                           │
│   • 26.4.1 - Hotfix for 26.4.0                     │
│   • 26.4.0 - Week 4 2026                           │
│   • 26.3.1 - Hotfix for 26.3.0                     │
│   • 26.3.0 - Week 3 2026                           │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**The workflow automatically searches for unreleased versions in JIRA.**

---

### 3. Version Selection

```
┌─ Select Version ───────────────────────────────────┐
│                                                     │
│ Select from 5 unreleased versions                  │
│                                                     │
│ Select fixVersion                                  │
│                                                     │
│ 1. 26.5.0                                           │
│ 2. 26.4.1                                           │
│ 3. 26.4.0                                           │
│ 4. 26.3.1                                           │
│ 5. 26.3.0                                           │
│                                                     │
│ Select option [1-5]:                                │
└─────────────────────────────────────────────────────┘
```

**Action:** Type the number of the version you want (example: `3` for 26.4.0)

---

### 4. Git Branch Management

```
┌─ Ensure Release Notes Branch ─────────────────────┐
│                                                     │
│ Target branch: release-notes/26.4.0                │
│                                                     │
│ Current branch: develop                            │
│                                                     │
│ Creating new release notes branch from develop...  │
│   1. Checking out develop...                       │
│   2. Pulling latest changes...                     │
│   3. Creating branch release-notes/26.4.0...       │
│   4. Checking out release-notes/26.4.0...          │
│                                                     │
│ ✓ Created and switched to release-notes/26.4.0    │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Automatic - no action required.**

**If already on the correct branch:**

```
┌─ Ensure Release Notes Branch ─────────────────────┐
│                                                     │
│ Target branch: release-notes/26.4.0                │
│                                                     │
│ Current branch: release-notes/26.4.0               │
│                                                     │
│ ✓ Already on branch release-notes/26.4.0          │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

### 5. JIRA Issue Search

```
┌─ Search JIRA Issues ───────────────────────────────┐
│                                                     │
│ Executing JQL Query                                │
│   fixVersion = "26.4.0" AND project = ECAPP        │
│   Max results: 100                                 │
│                                                     │
│ Searching JIRA...                                  │
│                                                     │
│ ✓ Found 15 issues                                  │
│                                                     │
│ Issues Retrieved:                                  │
│   • ECAPP-12154: Block postpaid recharger          │
│   • ECAPP-12058: New consents section              │
│   • ECAPP-12215: Text corrections                 │
│   ... and 12 more                                  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Automatic - no action required.**

---

### 6. AI Release Notes Generation

```
┌─ Generate Release Notes ──────────────────────────┐
│                                                     │
│ Processing 15 issues...                            │
│                                                     │
│ Grouping by brands...                              │
│   • Yoigo: 8 issues                                │
│   • MASMOVIL: 10 issues                            │
│   • Jazztel: 8 issues                              │
│   • Lycamobile: 2 issues                           │
│                                                     │
│ Generating AI descriptions...                      │
│   ✓ ECAPP-12154: Bloqueado el acceso al recarga... │
│   ✓ ECAPP-12058: Añadida nueva sección de cons... │
│   ✓ ECAPP-12215: Correcciones de textos           │
│   ...                                              │
│                                                     │
│ ✓ Release notes generated (1,234 characters)       │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Automatic - AI transforms summaries to Spanish.**

---

### 7. File Creation

```
┌─ Create Release Notes File ───────────────────────┐
│                                                     │
│ Using directory: docs/release-notes/ios           │
│                                                     │
│ Creating file: release-notes-26.4.0.md             │
│                                                     │
│ ✓ Created: docs/release-notes/ios/release-notes-26.4.0.md │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Automatic - creates the .md file in configured directory.**

---

### 8. LatestPublishers Update (iOS Only)

```
┌─ Update LatestPublishers.md (iOS Only) ───────────┐
│                                                     │
│ Detecting user: Roberto Pedraza                    │
│ Version week: 4                                    │
│                                                     │
│ Updating LatestPublishers.md...                    │
│                                                     │
│ ✓ Updated LatestPublishers.md for Roberto Pedraza (Week 4) │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Automatic - updates table with your name and version.**

---

### 9. Changes Commit

```
┌─ Commit Release Notes ────────────────────────────┐
│                                                     │
│ Staging changes...                                 │
│   M docs/LatestPublishers.md                       │
│   A docs/release-notes/ios/release-notes-26.4.0.md│
│                                                     │
│ Creating commit...                                 │
│   Message: docs: Add release notes for 26.4.0     │
│                                                     │
│ ✓ Commit created: abc1234                          │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Automatic - commits changes with standard message.**

---

## Final Result

### Created/Modified Files

```bash
# View changes
git status

# Output:
# On branch release-notes/26.4.0
# Changes to be committed:
#   modified:   docs/LatestPublishers.md
#   new file:   docs/release-notes/ios/release-notes-26.4.0.md

# View commit
git log -1

# Output:
# commit abc1234567890def
# Author: Roberto Pedraza <rpedraza@example.com>
# Date:   Sun Jan 19 16:00:00 2026
#
#     docs: Add release notes for 26.4.0
```

### View File Content

```bash
cat docs/release-notes/ios/release-notes-26.4.0.md
```

**Output:**

```markdown
# Release Notes 26.4.0 - iOS

**Date:** 2026-01-19
**Version:** 26.4.0

*🟣 Yoigo*
- Bloqueado el acceso al recargador a usuarios pospago (ECAPP-12154)
- Añadida nueva sección de consentimientos (ECAPP-12058)
- Correcciones de textos (ECAPP-12215)

*🟡 MASMOVIL*
- Bloqueado el acceso al recargador a usuarios pospago (ECAPP-12154)
- Correcciones de textos (ECAPP-12215)
...
```

### View Updated LatestPublishers

```bash
cat docs/LatestPublishers.md
```

**Output:**

```markdown
# Latest Publishers

| Publisher | Latest Version |
|-----------|----------------|
| Roberto Pedraza | [4 - 26.4.0]   |  # Updated
| Other User      | [3 - 26.3.0]   |
```

---

## Next Steps (Manual)

### Option 1: Direct push (if you have permissions)

```bash
# Push the branch
git push -u origin release-notes/26.4.0

# Create PR from GitHub UI or gh CLI
gh pr create \
  --title "docs: Release notes for 26.4.0" \
  --body "Generated release notes for version 26.4.0" \
  --base develop \
  --head release-notes/26.4.0
```

### Option 2: Full workflow with PR (automated)

Add a final step to the workflow:

```yaml
- id: create_pr
  name: "Create Pull Request"
  plugin: github
  step: create_pr
  params:
    title: "docs: Release notes for ${fix_version}"
    body: "Generated release notes for version ${fix_version}"
    base: "develop"
  requires:
    - fix_version
```

---

## Common Troubleshooting

### Error: "Workflow not found"

```bash
# Verify workflow exists
ls .titan/workflows/generate-release-notes.yaml

# If it doesn't exist, go back to Setup Step 2
```

### Error: "JIRA client not available"

```bash
# Verify JIRA configuration
titan plugins list | grep jira

# Configure JIRA if not set up
titan plugins configure jira
```

### Error: "Git client not available"

```bash
# Verify Git is installed
which git

# Verify plugin
titan plugins list | grep git
```

### Error: "No unreleased versions found"

**Possible causes:**
1. All versions have already been released in JIRA
2. You don't have permissions to view versions
3. Incorrect JIRA project

**Solution:**
```bash
# Verify in JIRA web that unreleased versions exist
# URL: https://jira.masmovil.com/projects/ECAPP/versions
```

### Error creating file: "Directory not found"

```bash
# Verify directory exists
ls -la docs/release-notes/ios

# If it doesn't exist, create it
mkdir -p docs/release-notes/ios

# Update workflow with correct path
vim .titan/workflows/generate-release-notes.yaml
```

### Branch already exists

```bash
# View local branches
git branch | grep release-notes

# Delete old branch if necessary
git branch -D release-notes/26.4.0

# Execute workflow again
```

---

## Complete Session Example

```bash
# 1. Navigate to project
$ cd ~/Documents/MasMovil/ragnarok-ios

# 2. Execute workflow
$ /generate-release-notes

# 3. Interaction
Select platform: 1 (iOS)
Select version: 3 (26.4.0)

# 4. Workflow executes...
✓ Created branch release-notes/26.4.0
✓ Found 15 issues in JIRA
✓ Generated AI descriptions
✓ Created release-notes-26.4.0.md
✓ Updated LatestPublishers.md
✓ Commit created: abc1234

# 5. Verify result
$ git status
On branch release-notes/26.4.0
nothing to commit, working tree clean

$ ls docs/release-notes/ios/
release-notes-26.4.0.md  ✓

# 6. Push and PR
$ git push -u origin release-notes/26.4.0
$ gh pr create --title "docs: Release notes for 26.4.0" --base develop

# 7. Done!
```

---

## Tips & Best Practices

### 1. Verify before executing

```bash
# View current branch
git branch --show-current

# Check for uncommitted changes
git status
```

### 2. Dry-run first

Execute with a test version to verify everything works.

### 3. Review generated release notes

```bash
# Before pushing, review content
cat docs/release-notes/ios/release-notes-26.4.0.md

# Edit if necessary
vim docs/release-notes/ios/release-notes-26.4.0.md

# Amend commit if edited
git add .
git commit --amend --no-edit
```

### 4. LatestPublishers backup

```bash
# Before executing workflow (first time)
cp docs/LatestPublishers.md docs/LatestPublishers.md.bak
```

---

**Ready to start?** Follow the Initial Setup and then execute `/generate-release-notes`!

**Last updated:** 2026-01-19
