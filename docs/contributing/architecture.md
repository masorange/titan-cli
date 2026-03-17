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
