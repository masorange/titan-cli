# Plugin-like Project Architecture

For reusable project domains, use a plugin-like layout while keeping Titan compatibility.

Recommended pattern:

```text
.titan/
├── workflows/
├── steps/
│   └── slack/
├── operations/
│   └── slack/
├── clients/
│   └── slack/
└── services/
    └── slack/
```

Notes:

1. Workflow files remain under `.titan/workflows/`.
2. Project-step entrypoints remain under `.titan/steps/**`.
3. Supporting code can be separated into domain folders under other top-level `.titan/` directories.
