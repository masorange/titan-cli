# OAuth Manager

Titan centralizes plugin OAuth coordination in `titan_cli.core.oauth`.

The manager is provider-neutral: plugins describe the credential they need with
an `OAuthRequest`, and the manager resolves an `OAuthCredential` from environment
variables, Titan's OAuth token store, legacy secret keys, or a registered OAuth
provider.

## Current Scope

- Async API: `OAuthManager.get_credential(...)`
- Blocking wrappers for today's synchronous workflow executor
- Provider-neutral events through `OAuthEventSink`
- Queue-backed event sink for a future shared runtime event queue
- One SecretManager JSON blob per OAuth credential
- Credential-scoped locks for refresh/login coordination
- Google OAuth provider integration for Firebase Remote Config tokens
- Legacy Firebase token keys still read for migration safety

Firebase can now obtain refreshable credentials through browser-based Google
OAuth with PKCE. Manual Firebase access tokens can still be stored in the OAuth
token store, but they do not include expiry metadata.

## Refresh Strategy

Provider-backed token sets should store `expires_at`.

Before returning a credential, the manager checks whether the token is still
valid outside the configured refresh margin. The default margin is 300 seconds.
If the token is expired or near expiry and a refresh token exists, the manager:

1. Acquires the credential lock.
2. Reads storage again in case another worker already refreshed it.
3. Calls the provider refresh method only if refresh is still needed.
4. Stores the refreshed token set as a single blob.
5. Emits safe lifecycle events without token values.

This prevents duplicate refreshes when several workflows, screens, or future
headless jobs ask for the same credential concurrently.

## Planned Evolution

The next provider work should migrate Slack to the same manager.

That future work should keep UI concerns outside `titan_cli.core.oauth`: a TUI,
CLI prompt, server process, or headless runner should observe the same events and
decide how to present authorization, errors, retries, and progress.
