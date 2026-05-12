# Titan V1 Decisions

## Decision Template

### D-XXX - Title
- Date: `YYYY-MM-DD`
- Status: `proposed | accepted | superseded`

#### Context
Why this decision is needed.

#### Decision
What was decided.

#### Impact
What this changes, enables, or constrains.

## Decisions

### D-001 - Four-layer target architecture
- Date: `2026-05-12`
- Status: `accepted`

#### Context
Titan needs a cleaner architectural model to separate workflow execution from UI concerns and support multiple clients.

#### Decision
Titan V1 will be organized conceptually into four layers:

1. `Core`
2. `Engine`
3. `Ports / Contracts`
4. `UI Adapters`

#### Impact
Future changes should reinforce these boundaries instead of introducing new UI coupling into the runtime.

### D-002 - Primary adapter targets
- Date: `2026-05-12`
- Status: `accepted`

#### Context
Titan needs a practical path forward for both automation and a richer user-facing experience.

#### Decision
`Headless` and `Desktop` are the primary adapter targets. `Textual` is transitional only.

#### Impact
Protocol and runtime work should prioritize headless and desktop needs first.

### D-003 - Protocol output modes
- Date: `2026-05-12`
- Status: `accepted`

#### Context
Titan needs both live execution visibility and a terminal snapshot.

#### Decision
Protocol V1 will support both:

- `event stream`
- `final_result`

#### Impact
Headless and desktop integrations must account for both live updates and final run summaries.

### D-004 - Desktop PoC integration model
- Date: `2026-05-12`
- Status: `accepted`

#### Context
The first desktop client needs a low-friction integration path while the runtime boundary is still evolving.

#### Decision
Desktop v1 will communicate with Titan through a local subprocess.

#### Impact
The protocol must be transportable over process boundaries and remain cleanly serializable.

### D-005 - Preferred desktop technology
- Date: `2026-05-12`
- Status: `accepted`

#### Context
The desktop PoC should optimize for implementation speed, architectural fit, and team familiarity.

#### Decision
Kotlin / Compose Desktop is the preferred direction for the first desktop adapter PoC.

#### Impact
The initial desktop view model and PoC UX can be designed around a Compose Desktop client, while keeping the runtime protocol UI-agnostic.
