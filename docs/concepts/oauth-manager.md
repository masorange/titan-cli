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
- One JSON token blob per OAuth credential, stored through the core security
  adapter rather than direct keyring access
- SecretBroker-aware namespacing, so plugin OAuth credentials use the same
  scoped secret boundary as the rest of Titan
- Credential-scoped locks for refresh/login coordination

Provider adapters live outside the manager. A plugin can register a provider for
browser login, device login, service-specific refresh, or any other OAuth flow
without coupling the core manager to that product.

OAuth storage must not read or write the OS keyring directly. Plugins should
pass their scoped `SecretBroker` into `OAuthManager`; the security boundary
derives the OAuth secret store from that broker and preserves the broker's
namespace for user-scope tokens. Project-scope tokens still use the active
project's `.titan/secrets.env` through `SecretManager`, keeping the same
global/project precedence model as the rest of Titan secrets.

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

Plugins that currently own bespoke OAuth flows should migrate to this manager
incrementally.

That future work should keep UI concerns outside `titan_cli.core.oauth`: a TUI,
CLI prompt, server process, or headless runner should observe the same events and
decide how to present authorization, errors, retries, and progress.
