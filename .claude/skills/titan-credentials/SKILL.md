---
name: titan-credentials
description: Wire a credential into Titan code end to end - choose the mechanism (pasted token, OAuth with connect_oauth, a CLI's own login, a secret passed to a subprocess), store it through the broker, the config screen that connects and validates, how the code consumes it, the leak tests, and the security review. Use whenever a plugin (official or community), mod, workspace or step needs a token, API key, password, OAuth login or any secret.
disable-model-invocation: false
---

# Titan Credentials

Bring one credential into Titan without any code outside `titan_cli/core/security/` ever
holding it as a returned value. Authoritative guide: `.claude/docs/security.md` — read it
first; on any conflict it wins. Follow every step, including the last.

## 1. Choose the mechanism

| The service offers | Use | Example |
|---|---|---|
| A token or API key the user can paste | `broker.store` from the config screen, consumed with `broker.create_client` or `create_authenticated_session` | Notion, Jira |
| Only OAuth (or OAuth is the user path) | `connect_oauth` + `OAuthCredentials` from `titan_cli.core.security` | Google, Slack |
| A CLI that keeps its own login | Call the CLI; Titan stores nothing | `gh`, `gcloud` |
| A secret a subprocess needs | `run_with_secret_stdin` / `run_with_secret_env` / `with_secret_tempfile` | gpg passphrase |

Never: a credential on argv, in the inherited environment, in `ctx.data`, in result
metadata, in a config TOML, or documented as an environment variable for users to export.

## 2. Declare it

- One broker key per credential, named for what it holds (`<project>_slack_oauth`,
  `notion_token`). An OAuth grant is one key holding the whole token set.
- OAuth: an `OAuthProvider` as data — endpoints, `scopes` (narrowest that work),
  `scope_separator`, `callback_path`, where tokens and non-secret fields sit
  (`token_container`, `metadata_fields`, `id_token_claims`) and **`api_hosts`** (the only
  hosts the session may send the token to). The user's registration is an `OAuthApp`
  (`client_id`; `client_secret_key` names a broker key, never the secret itself;
  `redirect_port` only when the provider matches the redirect URI exactly).
- Public config (client id, team, granted scopes) goes in plugin config; anything a stranger
  could use goes in the broker.

## 3. The config screen

- Pasted token: `broker.store` first, then validate through `create_client`; if the service
  rejects it, `broker.delete` it again.
- OAuth: run `connect_oauth(...)` in `asyncio.to_thread`. Pass `verify=` when the account
  matters (e.g. compare `grant.metadata["email"]` with the expected one) so a wrong account
  is rejected before anything is stored.
- Save public config after the grant; on any later failure delete the grant and roll the
  config back.
- After storing or deleting, `config.load(force_plugin_init=True)`: the plugin reads the
  credential at initialize and nothing in the config files changed.
- Errors go in an error card / `severity="error"` toast with the provider's error code,
  never a response body.

## 4. Consume it

- `initialize(config, broker)`: check `broker.exists(key)`, raise the plugin's
  configuration error with what to do when missing.
- SDK needing the token at construction: `create_client(builder)` (broker or
  `OAuthCredentials`). The builder returns a client, never the token or a string with it.
- HTTP: `OAuthCredentials.session()` or `create_authenticated_session(ref)`. Never build an
  `Authorization` header in plugin code.
- Reactive refresh in an SDK client: `OAuthCredentials.refresh(apply)` — `apply` receives
  the new token; nothing returns it.
- `OAuthError.reauthorize` → tell the user to connect again; otherwise it is transient.

## 5. Logs and errors

- Titan's logging does **not** redact: log codes, ids, scopes, counts — never a payload,
  header, URL with a token, or `repr` of an object holding one.
- Exceptions raised near a credential: fixed messages, `from None` when the cause could
  carry a body.
- Dataclasses holding raw material: `field(repr=False)`; derived material:
  `SensitiveValue`.

## 6. Tests (in the plugin's `tests/`, no UI mounting)

- The happy path stores under the expected key and the client is built with it.
- A rejected credential is deleted again; a failed later step rolls config back.
- No token in: exception messages, `repr` of public objects, returned values (a builder
  returning the token raises `SecretLeakError`).
- OAuth: fake the token endpoint (`http=`), not the flow; for `connect_oauth` drive the
  loopback redirect with a real local request as `tests/core/security/test_oauth.py` does.

## 7. Close

1. Run the plugin's tests and `make test`.
2. Run the **`titan-security-reviewer`** agent on the diff, then `titan-architecture-reviewer`
   if plugin layers changed. Fix what they confirm.
3. Docs: official plugin → `docs/plugins/<plugin>/` says how to connect and which key/scopes;
   a new primitive in `core/security/` → `.claude/docs/security.md`.
