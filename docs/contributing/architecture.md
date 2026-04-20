# Architecture

!!! note "Coming soon"
    Detailed architecture documentation is being written. In the meantime, contributors can refer to the internal docs in `.claude/docs/` within the repository.

---

## Overview

Titan follows a 5-layer plugin architecture:

```
Steps → Operations → Client → Services → Network
  ↓         ↓          ↓         ↓          ↓
 UI    Business    Public   Data Access   HTTP/CLI
       Logic       API
```

Each official plugin (Git, GitHub, Jira) follows this structure. See the source in `plugins/` for reference implementations.

---

## Plugin Documentation Rule

When working on an official plugin, keep its public documentation in sync with the code.

This applies to changes in:

- New public client functions
- Removed public client functions
- Parameter changes in existing public client functions
- Behavioral changes that affect how an existing function should be used
- New plugin workflows that expose new capabilities worth documenting

Update the corresponding page in the `Plugins` section:

- `Git Plugin`
- `GitHub Plugin`
- `Jira Plugin`

At minimum, the documentation should reflect:

- The operation name
- How to call it
- Which parameters are required
- Which parameters are optional
- Any important usage constraints
