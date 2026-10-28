# Step Contracts — Secrets, AI, Results

Rules every step must follow whatever its layout (project, official plugin, community
plugin). Authoritative sources: `.claude/docs/security.md` and
`.claude/docs/workflow-step-rules.md` in titan-cli — read them when a case is not covered
here.

## Results and outputs

1. Return `Success` / `Skip` / `Exit` / `Error` from `titan_cli.engine`.
2. Publish outputs through `metadata={...}`; the executor merges it into `ctx.data`. Do not
   write `ctx.data[...]` right before returning.
3. Clients and services return `ClientResult[T]` (`titan_cli.core.result`:
   `ClientSuccess(data=...)` / `ClientError(error_message=..., error_code=...)`). Steps
   pattern-match with `match`/`case`, never `try/except` around client calls.
4. `Skip` = nothing to do (user cancelled, AI disabled, no input). `Exit` = stop the
   workflow cleanly, only before anything that needs cleanup exists.

## Secrets

No Titan API returns a secret string, and the step's code must never hold one.

| Need | Use |
|---|---|
| Is the credential configured? | `ctx.secret_broker.exists(key)` |
| Ask the user for it | `ctx.secret_broker.prompt_and_store(key, prompt)` — not `ask_password` + manual storage |
| SDK/client needing it at construction | `ctx.secret_broker.create_client(key, lambda v: Client(..., token=v))` |
| `requests.Session` with an auth header | `create_authenticated_session(ref, scheme)` (`titan_cli.core.security`) |
| Subprocess needing it | `run_with_secret_stdin` / `run_with_secret_env` / `with_secret_tempfile` |
| Material derived from a secret (decrypted JSON) | wrap in `SensitiveValue`, `.reveal()` inside the client constructor |

Never:

1. put a raw secret, or anything derived from one, in `ctx.data` or result metadata
   (`Success`/`Skip`/`Exit` raise `SecretLeakError`);
2. pass a credential on argv or through the inherited environment;
3. import `keyring` or anything under `titan_cli.core.security._vault`.

Plugins get the broker in `initialize(config, broker)`; project/user steps get
`ctx.secret_broker` scoped to `titan.project` / `titan.user`.

## AI calls

Any step that calls an AI must declare it and route through the router:

```python
from titan_cli.ai.router.declaration import declare_ai_usage
from titan_cli.ai.router.enums import AIProviderType, AITask
from titan_cli.ai.router.models import AIExecutionError, AIExecutionSuccess


@declare_ai_usage(
    task=AITask.COMMIT_MESSAGE,   # reuse an AITask member, or a stable string of your own
    executes=[AIProviderType.REMOTE, AIProviderType.CLI_HEADLESS],
    enforces=True,
)
def my_step(ctx: WorkflowContext) -> WorkflowResult:
    ...
    match ctx.ai_router.generate_text(prompt, policy=my_step, announce=ctx.textual.ai_chip):
        case AIExecutionSuccess(data=text):
            ...
        case AIExecutionError(error_code="AI_DISABLED", error_message=msg):
            return Skip(msg)          # the user turned the task off: not an error
        case AIExecutionError(error_message=err):
            return Error(err)
```

Pick the call by what the step does:

| Shape | Call | Honest `executes` |
|---|---|---|
| One prompt → one text | `generate_text()` | `REMOTE`, `CLI_HEADLESS` |
| Generator handed to an agent (many calls) | `resolve_generator()` | `REMOTE`, `CLI_HEADLESS` (prefer `REMOTE`) |
| Interactive session editing files | `resolve()` + `ctx.textual.launch_external_cli` | `CLI_INTERACTIVE` only |

Also:

1. Never ask the user to pick a provider mid-workflow, never persist a preference.
2. Pass `model=` only when the prompt truly needs that model — it overrides the user's
   choice.
3. Always pass `announce=ctx.textual.ai_chip` so the run shows which AI served it.
4. Set `enforces=True` only if the code really consults `ctx.ai_router`.
