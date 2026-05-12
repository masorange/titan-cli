# Titan V1 Rules

## Documentation Rules

### Progress
- `progress.md` must remain a short current snapshot.
- It should contain only the current state, active focus, next steps, and open questions.
- It must not become a historical log.
- Keep it to roughly 1-2 screens.
- When progress changes, rewrite the snapshot instead of appending long notes.
- Stable architectural detail belongs in `README.md`.
- Durable decisions belong in `decisions.md`.
- Task-level execution detail belongs in `feature-list.json`.

### Feature List
- `feature-list.json` is the structured source of pending and completed tasks.
- Every task must have a stable `id`, `title`, `status`, and `priority`.
- Tasks must be actionable and testable.
- Dependencies should be used only when they add real clarity.
- Do not store long architectural discussion inside task notes.

### Decisions
- `decisions.md` stores durable architectural and strategic decisions.
- Each decision should include context, decision, and impact.
- Do not use `decisions.md` as a chronological work log.
- If a decision changes, record the new decision explicitly instead of silently rewriting history.

## Architecture Rules
- `Core` and `Engine` must not depend on concrete UI technologies.
- `Ports / Contracts` are the only official boundary between runtime and adapters.
- `Textual` is transitional only.
- `Headless` and `Desktop` are primary adapter targets.
- JSON is the first transport, not the domain model itself.

## Iteration Rules
- Prefer small protocol increments.
- Do not expand protocol scope without a real PoC need.
- Validate boundaries before polishing UI.
- Keep transport concerns separate from domain contracts.
- Keep the first desktop PoC focused on one workflow screen and one active run.
