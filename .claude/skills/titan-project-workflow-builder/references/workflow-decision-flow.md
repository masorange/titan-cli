# Workflow Decision Flow

Use this order when designing a project workflow:

1. Is there already a workflow that does most of the job?
2. If yes, can it be extended with hooks?
3. If not, can the workflow call an existing workflow as a nested step?
4. If not, can a `command` step solve the missing piece safely?
5. If not, create a `plugin: project` step.
6. If that step starts to carry business logic, extract an operation.
7. Only create clients and services when the integration is reusable.

Default to the smallest option that cleanly solves the requirement.
