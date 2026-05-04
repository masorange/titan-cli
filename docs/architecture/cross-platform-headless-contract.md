# Cross-Platform Headless Contract

## Goal

Titan should behave as one execution engine with many possible user interfaces.
The shared boundary is not Python code, Swift code, or Kotlin code. The shared
boundary is the `titan headless ... --json` contract.

This lets native and desktop clients consume Titan without reimplementing
workflow discovery, plugin loading, AI configuration, or execution semantics.

## Client Model

```text
Human CLI             -> Typer/Textual adapter
macOS SwiftUI         -> Process adapter + headless JSON
Kotlin Multiplatform  -> ProcessBuilder adapter + headless JSON
Web/API               -> HTTP adapter + same response models
CI/scripts            -> shell + headless JSON
```

Titan remains the Python engine. UI clients implement adapters around the
machine-readable contract.

## Stream Rules

- `stdout` is reserved for machine-readable JSON.
- `stderr` is reserved for diagnostics, logs, and technical failures.
- Successful commands return JSON on `stdout`.
- Failed commands should return actionable diagnostics on `stderr`.
- UI clients may attach a sanitized `stderr_tail` to a result, but they should
  not parse stderr as workflow data.

## Workflow Result

`WorkflowResult` is the normalized result shape a cross-platform UI should aim
to render after a run reaches a terminal state.

```json
{
  "run_id": "run-1",
  "workflow_name": "analyze-jira-issues",
  "status": "completed",
  "steps": [
    {
      "id": "ai_analyze_issue",
      "title": "AI Analyze Issue",
      "status": "success",
      "plugin": "jira",
      "error": null,
      "outputs": [
        {
          "kind": "markdown",
          "title": "JIRA Issue Analysis",
          "content": "# Analysis",
          "metadata": {}
        }
      ],
      "metadata": {}
    }
  ],
  "result": {
    "kind": "markdown",
    "title": "Final analysis",
    "content": "# Final analysis",
    "metadata": {}
  },
  "diagnostics": {
    "stderr_tail": ""
  }
}
```

## Kotlin Multiplatform Boundary

A KMP desktop app should model Titan as a local process, not as an embedded
library:

```kotlin
interface TitanWorkflowAdapter {
    suspend fun listWorkflows(projectPath: String): List<Workflow>
    suspend fun runWorkflow(projectPath: String, workflowName: String): WorkflowResult
    suspend fun respondToPrompt(runId: String, promptId: String, value: JsonElement): WorkflowResult
}
```

The local implementation can use `ProcessBuilder`:

```text
LocalTitanCliAdapter
  -> TitanExecutableResolver
  -> TitanProcessRunner
  -> titan headless ... --json
  -> DTO decoder
  -> domain models
```

Platform-specific details stay behind small interfaces:

- executable resolution
- directory picking
- filesystem permissions
- process launching

Compose Multiplatform screens should only receive domain models and feature
states.

## Acceptance Criteria

- A UI can render workflow state without reading Titan YAML directly.
- A UI can render step state without parsing terminal text.
- A UI can render markdown outputs from `WorkflowOutput(kind="markdown")`.
- A UI can show actionable errors using `WorkflowStepResult.error` and
  `WorkflowResult.diagnostics`.
- A future KMP client can reuse the same JSON contract already consumed by the
  SwiftUI prototype.
