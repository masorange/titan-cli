# Workflow Antipatterns

Avoid these mistakes:

1. Creating a brand new workflow when extending an existing one would do.
2. Creating a project step when a command step is enough.
3. Returning `Exit` from an intermediate step and skipping cleanup.
4. Putting parsing, filtering, or orchestration logic directly inside a complex step.
5. Creating a client for a one-off local action.
6. Hiding parameter flow instead of making it explicit via workflow params and metadata.
