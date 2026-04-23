---
name: skill-builder
description: Guide for creating new Claude skills following Anthropic's best practices. Use when user says "create a skill", "new skill", "build a skill", "skill for X", or asks about "how to create skills", "skill structure", "skill best practices", "skill guidelines".
keywords: skill creation, skill builder, best practices, anthropic guidelines, skill structure, progressive disclosure, skill template
metadata:
  author: MasOrange
  version: 1.0.0
  based_on: The Complete Guide to Building Skills for Claude (Anthropic)
---

# Skill Builder - Create Claude Skills Following Best Practices

**Purpose**: Guide Claude in creating well-structured, discoverable, and effective skills following Anthropic's official guidelines.

---

## Core Principles (Anthropic)

### Progressive Disclosure (3-Level System)

Skills use a three-level information architecture:

**Level 1: YAML Frontmatter** (Always loaded)
- Minimal metadata in system prompt
- Just enough for Claude to know WHEN to use the skill
- Under 1024 characters in description
- Includes trigger phrases

**Level 2: SKILL.md Body** (Loaded when relevant)
- Full instructions and guidance
- Detailed examples and patterns
- Best practices and rules

**Level 3: Linked Files** (Loaded as needed)
- `references/` - Additional documentation
- `scripts/` - Executable code
- `assets/` - Templates, icons, etc.

### Composability
- Skills should work alongside other skills
- No assumptions about being the only active skill
- Clear, focused scope

### Portability
- Works identically across Claude.ai, Claude Code, and API
- No environment-specific dependencies (unless documented)

---

## Skill Structure

### Directory Layout

```
skill-name/
├── skill.md              # REQUIRED - Main skill file
├── references/           # OPTIONAL - Additional docs
│   ├── api-guide.md
│   └── examples/
└── assets/               # OPTIONAL - Templates, etc.
    └── template.md
```

**Critical Rules**:
- ✅ Skill folder: `kebab-case` (e.g., `notion-project-setup`)
- ✅ Main file: Exactly `skill.md` (case-sensitive)
- ❌ No `README.md` inside skill folder (use skill.md)
- ❌ No spaces or capitals in folder name

---

## YAML Frontmatter (Level 1)

### Required Format

```yaml
---
name: skill-name
description: [What it does] + [When to use with specific triggers] + [Key capabilities]
---
```

### Complete Example

```yaml
---
name: notion-project-setup
description: Automates Notion workspace setup including database creation, template configuration, and team permissions. Use when user says "setup Notion", "create Notion workspace", "configure Notion project", or asks about "Notion automation", "workspace templates", "database setup".
keywords: notion, workspace, automation, database, templates, setup
metadata:
  author: YourName
  version: 1.0.0
  compatibility: Requires Notion MCP server
---
```

### Field Requirements

| Field | Required | Type | Constraints |
|-------|----------|------|-------------|
| `name` | ✅ Yes | string | kebab-case, no spaces/capitals, matches folder name |
| `description` | ✅ Yes | string | Under 1024 chars, includes triggers, no XML tags (< >) |
| `keywords` | ⚠️ Recommended | array/string | Searchable terms |
| `metadata` | ⚠️ Recommended | object | author, version, compatibility, etc. |
| `license` | ⚪ Optional | string | MIT, Apache-2.0, etc. (if open source) |

### Description Best Practices

**Structure**: `[What] + [When with triggers] + [Capabilities]`

✅ **GOOD** (Specific triggers):
```yaml
description: Analyzes Figma design files and generates developer handoff documentation. Use when user uploads .fig files, asks for "design specs", "component documentation", or "design-to-code handoff".
```

❌ **BAD** (Too vague):
```yaml
description: Helps with projects.
```

❌ **BAD** (No triggers):
```yaml
description: Creates sophisticated multi-page documentation systems.
```

**Trigger Phrase Examples**:
- User actions: "when user uploads", "when user mentions"
- Quoted phrases: "create workflow", "add hooks", "test this"
- Keywords: "workflow YAML", "plugin architecture", "common mistakes"
- Questions: "asks about X", "wants to know Y"

---

## Main Instructions (Level 2)

### Recommended Structure

