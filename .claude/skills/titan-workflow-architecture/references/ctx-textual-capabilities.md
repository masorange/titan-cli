# ctx.textual Capabilities

Source of truth: `titan_cli/ui/tui/textual_components.py` (grep `    def ` for the current
list) and `.claude/docs/textual.md`. Snapshot of what exists:

| Need | Methods |
|---|---|
| Step lifecycle | `begin_step(name)`, `end_step("success" \| "skip" \| "error")` |
| Text | `text`, `markdown`, `dim_text`, `success_text`, `warning_text`, `error_text`, `primary_text`, `bold_text`, `bold_primary_text` |
| Blocks | `panel`, `error_card`, `table`, `collapsible_list` (copyable), `show_diff_stat`, `mount(widget)` |
| Progress | `with ctx.textual.loading("...")` |
| Prompts | `ask_text`, `ask_password`, `ask_multiline`, `ask_confirm`, `ask_choice`, `ask_multiselect`, `ask_option` |
| AI | `ai_chip` (pass as `announce=`), `ai_content_review_flow`, `ai_document_review_flow` |
| External tools | `launch_external_cli(cli_name, prompt, cwd)` (suspends the TUI) |

Rules:

1. Do not add a custom UI layer when `ctx.textual` already covers the need.
2. Don't scroll manually; `scroll_to_end()` only before an interactive widget that follows
   content taller than the screen.
3. Credentials: `ctx.secret_broker.prompt_and_store`, not `ask_password` + manual storage.
4. Errors: `error_card` (copyable, takes actions such as Retry or Diagnose), not `error_text` or a hand-made red panel. Every error the user sees is an error card.
