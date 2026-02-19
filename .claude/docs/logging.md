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
from titan_cli.core.logging.config import get_logger

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

## 📐 Per-Component Rules

Each architectural layer has specific rules about what to log and what to protect.

---

### Network Layer (`clients/network/`)

**Pattern:** Log directly in the base method (`run_command`, `make_request`, etc.)

**Log:** subcommand/action, HTTP method, endpoint path, status code, duration, exit code on failure.

**NEVER log:**
- `args[2:]` in git — may contain remote URLs with credentials, commit message content
- `stdin_input` in gh — may contain PR/issue body
- GraphQL `variables` or `query` content — may contain PR/issue body
- HTTP request `params` or `json` kwargs in Jira — may contain JQL, issue content
- HTTP `headers` — contains `Authorization: Bearer <token>`
- Response content at any network layer

```python
# ✅ git_network.py
subcommand = args[1] if len(args) > 1 else "unknown"
start = time.time()
# ... run command ...
self._logger.debug("git_command_ok", subcommand=subcommand, duration=round(time.time() - start, 3))
self._logger.debug("git_command_failed", subcommand=subcommand, exit_code=e.returncode, duration=...)

# ✅ jira_network.py
self._logger.debug("jira_request_ok", method=method.upper(), endpoint=endpoint, status_code=response.status_code, duration=...)
self._logger.debug("jira_request_failed", method=method.upper(), endpoint=endpoint, status_code=e.response.status_code, duration=...)

# ✅ graphql_network.py
op_type = "mutation" if operation.lstrip().startswith("mutation") else "query"
self._logger.debug("graphql_ok", op_type=op_type, duration=...)
```

---

### Service Layer (`clients/services/`)

**Pattern:** Use `@log_client_operation()` decorator — do NOT add manual logs inside service methods.

The decorator automatically logs:
- `{op_name}_started` at DEBUG (with kwargs)
- `{op_name}_success` at INFO (with message, result_type, duration)
- `{op_name}_failed` at ERROR/WARNING (with error, error_code, duration)
- `{op_name}_exception` at ERROR with stack trace

```python
# ✅ GOOD
@log_client_operation()
def get_branches(self) -> ClientResult[List[UIGitBranch]]:
    ...

@log_client_operation("fetch_pr")
def get_pull_request(self, number: int) -> ClientResult[UIPullRequest]:
    ...

# ❌ BAD - manual logging inside a decorated service method
@log_client_operation()
def get_branches(self):
    self._logger.debug("fetching branches")  # redundant, decorator handles it
    ...
```

---

### AI Agents (`agents/`)

**Pattern:** Add `operation=` to `AgentRequest` — logging is handled centrally in `BaseAIAgent.generate()`.

**Never** add manual logs around `self.generate(request)` calls.

`BaseAIAgent.generate()` automatically logs:
- `ai_call_ok` at DEBUG: `provider`, `operation`, `tokens`, `max_tokens`, `duration`
- `ai_call_failed` at DEBUG: `provider`, `operation`, `max_tokens`, `duration`

**NEVER log:**
- `request.context` — contains diffs, issue descriptions, PR content
- `request.system_prompt` — contains project configuration
- `response.content` — contains AI-generated text

```python
# ✅ GOOD — just label the operation
request = AgentRequest(
    context=prompt,
    max_tokens=500,
    system_prompt=self.config.commit_system_prompt,
    operation="commit_message",   # ← this is all you need
)
response = self.generate(request)

# ❌ BAD — manual logging around AI calls
self._logger.debug("calling AI for commit message")
response = self.generate(request)
self._logger.debug("AI responded", tokens=response.tokens_used)  # already logged by base
```

**Available operation labels** (use these consistently):
- `commit_message` — generating a git commit message
- `pr_description` — generating PR title + body
- `issue_generation` — generating a GitHub issue
- `requirements_extraction` — Jira requirements analysis
- `risk_analysis` — Jira risk analysis
- `dependency_detection` — Jira dependency analysis
- `subtask_suggestion` — Jira subtask suggestion
- `comment_generation` — Jira comment generation

---

### Steps (`steps/`)

**Pattern:** No manual logging needed. The workflow executor logs `step_started`, `step_success`, `step_failed`, `step_skipped` automatically.

Only add logs in steps for significant business decisions that aren't captured by services:

```python
# ✅ OK — business decision worth logging
if analysis.needs_commit:
    self._logger.info("commit_required", staged_files=len(status.staged_files))

# ❌ BAD — duplicates what executor already logs
self._logger.info("starting pr creation step")
```

---

## 🔒 Security: What to Never Log

Regardless of component or log level:

| Category | Examples |
|---|---|
| Auth credentials | API tokens, Bearer headers, passwords, SSH keys |
| Secret fields | `Authorization`, `api_token`, `api_key`, `password` |
| User content | Diffs, commit messages, PR body, issue descriptions |
| AI content | Prompts sent to AI, AI responses |
| Query content | JQL queries, GraphQL variables, request bodies |
| Response bodies | HTTP responses, subprocess stdout with file content |

---

## 🔧 Examples by Component

### In CLI Commands (cli.py)

```python
from titan_cli.core.logging.config import get_logger

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
from titan_cli.core.logging.config import get_logger

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
from titan_cli.core.logging.config import get_logger

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
from titan_cli.core.logging.config import get_logger

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
