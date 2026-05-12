# Titan V1 Progress

## Summary

| Area | Status | Owner | Updated |
|---|---|---|---|
| Protocol V1 scope | Done | Alejandro | 2026-05-12 |
| Event model | Done | Alejandro | 2026-05-12 |
| Command model | Done | Alejandro | 2026-05-12 |
| PromptRequest model | Done | Alejandro | 2026-05-12 |
| OutputPayload model | Done | Alejandro | 2026-05-12 |
| RunResult model | Done | Alejandro | 2026-05-12 |
| Desktop PoC definition | In progress | Alejandro | 2026-05-12 |
| Headless transport | In progress | Alejandro | 2026-05-12 |
| Textual transition | Pending | Team | 2026-05-12 |

## Current
- Phase: `phase-0`
- Status: `in_progress`
- Focus: `Decide implementation architecture before coding`
- Next task: `P0-013`

## Done
- 4-layer architecture defined
- Desktop chosen as primary UX focus
- Headless confirmed as official adapter
- Textual marked as transitional
- Kotlin / Compose Desktop selected as preferred desktop direction
- Compose Desktop viability reviewed
- Initial protocol draft captured in `README.md` and `protocol.md`
- Protocol V1 scope closed and written down explicitly
- Outbound event model frozen with shared `StepRef`
- Inbound command model frozen with `start_run` left outside the runtime protocol
- PromptRequest model frozen with official V1 support limited to `confirm` and `text`
- OutputPayload model frozen with `format` naming and string-only `content` in V1
- RunResult model frozen as the terminal-only run snapshot

## In Progress
- Decide physical architecture for protocol and run coordination

## Next
1. Decide physical architecture for protocol and run coordination
2. Define transport strategy for headless V1

## Open Questions
- What is the exact bidirectional transport for desktop subprocess communication?

## Risks
- Protocol scope grows too early
- Headless transport gets coupled to the current CLI structure
- Desktop PoC starts before protocol is stable
