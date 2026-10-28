# Official Plugin Doc Rules

If a workflow change exposes a new public plugin capability, or changes how a public client function should be used, update the corresponding pages under `docs/plugins/<plugin>/`:

- `overview.md` — what the plugin can do
- `workflow-steps.md` — new or changed steps
- `client-api.md` — new or changed public client functions
- `built-in-workflows.md` — new or changed workflows

At minimum document:

1. what the capability does
2. how it is called or triggered
3. required parameters
4. optional parameters
5. important usage constraints

Generated step references live in `docs/plugins/generated/`: regenerate them with the
`sync-plugin-docs` workflow and check them with `validate-plugin-docs`. Never hand-edit them.
