# Layer Boundaries

In project workflow code:

1. Steps orchestrate UI, context, and result handling.
2. Operations hold business logic.
3. Clients expose reusable domain APIs.
4. Services sit below clients only when integration complexity justifies them.

Do not:

1. put complex business logic in a step
2. create services without a real client-level API need
3. mimic all 5 plugin layers for trivial project automation
