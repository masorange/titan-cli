# Titan Builder Skill

**Official skill for building Titan CLI plugins, workflows, steps, and hooks**

## Overview

This skill teaches Claude Code how to create complete, production-ready Titan CLI plugins following the official 5-layer architecture. It provides scaffolding templates, best practices, and implementation patterns for all Titan CLI extension points.

## What This Skill Creates

### ✅ Official Plugins (5-Layer Architecture)
- Complete plugin scaffold with proper separation of concerns
- Network layer (HTTP/CLI communication)
- Services layer (data access)
- Client facade (public API)
- Operations (business logic)
- Steps (UI orchestration)
- Full test suites (targeting 100% coverage)

### ✅ Workflows
- Declarative YAML workflows
- Hook-based extension system
- Parameter substitution
- Nested workflow calls

### ✅ Custom Steps
- Simple project-specific steps
- Integration with existing plugins
- Workflow orchestration

### ✅ Workflow Extensions
- Hook implementation
- Workflow inheritance
- Parameter overrides

## When to Use

Invoke this skill when you need to:
- Create a new plugin for an external service (Slack, Jira, AWS, etc.)
- Build custom workflows for your project
- Add project-specific steps
- Extend existing workflows with hooks
- Scaffold a complete integration

## Quick Start Examples

### Example 1: Create a Slack Plugin

**User**: "Create a Slack plugin for Titan CLI"

**Claude (with skill)** will generate:
- Complete 5-layer plugin structure
- Slack API client (Network layer)
- Message service (Services layer)
- Slack client facade (Client layer)
- Message operations (Operations layer)
- Steps for sending messages, creating channels, etc.
- Full test suite

### Example 2: Add a Custom Deployment Workflow

**User**: "Create a deployment workflow that runs tests before deploying"

**Claude (with skill)** will create:
- `.titan/workflows/deploy.yaml` with hooks
- Custom steps in `.titan/steps/`
- Proper hook points for pre/post-deployment actions
- Error handling with `on_error: continue`

### Example 3: Extend Existing Workflow

**User**: "Extend the commit-ai workflow to run linting before committing"

**Claude (with skill)** will:
- Create `.titan/workflows/commit-ai.yaml` extending the base
- Implement `before_commit` hook
- Add linting step
- Configure proper error handling

## Architecture Decision Tree

```
Are you creating an official plugin?
├─ YES → Use 5-layer architecture
│   ├─ Network (HTTP/CLI)
│   ├─ Services (Data access - PRIVATE)
│   ├─ Client (Public facade)
│   ├─ Operations (Business logic - optional)
│   └─ Steps (UI orchestration)
│
└─ NO → Creating a custom project step?
    └─ Use simple pattern:
        WorkflowContext → your logic → WorkflowResult
```

## Key Features

### 🎯 Complete Scaffolding
- Generates all necessary files and directories
- Proper `pyproject.toml` configuration
- Entry points for plugin registration
- Test structure with fixtures

### 🔒 Architecture Enforcement
- Mandatory pattern matching for `ClientResult`
- Separation of concerns (Network/Services/Client/Operations/Steps)
- Type-safe error handling
- Pure business logic in Operations

### 🧪 Test-Driven
- Service tests with mocks
- Operation tests (100% coverage target)
- Test fixtures and utilities
- Example test cases

### 📚 Documentation-First
- Clear docstrings with examples
- Type annotations throughout
- Architecture decision rationale
- Best practices embedded

## File Structure Generated

For a new plugin named "slack":

```
plugins/titan-plugin-slack/
├── pyproject.toml                   # Package configuration
├── README.md                        # Plugin documentation
├── titan_plugin_slack/
│   ├── __init__.py
│   ├── plugin.py                    # Plugin registration
│   ├── models/
│   │   ├── network/                 # API response models
│   │   ├── view/                    # UI-optimized models
│   │   ├── mappers/                 # Conversion logic
│   │   └── formatting.py
│   ├── clients/
│   │   ├── network/                 # HTTP/API client
│   │   ├── services/                # Data access (PRIVATE)
│   │   └── slack_client.py          # Public facade
│   ├── operations/                  # Business logic
│   ├── steps/                       # UI orchestration
│   └── workflows/                   # YAML workflows
└── tests/
    ├── conftest.py
    ├── services/                    # Service tests
    └── operations/                  # Operation tests
```

## Best Practices Enforced

### ✅ DO (Skill ensures these)
- Pattern matching for all `ClientResult`
- Services catch BASE exception class
- Operations are pure functions
- UI models pre-formatted for display
- 100% test coverage on Services/Operations
- Clear separation of concerns

### ❌ DON'T (Skill prevents these)
- Direct `.data` access on `ClientResult`
- Business logic in Steps or Services
- UI dependencies in Operations
- Returning `None` instead of `ClientResult`
- Mixing Network and UI models

## Integration with Titan CLI

The skill respects and enforces:
- Workflow engine result types (Success/Error/Skip/Exit)
- Result wrapper pattern (`ClientResult[T]`)
- Plugin registration via entry points
- Workflow discovery from multiple sources
- Hook-based extension system

## Examples Included

The skill includes complete examples for:
1. **HTTP API Plugin**: RESTful service integration
2. **CLI Tool Plugin**: Command-line tool wrapper
3. **Simple Workflow**: Linear step execution
4. **Extended Workflow**: Hook-based customization
5. **Cleanup Workflow**: Guaranteed cleanup pattern
6. **Custom Step**: Project-specific logic

## Testing Strategy

Generated tests follow this pattern:
- **Unit tests**: For Operations (pure logic)
- **Integration tests**: For Services (with mocked Network)
- **Fixtures**: Reusable test data and mocks
- **Coverage target**: 100% for Services and Operations

## Migration Support

The skill also helps migrate existing code to the 5-layer architecture:
- Identifies business logic to extract
- Suggests Operations refactoring
- Converts old client patterns to new Result wrapper
- Updates tests to match new structure

## Compatibility

- **Titan CLI**: 0.1.0+
- **Python**: 3.11+
- **Architecture**: Official 5-layer pattern (v3.0)

## Further Reading

- [Plugin Architecture Guide](../../.claude/docs/plugin-architecture.md)
- [Workflows Guide](../../.claude/docs/workflows.md)
- [Operations Pattern](../../.claude/docs/operations.md)
- [Development Setup](../../.claude/docs/development-setup.md)

## License

Apache 2.0 (same as Titan CLI)

---

**Version**: 1.0.0
**Last Updated**: 2026-03-27
**Status**: Production Ready