```markdown
# Skill Name

[Brief description expanding on frontmatter]

## Instructions

### Step 1: [First Major Step]
Clear explanation of what happens.

[More steps as needed]

## Examples

### Example 1: [Common scenario]
User says: "..."
Actions:
1. ...
2. ...
Result: ...

[2-3 more examples]

## Troubleshooting

### Issue: [Common error]
**Cause**: Why it happens
**Solution**: How to fix

[2-3 more issues]

## Best Practices
- ✅ DO: ...
- ❌ DON'T: ...

---

**Version**: 1.0.0
**Last updated**: YYYY-MM-DD
```

### Instructions Section

**DO**:
- ✅ Be specific and actionable
- ✅ Include code examples with comments
- ✅ Reference bundled resources clearly
- ✅ Include error handling guidance
- ✅ Use progressive disclosure (link to `references/` for details)

**DON'T**:
- ❌ Be vague ("validate the data")
- ❌ Assume prior knowledge
- ❌ Include everything inline (use `references/`)

### Examples Section (CRITICAL)

**Every skill MUST have 3 real-world examples**:

```markdown
## Quick Examples

### Example 1: [Scenario title]

**User says**: "Exact phrase user would say"

**What Claude does**:
1. First action
2. Second action
3. Third action

**Result**: Concrete outcome

[2 more examples]
```

**Why Examples Matter**:
- Shows when skill activates
- Demonstrates expected behavior
- Helps users understand value
- Documents edge cases

### Troubleshooting Section (CRITICAL)

**Every skill MUST have troubleshooting**:

```markdown
## Troubleshooting

### Issue: "Error message or problem"
**Cause**: Root cause explanation

**Solution**:
1. Step to fix
2. Alternative approach
3. How to verify

[2 more issues]
```

**Common Issues to Cover**:
- Missing dependencies
- Configuration errors
- Permission problems
- Unexpected inputs

---

## Writing Effective Skills

### 1. Start with Use Cases

Before writing anything, define 2-3 concrete use cases:

**Good Use Case Definition**:
```
Use Case: Project Sprint Planning

Trigger: User says "help me plan this sprint" or "create sprint tasks"

Steps:
1. Fetch current project status from Linear (via MCP)
2. Analyze team velocity and capacity
3. Suggest task prioritization
4. Create tasks in Linear with proper labels

Result: Fully planned sprint with tasks created
```

**Ask yourself**:
- What does the user want to accomplish?
- What multi-step workflows does this require?
- Which tools are needed (built-in or MCP)?
- What domain knowledge should be embedded?

### 2. Define Success Criteria

**Quantitative Metrics** (Aspirational):
- Skill triggers on 90% of relevant queries
- Completes workflow in X tool calls
- 0 failed API calls per workflow

**Qualitative Metrics**:
- Users don't need to prompt about next steps
- Workflows complete without user correction
- Consistent results across sessions

### 3. Choose Skill Category

**Category 1: Document & Asset Creation**
- Creating consistent, high-quality output
- Uses Claude's built-in capabilities
- Examples: documents, presentations, code, designs

**Category 2: Workflow Automation**
- Multi-step processes with consistent methodology
- May coordinate across multiple tools
- Examples: sprint planning, release workflows

**Category 3: MCP Enhancement**
- Workflow guidance for MCP server tools
- Embeds domain expertise
- Handles common MCP issues
- Examples: service-specific best practices

### 4. Write Clear Frontmatter

**Description Formula**:
```
[Action verb] + [object] + [purpose]. Use when user [action1], [action2], or asks about [topic1], [topic2].
```

**Examples**:
```yaml
# Good - Specific and actionable
description: Analyzes code for security vulnerabilities using OWASP top 10. Use when user says "security scan", "check vulnerabilities", or uploads code files asking for "security review".

# Good - Includes trigger phrases
description: Manages Linear project workflows including sprint planning, task creation, and status tracking. Use when user mentions "sprint", "Linear tasks", "project planning", or asks to "create tickets".
```

### 5. Provide Complete Examples

**Pattern for Examples**:
```markdown
### Example [N]: [Title]

**User says**: "[Exact natural language query]"

**What Claude does**:
1. [Specific action with tool/API]
2. [Next action]
3. [Final action]

**Result**: [Concrete, measurable outcome]
```

**Cover These Scenarios**:
1. Happy path (everything works)
2. Error handling (something fails)
3. Edge case (unusual but valid input)

### 6. Add Troubleshooting

