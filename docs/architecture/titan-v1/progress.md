# Titan V1 Progress

## Summary

| Area | Status | Owner | Updated |
|---|---|---|---|
| Protocol V1 scope | In progress | Alejandro | 2026-05-12 |
| Event model | In progress | Alejandro | 2026-05-12 |
| Command model | In progress | Alejandro | 2026-05-12 |
| Desktop PoC definition | In progress | Alejandro | 2026-05-12 |
| Headless transport | In progress | Alejandro | 2026-05-12 |
| Textual transition | Pending | Team | 2026-05-12 |

## Current
- Phase: `phase-0`
- Status: `in_progress`
- Focus: `Protocol V1 scope and adapter boundary`
- Next task: `P0-002`

## Done
- 4-layer architecture defined
- Desktop chosen as primary UX focus
- Headless confirmed as official adapter
- Textual marked as transitional
- Kotlin / Compose Desktop selected as preferred desktop direction
- Compose Desktop viability reviewed
- Initial protocol draft captured in `README.md`

## In Progress
- Freeze Protocol V1 scope
- Freeze event model draft
- Freeze command model draft
- Freeze prompt/output/result draft shapes

## Next
1. Close Protocol V1 scope
2. Freeze outbound events
3. Freeze inbound commands
4. Freeze `PromptRequest`
5. Freeze `OutputPayload`
6. Freeze `FinalResult`

## Open Questions
- Should `start_run` belong to the runtime protocol?
- Should `OutputPayload.content` stay string-only in V1?
- Which prompt kinds are officially in V1?
- What is the exact bidirectional transport for desktop subprocess communication?

## Risks
- Protocol scope grows too early
- Headless transport gets coupled to the current CLI structure
- Desktop PoC starts before protocol is stable
