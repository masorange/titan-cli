# Changelog

All notable changes to Titan CLI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-14

### 🎉 First Stable Release

Titan CLI v1.0.0 is the first production-ready release of our modular development tools orchestrator. This release includes a complete plugin system, AI integration, workflow engine, and intuitive terminal UI.

### ✨ Features

#### Core CLI & UI
- **Textual-Based TUI** - Modern terminal user interface built with Textual framework
- **Interactive Workflow Management** - Browse and execute workflows from dedicated TUI screen
- **Legacy Rich Menu** - Fallback Rich-based menu for backward compatibility
- **Terminal UI Components** - Centralized theming with panel, table, text, and spacer renderers
- **Multi-Provider CLI Launcher** - Support for Claude Code and Gemini CLI integration
- **External CLI Utilities** - Centralized command execution for external tools

#### Plugin System
- **Plugin Architecture** - Extensible plugin system with dependency resolution
- **Entry Point Discovery** - Automatic plugin discovery via Python entry points
- **Plugin Configuration** - Per-plugin configuration with validation
- **Plugin Marketplace** - GitHub-based registry with interactive discovery and installation
- **Dynamic Configuration Wizard** - JSON Schema-based config with secure secret storage
- **Project-Level Plugins** - Plugins install to `.titan/plugins/` per project
- **Dual-Mode Installation** - Support for local path and PyPI plugin installation
- **Git Plugin** - Complete Git operations client with AI-powered commit messages
- **GitHub Plugin** - GitHub integration with PR creation and AI-powered descriptions
- **JIRA Plugin** - JIRA issue tracking with saved queries and AI workflows

#### Workflow Engine
- **Extensible Workflows** - YAML-based workflow definitions with step composition
- **Nested Workflows** - Support for workflow inclusion and composition
- **Hook System** - Pre/post hooks for linting, testing, and custom actions
- **Step Registry** - Plugin-contributed workflow steps with dependency injection
- **Dynamic Parameters** - Runtime parameter resolution and context sharing
- **Custom Steps** - Ruff linter and pytest runner integration

#### AI Integration
- **Multi-Provider Support** - Anthropic Claude and Google Gemini backends
- **Platform Agent** - TAP + TOML configuration for AI providers
- **AI Commit Messages** - Opt-in AI-generated commit messages with context analysis
- **AI PR Descriptions** - Dynamic description length based on PR size (small/medium/large/very large)
- **PR Template Enforcement** - Structured PR descriptions following GitHub templates
- **Smart Token Limits** - Configurable max_tokens with provider-specific defaults

#### Configuration & Secrets
- **Project Discovery** - Automatic detection of Titan-enabled projects
- **Multi-Project Support** - Switch between projects with isolated configurations
- **Global Config Preservation** - Maintain global AI config when switching projects
- **Secret Management** - OS keyring integration for secure credential storage
- **Config Defaults** - Sensible defaults with override capabilities
- **TOML Configuration** - Human-readable config files with validation

#### Developer Experience
- **Comprehensive Testing** - 140+ unit tests with pytest coverage
- **Type Hints** - Full type annotations for better IDE support
- **Documentation** - Complete guides for users, developers, and AI agents
- **Error Handling** - Robust plugin error handling with graceful degradation
- **CLI Help** - Contextual help messages for all commands

### 🐛 Bug Fixes

- **Config Data Loss** - Prevent global config loss when switching projects (#50)
- **GitHub Token Limits** - Increase token limits for large PR analysis (#62, #77)
- **JIRA Credentials** - Fix credential configuration and query parameters (#60)
- **Hook Detection** - Resolve workflow hook detection issues (#77)
- **Commit/PR Decoupling** - Remove title character limits and decouple workflows (#57)
- **AI Character Limits** - Replace length truncation with user warnings
- **Workflow Resilience** - Improve error handling and recovery in workflows

### 🔄 Refactoring

- **CLI Restructuring** - Reorganize code for better maintainability (#36)
- **Menu String Centralization** - Move all UI strings to messages.py (#78)
- **External CLI Relocation** - Separate external CLI utilities from core (#78)
- **AI Provider Architecture** - Refactor to support multiple AI backends (#42)
- **Workflow Simplification** - Simplify AI prompts and enforce limits (#57)
- **Component Organization** - Separate UI components from business logic

### 📚 Documentation

- **AGENTS.md** - Complete guide for AI coding agents and contributors (#51)
- **DEVELOPMENT.md** - Architecture overview and development setup
- **INSTALLATION.md** - Step-by-step installation guide with troubleshooting
- **RELEASE.md** - Release preparation and distribution checklist
- **README.md** - User-facing documentation with quick start
- **Code Documentation** - Comprehensive docstrings and type hints

### 🔒 Security

- **Secret Storage** - OS keyring integration for credentials
- **No Hardcoded Secrets** - All sensitive data via environment or keyring
- **Plugin Validation** - Entry point verification and dependency checks
- **Safe Defaults** - Secure default configurations

### 📦 Distribution

- **PyPI Package** - Pure Python wheel (115KB)
- **Python 3.10+** - Support for Python 3.10, 3.11, 3.12
- **Cross-Platform** - Windows, macOS, Linux compatibility
- **Pipx Installation** - Isolated installation with pipx
- **No Bundled Plugins** - Clean core distribution (plugins installed separately)

### 🎯 Breaking Changes

None - this is the first stable release.

### 🚀 Migration Guide

For users upgrading from pre-release versions:

1. **Uninstall old version**: `pipx uninstall titan-cli`
2. **Install v1.0.0**: `pipx install titan-cli==1.0.0`
3. **Reinitialize config**: `titan init`
4. **Install plugins**: Plugins are now separate - install as needed

### 📊 Statistics

- **Python Files**: 150+
- **Lines of Code**: 15,000+
- **Test Coverage**: 140+ tests
- **Plugins**: 3 official (git, github, jira)
- **AI Providers**: 2 (Claude, Gemini)
- **Workflow Steps**: 20+

### 🙏 Acknowledgments

Special thanks to all contributors and early adopters who provided feedback during development.

---

## [Unreleased]

### Planned for v1.1.0+
- Automated release workflow with AI-generated changelogs
- Enhanced workflow filtering and discovery
- Workflow templates library
- Performance optimizations and caching
- Migration from google.generativeai to google.genai
- Plugin versioning and update notifications

---

**Full Changelog**: https://github.com/masmovil/titan-cli/commits/v1.0.0
