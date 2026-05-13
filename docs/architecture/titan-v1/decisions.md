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
- `run_result`

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

### D-006 - Protocol V1 scope boundaries
- Date: `2026-05-12`
- Status: `accepted`

#### Context
Titan needs a small first protocol version that is stable enough for the first headless and desktop PoC without prematurely absorbing rendering, UX, or transport expansion concerns.

#### Decision
Protocol V1 includes:

1. `EngineEvent`
2. `EngineCommand`
3. Structured prompt requests
4. Semantic output emitted by the engine
5. `RunResult`
6. Both `event stream` and `run_result` consumption modes
7. A serializable contract usable by both `headless` and `desktop`

Protocol V1 excludes:

1. Advanced rendering concerns
2. Concrete widget/layout definitions
3. Runtime coupling to Textual or any specific UI technology
4. Run persistence as an official protocol capability
5. Multi-run desktop orchestration in the first PoC
6. Advanced prompt or output capabilities not required by the first PoC

#### Impact
The remaining phase-0 tasks should refine the exact shapes of events, commands, prompts, outputs, and final results without expanding the baseline scope unless a real PoC need appears.

### D-007 - Protocol V1 outbound event model
- Date: `2026-05-12`
- Status: `accepted`

#### Context
Titan needs a stable outbound event contract for the first headless and desktop integrations without over-generalizing the event stream.

#### Decision
Protocol V1 outbound events use a shared envelope with `type`, `run_id`, `sequence`, `timestamp`, and `payload`.

The official V1 outbound event set is:

1. `run_started`
2. `step_started`
3. `output_emitted`
4. `prompt_requested`
5. `step_finished`
6. `step_failed`
7. `step_skipped`
8. `run_completed`
9. `run_failed`
10. `run_cancelled`

All step-related events reuse a shared `StepRef` object under `payload.step`.
Semantic output is emitted only through `output_emitted` and structured input requests only through `prompt_requested`.

#### Impact
Runtime and adapters can align on a single outbound stream model while keeping `PromptRequest`, `OutputPayload`, and `RunResult` as separate follow-up refinements.

### D-008 - Protocol V1 inbound command model
- Date: `2026-05-12`
- Status: `accepted`

#### Context
Titan needs a minimal inbound command set for the first runtime protocol without mixing run bootstrap concerns with interaction on an already active run.

#### Decision
Protocol V1 inbound runtime commands use a shared envelope with `type`, `run_id`, `timestamp`, and `payload`.

The official V1 inbound runtime command set is:

1. `submit_prompt_response`
2. `cancel_run`

`start_run` is explicitly left outside the runtime protocol and remains an adapter-level action used to create and begin a run.

#### Impact
Adapters and runtime can treat the bidirectional protocol as interaction over an existing `run_id`, while run bootstrap stays outside the stream contract and can evolve independently.

### D-009 - Protocol V1 prompt request model
- Date: `2026-05-12`
- Status: `accepted`

#### Context
Titan needs a stable prompt contract that is small enough for the first PoC while still reserving space for richer prompt types later.

#### Decision
Protocol V1 `PromptRequest` includes the fields `prompt_id`, `prompt_type`, `message`, `default`, `required`, and `options`.

`PromptOption` is defined with `id`, `label`, `value`, and `description` for future selection-based prompts.

The kinds defined in the contract are:

1. `confirm`
2. `text`
3. `multiline`
4. `select_one`
5. `multi_select`
6. `secret`

Official V1 support for the first PoC is limited to:

1. `confirm`
2. `text`

The remaining kinds are explicitly deferred.

#### Impact
Adapters can implement a minimal prompt surface for the first PoC without blocking future prompt expansion or requiring the runtime to redefine the prompt contract later.

### D-010 - Protocol V1 output payload model
- Date: `2026-05-12`
- Status: `accepted`

#### Context
Titan needs a small output contract for the first PoC that works for headless and desktop adapters without prematurely committing to structured table, diff, or JSON payloads.

