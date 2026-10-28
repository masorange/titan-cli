---
name: titan-plugin-capability
description: Add or change a public client function in an official Titan plugin (git, github, jira, slack, docker) end to end - network call, Network model, mapper, UI model, service returning ClientResult, client facade, operation, tests and docs/plugins. Use when a step or mod needs data or an action the plugin client does not expose yet, or when changing the signature or behaviour of an existing client function. For the workflow/step part use titan-official-plugin-workflow-builder.
disable-model-invocation: false
---

# Titan Plugin Capability

Add one capability to an official plugin through every layer, in order, without skipping
the docs. Authoritative guides: `.claude/docs/plugin-architecture.md` and
`.claude/docs/operations.md` — read the first before starting.

```
Steps / mods → Operations → Client (facade) → Services → Network
                                     ↑ UI models ← mappers ← Network models
```

`titan-plugin-slack` uses a simplified layout without `models/`; match the plugin you are in.

## 0. Check it doesn't exist

Grep the plugin's client facade (`clients/<plugin>_client.py`) and services for the
operation, and `docs/plugins/<plugin>/client-api.md`. Extending an existing function with a
parameter beats a near-duplicate.

## 1. Network model — `models/network/rest/` or `models/network/graphql/`

Faithful to the API response: same field names and nesting, no formatting, no defaults the
API doesn't give. REST and GraphQL shapes live in separate packages even for the same entity.

## 2. UI model — `models/view.py` (or the plugin's equivalent)

What a step or mod displays: pre-formatted strings, derived flags, enums. No raw API dicts.

## 3. Mapper — `models/mappers/<entity>_mapper.py`

Pure function `from_network_<entity>(network) -> UI<Entity>`. No I/O, no logging. Export it
from `models/mappers/__init__.py`.

## 4. Network call

Use the plugin's existing network layer (`clients/network/`). New GraphQL queries go in
`graphql_queries.py`. Never pass a credential on argv or through the inherited environment;
authenticated objects come from the broker (`create_client`, session factory).

## 5. Service — `clients/services/<area>_service.py`

```python
@log_client_operation()
def get_thing(self, thing_id: str) -> ClientResult[UIThing]:
    try:
        raw = self.gh.run_command([...])
    except GitHubAPIError as exc:
        return ClientError(error_message=str(exc), error_code="API_ERROR")
    return ClientSuccess(data=from_network_thing(NetworkThing(**json.loads(raw))))
```

- Always `ClientResult[UIModel]`, never raises to the caller, never returns a dict.
- `ClientError.log_level="warning"` for expected cases (not found, invalid transition),
  default `"error"` for unexpected failures. `error_message` carries no sensitive data.
- Services are internal; nothing outside the client imports them.

## 6. Client facade — `clients/<plugin>_client.py`

One thin method delegating to the service, same signature and return type, short docstring.
This is the public API steps and mods call.

## 7. Operation — `operations/` (only if there is logic)

If callers need to filter, rank, combine or decide on the result, that is an operation: pure,
UI-agnostic, takes and returns UI models, no `ctx`. Steps and mods stay orchestration only.
Mods reuse the same client and operations (they don't reimplement the call).

## 8. Tests — `tests/`

- Service: mock the network layer, assert `ClientSuccess` with the mapped UI model and the
  `ClientError` path (`tests/services/test_<area>_service.py`).
- Mapper: plain input → output.
- Operation: unit tests for every branch (`tests/operations/`).
- No Textual mounting tests; no doctests in docstrings.

Run the plugin's tests via the `test-triager` agent (scope: the plugin's `tests/`).

## 9. Docs — `docs/plugins/<plugin>/`

Required by AGENTS.md whenever a public client function is added, removed or changed:

- `client-api.md` — what it does, how it's called, required and optional parameters, return
  model, error codes worth handling;
- `overview.md` if the plugin's capability list changes;
- `workflow-steps.md` / `built-in-workflows.md` if a step or workflow now exposes it;
- then run the `sync-plugin-docs` workflow and check with `validate-plugin-docs`
  (`.titan/workflows/`). Never hand-edit `docs/plugins/generated/`.

## 10. Review

Before handing back, run the `titan-architecture-reviewer` agent on the diff. Check yourself:

- [ ] Network model mirrors the API; UI model is display-ready; mapper is pure
- [ ] Service returns `ClientResult[UIModel]` and is decorated with `log_client_operation`
- [ ] Client facade method added; no caller imports a service
- [ ] Business logic in `operations/` with tests
- [ ] No credential on argv/env, no raw secret in results
- [ ] `docs/plugins/<plugin>/` updated, generated docs synced
- [ ] Version untouched if the branch already bumps it vs master
