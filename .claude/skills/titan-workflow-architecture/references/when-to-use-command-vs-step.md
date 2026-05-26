# When To Use Command vs Step

Use a command step when:

1. the action is a straightforward shell command
2. no `ctx.textual` interaction is needed
3. no custom branching logic is needed
4. no reusable Python behavior is being introduced

Use a project step when:

1. the workflow needs prompts, UI, or metadata handling
2. the shell form would be hard to read or unsafe
3. the logic needs Python conditionals or composition
