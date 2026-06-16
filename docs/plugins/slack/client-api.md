# Slack Client API

The Slack plugin adds read-oriented Slack operations to Titan through `SlackClient`. This page documents the plugin from a functional point of view and shows how each capability is called and which parameters it needs.

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

### `post_message(channel_id, text, thread_ts=None)`

Post a plain-text message to a Slack conversation.

**Parameters:**

- `channel_id`: Required conversation ID.
- `text`: Required message text.
- `thread_ts`: Optional thread timestamp for replies.

---

## Usage constraints

- The current client surface backs discovery, messaging, and summary workflows.
- `read_channel()` exists in the client API but is not yet exposed as a public workflow step.
- The current Slack integration assumes one active Slack workspace binding per repository.
