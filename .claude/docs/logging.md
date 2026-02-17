# Logging Architecture

> Structured logging with structlog for Titan CLI

---

## 🎯 Overview

Titan CLI uses [structlog](https://www.structlog.org/) for structured logging with:

- ✅ **JSON logs** - Machine-parseable for analysis
- ✅ **File rotation** - 10MB per file, keeps 5 files (50MB total)
- ✅ **XDG-compliant** - Logs in `~/.local/state/titan/logs/`
- ✅ **Dev/Prod modes** - Colorized console (dev) vs JSON (prod)
- ✅ **Context binding** - Attach metadata to log entries

---

## 📁 Log File Locations

### End Users (Production)

```
~/.local/state/titan/logs/
├── titan.log       ← Current log file
├── titan.log.1     ← Rotated (older)
├── titan.log.2     ← Rotated (older)
├── titan.log.3     ← Rotated (older)
└── titan.log.4     ← Rotated (oldest, will be deleted on next rotation)
```

**Rotation policy:**
- Each file max: 10 MB
- Total retention: 5 files (50 MB)
- Format: JSON (structured)

**When a user reports an error, ask them to share:**
```bash
# Last 100 lines
tail -100 ~/.local/state/titan/logs/titan.log

# Or copy the whole file
cat ~/.local/state/titan/logs/titan.log
```

### Development

Same location, but logs are also displayed on console with colors.

---

## 🎨 Logging Modes

### Development Mode (titan-dev)

**Triggered by:**
- `TITAN_ENV=development`
- `--debug` flag
- Running in a TTY (terminal)

**Console output:** Colorized, human-readable
```
2026-02-17 10:30:45 | INFO     | titan.cli:main:42 - cli_invoked command=None verbose=False debug=True
2026-02-17 10:30:46 | INFO     | titan.workflow:execute:120 - workflow_started name=create_pr steps=5
2026-02-17 10:30:48 | ERROR    | titan.git:commit:55 - commit_failed error="No changes to commit"
```

**File output:** JSON
```json
{"event": "cli_invoked", "level": "info", "timestamp": "2026-02-17T10:30:45Z", "command": null}
{"event": "workflow_started", "level": "info", "timestamp": "2026-02-17T10:30:46Z", "name": "create_pr", "steps": 5}
{"event": "commit_failed", "level": "error", "timestamp": "2026-02-17T10:30:48Z", "error": "No changes to commit"}
```

### Production Mode (titan)

**Triggered by:** Default when not in dev mode

**Console output:** Minimal (only ERRORS)
```
commit_failed error="No changes to commit"
```

**File output:** JSON (same as dev)

---

## 🚀 Usage

### Basic Usage

```python
from titan_cli.core.logging_config import get_logger

logger = get_logger(__name__)

# Simple log
logger.info("operation_completed")

# Log with context
logger.info("step_started", step="commit", branch="main")

# Log errors
logger.error("operation_failed", error=str(e), step="fetch_issues")

# Exception with stack trace
try:
    risky_operation()
except Exception as e:
    logger.exception("unexpected_error", operation="fetch_data")
```

### CLI Flags

```bash
# Default: production mode (minimal console, file logging)
titan

# Verbose mode: INFO level logs on console
titan --verbose
titan -v

# Debug mode: DEBUG level logs, colorized console
titan --debug
titan -d

# Both verbose and debug
titan -v -d  # Debug takes precedence
```

### Environment Variable

```bash
# Force development mode
TITAN_ENV=development titan

# Also works with titan-dev
TITAN_ENV=development titan-dev
```

---

## 📝 Logging Best Practices

### Event Naming

Use `snake_case` for event names:

```python
# ✅ GOOD
logger.info("workflow_started")
logger.info("pr_created")
logger.error("api_request_failed")

# ❌ BAD
logger.info("Workflow Started")  # Title case
logger.info("pr-created")        # Kebab case
logger.info("PRCreated")         # Camel case
```

### Context Data

Always include relevant context:

```python
# ✅ GOOD
logger.info("commit_created",
    sha="abc123",
    message="feat: Add feature",
    branch="main"
)

logger.error("api_error",
    endpoint="/api/issues",
    status_code=500,
    error=str(e)
)

# ❌ BAD
logger.info("Commit created")  # No context
logger.error(f"API error: {e}")  # String formatting loses structure
```

### Log Levels

Use appropriate levels:

```python
# DEBUG - Detailed information for debugging
logger.debug("api_response", data=response_data)

# INFO - General information about app flow
logger.info("workflow_started", name="create_pr")

# WARNING - Something unexpected but recoverable
logger.warning("deprecated_config", key="old_setting")

# ERROR - Error that affects the operation
logger.error("operation_failed", error=str(e))

# CRITICAL - Critical error, app may crash
logger.critical("database_unreachable")
```

### Exception Logging

Use `.exception()` to capture stack traces:

```python
try:
    result = risky_operation()
except ValueError as e:
    # ✅ GOOD - Captures full stack trace
    logger.exception("validation_error", value=invalid_value)

except Exception as e:
    # ❌ BAD - No stack trace
    logger.error("operation_failed", error=str(e))
```

---

## 🔧 Examples by Component

### In CLI Commands (cli.py)

```python
from titan_cli.core.logging_config import get_logger

logger = get_logger("titan.cli")

@app.command()
def my_command():
    logger.info("command_started", command="my_command")
    try:
        # ... command logic
        logger.info("command_completed", duration=elapsed)
    except Exception as e:
        logger.exception("command_failed", command="my_command")
        raise
```

### In Workflow Steps

```python
from titan_cli.core.logging_config import get_logger

logger = get_logger("titan.workflows.create_pr")

def create_pr_step(ctx: WorkflowContext) -> WorkflowResult:
    logger.info("step_started", step="create_pr")

    # Log operations
    logger.debug("fetching_branches")
    branches = ctx.git.list_branches()
    logger.debug("branches_fetched", count=len(branches))

    # Log user actions
    branch = ctx.textual.ask_selection("Select branch", branches)
    logger.info("user_selected_branch", branch=branch)

    # Log errors
    try:
        pr = ctx.github.create_pr(branch)
        logger.info("pr_created", number=pr.number, url=pr.url)
        return Success()
    except Exception as e:
        logger.exception("pr_creation_failed", branch=branch)
        return Error(f"Failed: {e}")
```

### In Plugin Services

```python
from titan_cli.core.logging_config import get_logger

logger = get_logger("titan.plugins.jira")

class JiraService:
    def search_issues(self, jql: str) -> ClientResult[List[UIJiraIssue]]:
        logger.debug("search_started", jql=jql)

        try:
            response = self._api.search(jql)
            logger.info("search_completed",
                jql=jql,
                result_count=len(response.issues)
            )
            # ... process and return
        except JiraAPIError as e:
            logger.error("search_failed",
                jql=jql,
                error=str(e),
                status_code=e.status_code
            )
            return ClientError(error_message=str(e))
```

### In Error Handling

```python
from titan_cli.core.logging_config import get_logger

logger = get_logger("titan.github")

def fetch_pr(pr_number: int):
    logger.debug("fetching_pr", number=pr_number)

    try:
        pr = api.get_pull_request(pr_number)
        logger.info("pr_fetched", number=pr_number, state=pr.state)
        return pr
    except NotFoundError:
        logger.warning("pr_not_found", number=pr_number)
        return None
    except RateLimitError as e:
        logger.error("rate_limit_exceeded",
            reset_at=e.reset_at,
            remaining=e.remaining
        )
        raise
    except Exception as e:
        logger.exception("unexpected_error", number=pr_number)
        raise
```

---

## 🐛 Debugging Tips

### Enable Debug Mode

```bash
# See all DEBUG logs with colors
titan-dev --debug

# Or with environment variable
TITAN_ENV=development titan-dev
```

### Tail Logs in Real-Time

```bash
# Watch logs as they're written
tail -f ~/.local/state/titan/logs/titan.log

# With jq for pretty JSON
tail -f ~/.local/state/titan/logs/titan.log | jq .
```

### Search Logs

```bash
# Find all errors
grep '"level": "error"' ~/.local/state/titan/logs/titan.log | jq .

# Find specific event
grep 'pr_created' ~/.local/state/titan/logs/titan.log | jq .

# Find logs from specific module
grep 'titan.github' ~/.local/state/titan/logs/titan.log | jq .
```

### Analyze Logs with jq

```bash
# Count errors
grep '"level": "error"' ~/.local/state/titan/logs/titan.log | wc -l

# Most common events
jq -r '.event' ~/.local/state/titan/logs/titan.log | sort | uniq -c | sort -rn

# Errors grouped by module
grep '"level": "error"' ~/.local/state/titan/logs/titan.log | jq -r '.logger_name' | sort | uniq -c
```

---

## 🧹 Log Maintenance

### Automatic Rotation

Logs rotate automatically when `titan.log` reaches 10 MB:

```
titan.log (9.5 MB)  →  Write more logs  →  titan.log (10.1 MB)
                                               ↓
                                          ROTATION
                                               ↓
titan.log (0.1 MB)      ← New file
titan.log.1 (10 MB)     ← Old titan.log renamed
titan.log.2 (10 MB)     ← Previous .1
titan.log.3 (10 MB)     ← Previous .2
titan.log.4 (10 MB)     ← Previous .3
(previous .4 deleted)   ← Oldest file removed
```

### Manual Cleanup

```bash
# View disk usage
du -h ~/.local/state/titan/logs/

# Delete all logs (careful!)
rm ~/.local/state/titan/logs/*.log*

# Archive logs before deleting
tar -czf titan-logs-$(date +%Y%m%d).tar.gz ~/.local/state/titan/logs/
rm ~/.local/state/titan/logs/*.log*
```

---

## 🔍 Troubleshooting

### Logs not being created

**Check:**
1. Directory exists: `ls -la ~/.local/state/titan/logs/`
2. Permissions: `ls -ld ~/.local/state/titan/logs/`
3. Disk space: `df -h ~`

**Fix:**
```bash
mkdir -p ~/.local/state/titan/logs/
chmod 755 ~/.local/state/titan/logs/
```

### Too many logs / disk full

**Check rotation:**
```bash
# Should have max 5 files
ls -lh ~/.local/state/titan/logs/
```

**Reduce retention** (edit `logging_config.py`):
```python
backupCount=3,  # Instead of 5
```

### No console output in production

This is **expected**. Production mode only shows ERRORs on console.

**To see more:**
```bash
titan --verbose  # Show INFO logs
titan --debug    # Show DEBUG logs
```

---

## 📚 Resources

- [Structlog Documentation](https://www.structlog.org/)
- [Structlog Best Practices](https://www.structlog.org/en/stable/logging-best-practices.html)
- [Python Logging HOWTO](https://docs.python.org/3/howto/logging.html)
- [Better Stack Logging Guide](https://betterstack.com/community/guides/logging/structlog/)

---

**Last updated:** 2026-02-17
