# Contributing to Titan CLI

Thank you for your interest in contributing to Titan CLI! 🎉

## Quick Start for Contributors

### 1. Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/masmovil/titan-cli.git
cd titan-cli

# Install dependencies
poetry install --with dev

# Create alias for development version
alias titan-dev='poetry -C /path/to/titan-cli run python -m titan_cli.cli'

# Test your setup
titan-dev --version
```

**For detailed setup instructions (including how to run `titan` and `titan-dev` side-by-side), see [DEVELOPMENT.md](DEVELOPMENT.md).**

### 2. Make Your Changes

```bash
# Create a feature branch
git checkout -b feat/your-feature-name

# Make your changes and test with titan-dev
titan-dev

# Run tests
poetry run pytest tests/

# Lint your code
poetry run ruff check .
```

### 3. Submit a Pull Request

```bash
# Commit with conventional commit format
git commit -m "feat(scope): description of your changes"

# Push to your fork
git push origin feat/your-feature-name

# Open a PR on GitHub
```

## Commit Message Format

We use [Conventional Commits](https://www.conventionalcommits.org/) for automatic changelog generation:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code refactoring
- `chore`: Maintenance tasks
- `test`: Test changes
- `perf`: Performance improvements

**Scopes:** `ui`, `git`, `github`, `jira`, `core`, `cli`, `config`, `engine`, `workflows`

**Examples:**
```bash
feat(ui): add new component for workflow visualization
fix(git): resolve branch detection issue on Windows
docs(readme): update installation instructions
refactor(core): simplify plugin loading logic
```

## Testing

```bash
# Run all tests
poetry run pytest tests/

# Run plugin tests
poetry run pytest plugins/titan-plugin-git/tests
poetry run pytest plugins/titan-plugin-github/tests

# Run with coverage
poetry run pytest tests/ --cov=titan_cli --cov-report=html
```

## Code Style

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
# Check code style
poetry run ruff check .

# Auto-fix issues
poetry run ruff check . --fix

# Format code
poetry run ruff format .
```

## Documentation

When adding new features:

1. **Code documentation**: Add docstrings to all functions/classes
2. **User documentation**: Update relevant markdown files:
   - `README.md` - User-facing features
   - `DEVELOPMENT.md` - Technical/architectural changes
   - `AGENTS.md` - AI agent and workflow documentation
3. **Examples**: Add examples to help users understand the feature

## Need Help?

- 📖 Read [DEVELOPMENT.md](DEVELOPMENT.md) for detailed technical documentation
- 💬 Open an issue for questions or discussions
- 🐛 Report bugs using our [issue templates](.github/ISSUE_TEMPLATE/)

## Code of Conduct

Be respectful, inclusive, and constructive. We're all here to build something great together!

## License

By contributing to Titan CLI, you agree that your contributions will be licensed under the MIT License.