**Pattern for Issues**:
```markdown
### Issue: "[Error message or symptom]"
**Cause**: [Why this happens]

**Solution**:
[Step-by-step fix]

**Prevention**: [How to avoid in future]
```

**Common Categories**:
- Configuration errors
- Missing dependencies
- Permission issues
- API failures
- Invalid inputs

---

## Skill Creation Process

### Step-by-Step Guide

**Step 1: Plan the Skill** (5-10 minutes)
- [ ] Define 2-3 concrete use cases
- [ ] Identify trigger phrases users would say
- [ ] List required tools/capabilities
- [ ] Determine success criteria

**Step 2: Create Directory Structure**
```bash
mkdir -p .titan/skills/skill-name
cd .titan/skills/skill-name
touch skill.md
```

**Step 3: Write Frontmatter** (5 minutes)
- [ ] name (kebab-case, matches folder)
- [ ] description (what + when + triggers)
- [ ] keywords (searchable terms)
- [ ] metadata (author, version)

**Step 4: Write Instructions** (10-15 minutes)
- [ ] Clear step-by-step process
- [ ] Code examples with comments
- [ ] Error handling guidance
- [ ] Links to references/ if detailed

**Step 5: Add Examples** (5-10 minutes)
- [ ] 3 real-world scenarios
- [ ] User says + Actions + Result format
- [ ] Cover happy path + error + edge case

**Step 6: Add Troubleshooting** (5 minutes)
- [ ] 3 common issues
- [ ] Cause + Solution for each
- [ ] Prevention tips

**Step 7: Review Checklist**
- [ ] Frontmatter under 1024 chars
- [ ] No XML tags (< >) in frontmatter
- [ ] Trigger phrases included
- [ ] 3 examples provided
- [ ] 3 troubleshooting items
- [ ] Metadata complete
- [ ] File named exactly `skill.md`
- [ ] Folder name is kebab-case

---

## Validation Checklist

### Before Finalizing

**Frontmatter Validation**:
- [ ] `name` matches folder name exactly
- [ ] `description` includes specific trigger phrases
- [ ] `description` under 1024 characters
- [ ] No `<` or `>` in frontmatter
- [ ] `metadata.version` present
- [ ] `metadata.author` present

**Content Validation**:
- [ ] 3 Quick Examples provided
- [ ] Each example shows: User says + Actions + Result
- [ ] Troubleshooting section present
- [ ] 3+ issues with cause + solution
- [ ] Code examples are complete and runnable
- [ ] References to external docs are clear

**Structure Validation**:
- [ ] File is `skill.md` (not SKILL.md or skill.MD)
- [ ] Folder is kebab-case
- [ ] No README.md in skill folder
- [ ] references/ used for detailed docs
- [ ] Total size reasonable (<100KB for skill.md)

---

## Common Patterns

### Pattern: Simple Tool Wrapper

**When**: Wrapping a single MCP server or tool

```yaml
---
name: tool-name-helper
description: [Tool action] with best practices and error handling. Use when user says "[action]", "use [tool]", or asks about "[capability]".
metadata:
  author: YourName
  version: 1.0.0
  requires: tool-name MCP server
---

# Instructions
1. Verify MCP connection
2. Execute tool with parameters
3. Handle errors gracefully
4. Format results for display

[Examples and Troubleshooting]
```

### Pattern: Multi-Step Workflow

**When**: Coordinating multiple tools or steps

```yaml
---
name: workflow-name
description: Orchestrates [workflow] across [tools]. Use when user says "[trigger phrase]" or wants to "[goal]".
metadata:
  author: YourName
  version: 1.0.0
---

# Instructions

## Prerequisites
- Required tools/access
- Expected state

## Workflow Steps
1. Validation
2. Data gathering
3. Processing
4. Output/Notification

## Error Handling
- What can go wrong
- How to recover

[Examples and Troubleshooting]
```

### Pattern: Knowledge/Expertise

**When**: Embedding domain knowledge (no tools needed)

```yaml
---
name: domain-expert
description: Provides expert guidance on [domain]. Use when user asks about "[topic]", "[methodology]", or needs "[expertise]".
metadata:
  author: YourName
  version: 1.0.0
---

# Domain Knowledge
[Core concepts, principles, best practices]

# Decision Framework
[When to use what approach]

# Common Scenarios
[Typical problems and solutions]

[Examples and Troubleshooting]
```

