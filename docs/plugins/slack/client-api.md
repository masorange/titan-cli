# Slack Client API

The Slack plugin exposes Slack operations through `SlackClient`. This page documents the current public client surface and the parameters each method accepts.

## Requirements

To use the Slack client in Titan code:

- enable the `slack` plugin
- complete project-scoped Slack OAuth configuration so a personal token is available in keyring for the active repository

---

## Accessing the client

```python
slack_plugin = config.registry.get_plugin("slack")
client = slack_plugin.get_client()
```

---

## Connection validation

### `auth_test()`

Validate the configured personal Slack token and return identity metadata.

**Call:**

```python
client.auth_test()
```

**Parameters:**

- No parameters.

---

## Discovery operations

### `list_users(limit=100, cursor=None)`

List Slack users visible to the current token.

**Parameters:**

- `limit`: Optional maximum number of users to return.
- `cursor`: Optional pagination cursor.

### `list_public_channels(limit=100, cursor=None, exclude_archived=True)`

List public Slack channels visible to the current token.

**Parameters:**

- `limit`: Optional maximum number of channels to return.
- `cursor`: Optional pagination cursor.
- `exclude_archived`: Optional flag to skip archived channels.

### `read_channel(channel_id, limit=20, cursor=None, oldest=None, latest=None, inclusive=False)`

Read message history from a Slack public channel.

**Parameters:**

- `channel_id`: Required Slack channel ID.
- `limit`: Optional maximum number of messages to return.
- `cursor`: Optional pagination cursor.
- `oldest`: Optional oldest timestamp bound.
- `latest`: Optional latest timestamp bound.
- `inclusive`: Optional boundary inclusion flag.

### `read_conversation(conversation_id, limit=20, cursor=None, oldest=None, latest=None, inclusive=False)`

Read message history from any Slack conversation ID.

**Parameters:**

- `conversation_id`: Required conversation ID.
- `limit`: Optional maximum number of messages to return.
- `cursor`: Optional pagination cursor.
- `oldest`: Optional oldest timestamp bound.
- `latest`: Optional latest timestamp bound.
- `inclusive`: Optional boundary inclusion flag.

### `open_direct_message(user_id)`

Open or reuse a direct message conversation with a Slack user.

**Parameters:**

- `user_id`: Required Slack user ID.

### `post_message(channel_id, text, blocks=None, thread_ts=None)`

Post a message to a Slack conversation, optionally with Block Kit blocks.

**Parameters:**

- `channel_id`: Required conversation ID.
- `text`: Required message text. Always sent, even when `blocks` is provided - Slack uses it as
  the fallback for notifications and clients that can't render blocks.
- `blocks`: Optional list of Block Kit block dicts (e.g. built with `SlackBlockFormatter`, see
  [Formatting helpers](#formatting-helpers) below) rendered instead of the plain `text`.
- `thread_ts`: Optional thread timestamp for replies.

---

## Formatting helpers

Two stateless formatter classes convert standard Markdown into Slack-ready content; neither
calls the Slack API. Both live in `titan_plugin_slack` and share the same Markdown-recognition
rules (headers, bold/italic/strikethrough, links, bullet lists, pipe tables, horizontal rules),
so a document converts consistently whichever one a caller uses.

### `SlackFormatter.to_mrkdwn(text)`

Converts standard Markdown into a single Slack `mrkdwn` string (bold becomes `*bold*`, headers
become bold lines, tables render as a fixed-width grid inside a code block). This is what
`text` should always contain, whether or not `blocks` is also sent.

### `SlackBlockFormatter.to_blocks(text)`

Converts the same kind of Markdown into a list of Block Kit block dicts - one `header`,
`divider`, or `section` block per structural element - ready to pass as `post_message`'s
`blocks` parameter. Oversized sections are automatically split to stay under Slack's per-block
text limit.

`SlackBlockFormatter` also exposes builders for assembling blocks by hand instead of (or
alongside) `to_blocks`: `section(text)`, `header(text)`, `divider()`, `context(text)`, and
`fields(texts)` (up to 10 side-by-side mrkdwn fields in one section).

---

## Usage constraints

- The current client surface backs discovery, messaging, and summary workflows.
- `read_channel()` exists in the client API but is not yet exposed as a public workflow step.
- The current Slack integration assumes one active Slack workspace binding per repository.
- `granted_scopes` is recorded during OAuth connection setup; `auth_test()` validates the token but does not refresh that stored scope snapshot.
