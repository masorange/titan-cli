# Titan V1 Progress

## Summary

| Area | Status | Owner | Updated |
|---|---|---|---|
| Protocol V1 scope | Done | Alejandro | 2026-05-12 |
| Event model | Done | Alejandro | 2026-05-12 |
| Command model | Done | Alejandro | 2026-05-12 |
| PromptRequest model | Done | Alejandro | 2026-05-12 |
| Desktop PoC definition | In progress | Alejandro | 2026-05-12 |
| Headless transport | In progress | Alejandro | 2026-05-12 |
| Textual transition | Pending | Team | 2026-05-12 |

## Current
- Phase: `phase-0`
- Status: `in_progress`
- Focus: `Freeze output and final result protocol shapes`
- Next task: `P0-006`

## Done
- 4-layer architecture defined
- Desktop chosen as primary UX focus
- Headless confirmed as official adapter
- Textual marked as transitional
- Kotlin / Compose Desktop selected as preferred desktop direction
- Compose Desktop viability reviewed
- Initial protocol draft captured in `README.md`
- Protocol V1 scope closed and written down explicitly
- Outbound event model frozen with shared `StepRef`
- Inbound command model frozen with `start_run` left outside the runtime protocol
- PromptRequest model frozen with official V1 support limited to `confirm` and `text`

## In Progress
- Freeze output/result draft shapes

## Next
1. Freeze `OutputPayload`
2. Freeze `FinalResult`
3. Decide physical architecture for protocol and run coordination

## Open Questions
- Should `OutputPayload.content` stay string-only in V1?
- What is the exact bidirectional transport for desktop subprocess communication?

## Risks
- Protocol scope grows too early
- Headless transport gets coupled to the current CLI structure
- Desktop PoC starts before protocol is stable