---

## Quick Examples

### Example 1: User asks "Create a skill for API documentation"

**User says**: "I want to create a skill that generates API documentation from code"

**What Claude does**:
1. Asks for clarification: Language? API style (REST/GraphQL)?
2. Creates folder: `.titan/skills/api-doc-generator/`
3. Writes frontmatter with triggers: "generate API docs", "document API", etc.
4. Adds instructions for code parsing and doc generation
5. Includes 3 examples (REST, GraphQL, webhook)
6. Adds troubleshooting (missing annotations, parse errors, etc.)

**Result**: Complete skill ready to use for API documentation

### Example 2: User asks "How do I make my skill more discoverable?"

**User says**: "My skill isn't triggering when it should"

**What Claude explains**:
- Reviews description for specific trigger phrases
- Suggests adding user's natural language phrases
- Shows examples of good vs bad descriptions
- Recommends testing with 5-10 queries
- Updates frontmatter with better triggers

**Result**: Improved skill that triggers correctly

### Example 3: User asks "Validate this skill I created"

**User says**: "Check if my skill follows best practices"

**What Claude does**:
1. Reviews frontmatter (name, description, metadata)
2. Checks for 3 examples and troubleshooting
3. Validates trigger phrases are specific
4. Verifies file structure (skill.md, kebab-case)
5. Suggests improvements if needed

**Result**: Validation report with action items

---

## Troubleshooting

### Issue: "Skill doesn't trigger when expected"
**Cause**: Description lacks specific trigger phrases

**Solution**:
1. Review your description field
2. Add exact phrases users would say
3. Include common variations
4. Test with 5-10 natural queries
5. Iterate until trigger rate >90%

**Example Fix**:
```yaml
# Before (vague)
description: Helps with projects.

# After (specific triggers)
description: Manages Linear project workflows. Use when user says "create Linear task", "plan sprint", or asks about "project management".
```

### Issue: "Skill file not found"
**Cause**: File naming or location incorrect

**Solution**:
- File MUST be named `skill.md` (exact case)
- Folder MUST be kebab-case
- Folder name MUST match frontmatter `name`
- No README.md in skill folder

**Verify**:
```bash
ls .titan/skills/your-skill/skill.md  # Should exist
```

### Issue: "Skill loads too much context"
**Cause**: Not using Progressive Disclosure

**Solution**:
1. Keep skill.md under 2000 lines
2. Move detailed docs to `references/`
3. Link to references only when needed
4. Use Level 3 (linked files) for depth

**Example**:
```markdown
For detailed API reference, see [API Guide](references/api-guide.md).
```

---

## Best Practices Summary

### DO ✅
- Use kebab-case for folder names
- Include 3+ specific trigger phrases in description
- Add metadata (author, version)
- Provide 3 real-world examples
- Include troubleshooting section
- Keep frontmatter under 1024 characters
- Test skill activation with real queries
- Use Progressive Disclosure (3 levels)
- Reference external docs in references/
- Version your skills (1.0.0, 1.1.0, etc.)

### DON'T ❌
- Use spaces or capitals in folder names
- Write vague descriptions without triggers
- Skip examples or troubleshooting
- Include XML tags (< >) in frontmatter
- Put everything in skill.md (use references/)
- Assume skill will be only one loaded
- Make environment-specific assumptions
- Use "claude" or "anthropic" in skill name
- Create README.md inside skill folder
- Forget to version your skill

---

## Resources

### Anthropic Guidelines
- [The Complete Guide to Building Skills for Claude](https://docs.anthropic.com/skills)
- Progressive Disclosure principle
- Skill composability best practices

### Titan CLI Skill Examples
Reference these for patterns:
- `titan-workflows` - Complex workflow orchestration
- `titan-plugin-architecture` - Knowledge/expertise skill
- `titan-testing` - Tool guidance with examples
- `titan-antipatterns` - Error prevention skill

### Testing Your Skill
1. Create skill following this guide
2. Test with 10 natural language queries
3. Verify trigger rate (target: 90%)
4. Check examples are clear
5. Validate troubleshooting helps
6. Iterate based on usage

---

**Version**: 1.0.0
**Last updated**: 2026-03-31
**Based on**: The Complete Guide to Building Skills for Claude (Anthropic)
