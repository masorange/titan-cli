# Public Plugin Workflow Layout

Public plugin workflows live under the plugin package, not under `.titan/`.

A common pattern is category first, then layers:

```text
titan_plugin_example/
├── category_a/
├── category_b/
├── category_c/
├── step_registry/
└── workflows/
```

When that structure exists, keep new workflows consistent with it.