#### Decision
Protocol V1 `OutputPayload` uses the fields `format`, `title`, `content`, and `metadata`.

`content` is explicitly string-only in V1.

The formats defined in the contract are:

1. `text`
2. `markdown`
3. `table`
4. `diff`
5. `warning`
6. `error`
7. `json`

Official V1 support for the first PoC is limited to:

1. `text`
2. `markdown`

The remaining formats are explicitly deferred.

#### Impact
Adapters can implement a minimal output renderer for the first PoC while preserving a stable contract shape for future richer output formats.

### D-011 - Protocol V1 terminal run snapshot model
- Date: `2026-05-12`
- Status: `accepted`

#### Context
Titan needs a clear terminal run snapshot contract that does not get confused with live execution state and is not tied to legacy naming from pre-V1 architecture.

#### Decision
The canonical terminal snapshot is named `RunResult`.

`RunResult` includes:

1. `run_id`
2. `workflow_name`
3. `status`
4. `steps`
5. `result`
6. `diagnostics`

`RunResult.status` is terminal-only and can be only:

1. `completed`
2. `failed`
3. `cancelled`

Each step summary includes `id`, `title`, `status`, `plugin`, `error`, `outputs`, and `metadata`.
Step status in V1 can be only `success`, `failed`, or `skipped`.

#### Impact
The protocol distinguishes clearly between the live event stream and the terminal snapshot, while avoiding coupling the V1 contract to legacy object names such as `FinalResult` or current implementation details.

### D-012 - Legacy architecture is not canonical for V1
- Date: `2026-05-12`
- Status: `accepted`

#### Context
Titan already contains pre-V1 structures and documentation that mix runtime, contract, adapter, and orchestration concerns in ways that do not cleanly match the new four-layer target architecture.

#### Decision
Pre-V1 structures such as `application/`, `interaction/`, `commands/`, `headless/`, and earlier architecture documents are treated as transitional material, not as the canonical source of truth for V1 design.

They may be reused, split, moved, renamed, or removed as the PoC clarifies the correct separation between `Core`, `Engine`, `Ports / Contracts`, and `UI Adapters`.

#### Impact
V1 planning and implementation can evolve toward the four-layer architecture without being constrained by inherited code layout or earlier headless/runtime abstractions.

### D-013 - Minimal physical architecture for protocol and run semantics
- Date: `2026-05-12`
- Status: `accepted`

#### Context
Titan needs a physical code layout that matches the V1 four-layer architecture closely enough to start implementation, but without locking the PoC into unnecessary internal infrastructure.

#### Decision
Approved V1 protocol contracts live in `titan_cli/ports/protocol/`.

Workflow execution and run semantics live in `titan_cli/engine/`.

`commands/headless/` remains an adapter layer.

`application/` is transitional and must not receive new V1 protocol contracts.

The concrete run infrastructure must start minimal. V1 does not require a precommitted internal architecture based on `RunStore`, `EventBus`, complex `RunSession` types, or a dedicated projection module unless the PoC proves they are necessary.

#### Impact
Implementation can start with clear physical boundaries for contracts, engine, and adapters while avoiding premature internal runtime architecture that may not survive the PoC.

### D-014 - Headless V1 transport binding
- Date: `2026-05-12`
- Status: `accepted`

#### Context
Titan needs a concrete transport for the first local headless and desktop integrations while preserving a protocol model that can later map to other transports such as sockets or web channels.

#### Decision
The canonical V1 protocol remains transport-agnostic, bidirectional, session-oriented, and message-based.

The official local headless binding for V1 uses subprocess `stdio`:

1. `stdout` for protocol messages
2. `stdin` for inbound protocol commands during a live run
3. `stderr` for logs and operational diagnostics

Serialization in V1 is:

1. `event_stream` -> JSON Lines
2. `run_result` -> single JSON object

`start_run` remains outside the runtime protocol and belongs to the adapter or command layer.

#### Impact
Titan can implement one pragmatic local binding for the PoC without coupling the protocol itself to `stdio` forever, preserving a clean path to future desktop, web, and CI/CD transports.
