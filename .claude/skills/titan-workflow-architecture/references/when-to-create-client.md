# When To Create Client

Create a client only when the project is introducing a reusable integration or domain API.

Good signals:

1. multiple operations target the same external system
2. multiple workflows will reuse that integration
3. a coherent public API helps keep steps simple
4. the integration may later become a plugin

Bad signals:

1. one-off script behavior
2. purely local file edits
3. shell commands that already solve the problem cleanly
