import { FormEvent, useEffect, useReducer, useRef, useState } from 'react'

type SessionOpenedPayload = {
  session_id: string
  adapter: string
  transport: string
}

type PromptRequest = {
  prompt_id: string
  prompt_type: string
  message: string
  default: unknown
  required: boolean
}

type OutputPayload = {
  format: string
  title?: string | null
  content: string
}

type RuntimeEvent = {
  type: string
  run_id: string
  sequence: number
  payload: Record<string, unknown>
}

type MessageEnvelope = {
  type: string
  payload?: unknown
  event?: RuntimeEvent
}

type StepState = {
  stepId: string
  stepName: string
  stepIndex: number
  status: 'pending' | 'running' | 'success' | 'failed' | 'skipped'
  outputs: OutputPayload[]
}

type RunState = {
  runId: string
  workflowName: string
  status: string
  steps: StepState[]
  activePrompt: PromptRequest | null
  activePromptStepId: string | null
  resultSummary: string | null
}

type AppState = {
  connectionStatus: string
  sessionId: string | null
  messageLog: MessageEnvelope[]
  run: RunState | null
}

type AppAction =
  | { type: 'connection'; status: string }
  | { type: 'message'; message: MessageEnvelope }

const initialState: AppState = {
  connectionStatus: 'Connecting...',
  sessionId: null,
  messageLog: [],
  run: null,
}

function createWebSocketUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/ws`
}

function upsertStep(steps: StepState[], incoming: Pick<StepState, 'stepId' | 'stepName' | 'stepIndex'>): StepState[] {
  const existingIndex = steps.findIndex((step) => step.stepId === incoming.stepId)
  if (existingIndex < 0) {
    return [
      ...steps,
      {
        ...incoming,
        status: 'pending' as const,
        outputs: [],
      },
    ].sort((left, right) => left.stepIndex - right.stepIndex)
  }

  return steps.map((step, index) =>
    index === existingIndex
      ? {
          ...step,
          stepName: incoming.stepName,
          stepIndex: incoming.stepIndex,
        }
      : step,
  )
}

function updateStep(
  steps: StepState[],
  stepId: string,
  updater: (step: StepState) => StepState,
): StepState[] {
  return steps.map((step) => (step.stepId === stepId ? updater(step) : step))
}

function reducer(state: AppState, action: AppAction): AppState {
  if (action.type === 'connection') {
    return {
      ...state,
      connectionStatus: action.status,
    }
  }

  const message = action.message
  const nextState: AppState = {
    ...state,
    messageLog: [...state.messageLog, message],
  }

  if (message.type === 'session_opened') {
    const payload = message.payload as SessionOpenedPayload
    nextState.sessionId = payload.session_id
    nextState.connectionStatus = `Session ready on ${payload.transport}`
    return nextState
  }

  if (message.type === 'session_error') {
    const payload = message.payload as { message?: string }
    nextState.connectionStatus = payload.message ?? 'Session error'
    return nextState
  }

  if (message.type === 'run_bootstrapped') {
    const payload = message.payload as {
      run_id: string
      workflow_name: string
    }
    nextState.run = {
      runId: payload.run_id,
      workflowName: payload.workflow_name,
      status: 'created',
      steps: [],
      activePrompt: null,
      activePromptStepId: null,
      resultSummary: null,
    }
    return nextState
  }

  if (message.type !== 'runtime_event' || message.event == null) {
    return nextState
  }

  const event = message.event
  const currentRun = nextState.run ?? {
    runId: event.run_id,
    workflowName: 'unknown',
    status: 'running',
    steps: [],
    activePrompt: null,
    activePromptStepId: null,
    resultSummary: null,
  }

  const stepRef = event.payload.step as
    | { step_id: string; step_name: string; step_index: number }
    | undefined

  let steps = currentRun.steps
  if (stepRef) {
    steps = upsertStep(steps, {
      stepId: stepRef.step_id,
      stepName: stepRef.step_name,
      stepIndex: stepRef.step_index,
    })
  }

  switch (event.type) {
    case 'run_started': {
      const payload = event.payload as { workflow_name?: string }
      nextState.run = {
        ...currentRun,
        workflowName: payload.workflow_name ?? currentRun.workflowName,
        status: 'running',
        steps,
      }
      return nextState
    }

    case 'step_started': {
      if (stepRef) {
        steps = updateStep(steps, stepRef.step_id, (step) => ({ ...step, status: 'running' }))
      }
      nextState.run = { ...currentRun, status: 'running', steps }
      return nextState
    }

    case 'output_emitted': {
      const output = event.payload.output as OutputPayload | undefined
      if (stepRef && output) {
        steps = updateStep(steps, stepRef.step_id, (step) => ({
          ...step,
          status: step.status === 'pending' ? 'running' : step.status,
          outputs: [...step.outputs, output],
        }))
      }
      nextState.run = { ...currentRun, status: 'running', steps }
      return nextState
    }

    case 'prompt_requested': {
      const prompt = event.payload.prompt as PromptRequest | undefined
      if (stepRef) {
        steps = updateStep(steps, stepRef.step_id, (step) => ({ ...step, status: 'running' }))
      }
      nextState.run = {
        ...currentRun,
        status: 'waiting_for_prompt',
        steps,
        activePrompt: prompt ?? null,
        activePromptStepId: stepRef?.step_id ?? null,
      }
      return nextState
    }

    case 'step_finished':
    case 'step_failed':
    case 'step_skipped': {
      const nextStatus =
        event.type === 'step_finished'
          ? 'success'
          : event.type === 'step_failed'
            ? 'failed'
            : 'skipped'
      if (stepRef) {
        steps = updateStep(steps, stepRef.step_id, (step) => ({ ...step, status: nextStatus }))
      }
      nextState.run = {
        ...currentRun,
        status: 'running',
        steps,
        activePrompt: null,
        activePromptStepId: null,
      }
      return nextState
    }

    case 'run_completed':
    case 'run_failed':
    case 'run_cancelled': {
      nextState.run = {
        ...currentRun,
        status: event.type.replace('run_', ''),
        steps,
        activePrompt: null,
        activePromptStepId: null,
      }
      return nextState
    }

    case 'run_result_emitted': {
      const runResult = event.payload.run_result as { status?: string } | undefined
      nextState.run = {
        ...currentRun,
        status: runResult?.status ?? currentRun.status,
        steps,
        activePrompt: null,
        activePromptStepId: null,
        resultSummary: runResult?.status ?? 'completed',
      }
      return nextState
    }

    default: {
      nextState.run = { ...currentRun, steps }
      return nextState
    }
  }
}

function promptValueFromInput(promptType: string, rawValue: string): string | boolean {
  if (promptType === 'confirm') {
    return rawValue === 'true'
  }
  return rawValue
}

export default function App() {
  const [state, dispatch] = useReducer(reducer, initialState)
  const [workflowName, setWorkflowName] = useState('commit-ai')
  const [projectPath, setProjectPath] = useState('')
  const [promptDraft, setPromptDraft] = useState('')
  const socketRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const socket = new WebSocket(createWebSocketUrl())
    socketRef.current = socket

    socket.addEventListener('open', () => {
      dispatch({ type: 'connection', status: 'Connected to local backend' })
      socket.send(JSON.stringify({ type: 'open_session', payload: {} }))
    })

    socket.addEventListener('message', (event) => {
      const message: MessageEnvelope = JSON.parse(event.data)
      dispatch({ type: 'message', message })
    })

    socket.addEventListener('close', () => {
      dispatch({ type: 'connection', status: 'Connection closed' })
    })

    socket.addEventListener('error', () => {
      dispatch({ type: 'connection', status: 'Connection error' })
    })

    return () => {
      socket.close()
      socketRef.current = null
    }
  }, [])

  const canStartRun = state.sessionId !== null

  const activePrompt = state.run?.activePrompt ?? null
  const activePromptStepId = state.run?.activePromptStepId ?? null

  function sendMessage(message: Record<string, unknown>) {
    socketRef.current?.send(JSON.stringify(message))
  }

  function handleStartRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    sendMessage({
      type: 'start_run',
      payload: {
        workflow_name: workflowName,
        project_path: projectPath.trim() || null,
        params: {},
      },
    })
  }

  function submitPromptResponse(value: string | boolean) {
    if (!state.run || !activePrompt) {
      return
    }
    sendMessage({
      type: 'runtime_command',
      command: {
        type: 'submit_prompt_response',
        run_id: state.run.runId,
        payload: {
          prompt_id: activePrompt.prompt_id,
          value,
        },
      },
    })
    setPromptDraft('')
  }

  function handlePromptSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!activePrompt) {
      return
    }
    submitPromptResponse(promptValueFromInput(activePrompt.prompt_type, promptDraft))
  }

  return (
    <main className="min-h-screen bg-titan-background text-titan-ink">
      <div className="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-6 px-6 py-10 lg:px-10">
        <section className="rounded-2xl bg-titan-panel p-8 shadow-titan ring-1 ring-titan-border">
          <div className="flex flex-col gap-4">
            <div>
              <p className="text-sm font-medium uppercase tracking-[0.24em] text-slate-500">Titan UI</p>
              <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-900">
                Local workflow execution shell
              </h1>
            </div>
            <p className="max-w-3xl text-base leading-7 text-slate-600">
              Start a workflow on your machine, stream protocol events in real time, and answer the
              first browser-driven prompts through the same local session.
            </p>
          </div>
        </section>

        <section>
          <article className="rounded-2xl bg-titan-panel p-6 shadow-titan ring-1 ring-titan-border">
            <header className="mb-4 flex items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">Run workflow</h2>
                <p className="text-sm text-slate-500">First real browser-driven execution path</p>
              </div>
              <span className="rounded-full bg-titan-soft px-3 py-1 text-sm font-medium text-titan-accent">
                {state.connectionStatus}
              </span>
            </header>

            <form className="space-y-4" onSubmit={handleStartRun}>
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-slate-700">Workflow name</span>
                <input
                  className="w-full rounded-xl border border-titan-border bg-white px-4 py-3 text-sm text-slate-900 outline-none ring-0 transition focus:border-titan-accent"
                  value={workflowName}
                  onChange={(event) => setWorkflowName(event.target.value)}
                />
              </label>

              <label className="block">
                <span className="mb-2 block text-sm font-medium text-slate-700">Project path</span>
                <input
                  className="w-full rounded-xl border border-titan-border bg-white px-4 py-3 text-sm text-slate-900 outline-none ring-0 transition focus:border-titan-accent"
                  value={projectPath}
                  onChange={(event) => setProjectPath(event.target.value)}
                  placeholder="Optional. Leave empty to use the backend working directory."
                />
              </label>

              <div className="flex items-center justify-between gap-4">
                <p className="text-sm text-slate-500">Session ready to launch workflows locally.</p>
                <button
                  type="submit"
                  disabled={!canStartRun}
                  className="rounded-xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
                >
                  Run workflow
                </button>
              </div>
            </form>
          </article>
        </section>

        {state.run ? (
          <section>
            <article className="rounded-2xl bg-titan-panel p-6 shadow-titan ring-1 ring-titan-border">
              <header className="mb-4">
                <h2 className="text-lg font-semibold text-slate-900">Run state</h2>
                <p className="text-sm text-slate-500">
                  {state.run.workflowName} · {state.run.runId}
                </p>
              </header>
              <div className="space-y-4">
                <div className="rounded-xl border border-titan-border bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Status</p>
                  <p className="mt-2 text-sm font-semibold text-slate-900">{state.run.status}</p>
                </div>

                <div className="space-y-3">
                  {state.run.steps.length === 0 ? (
                    <p className="text-sm text-slate-500">Waiting for workflow steps...</p>
                  ) : (
                    state.run.steps.map((step) => (
                      <div key={step.stepId} className="rounded-xl border border-titan-border bg-white p-4">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                              Step {step.stepIndex}
                            </p>
                            <h3 className="mt-1 text-sm font-semibold text-slate-900">{step.stepName}</h3>
                          </div>
                          <span className="rounded-full bg-titan-soft px-3 py-1 text-xs font-medium text-titan-accent">
                            {step.status}
                          </span>
                        </div>

                        {step.outputs.length > 0 ? (
                          <div className="mt-4 space-y-3">
                            {step.outputs.map((output, index) => (
                              <div key={`${step.stepId}-${index}`} className="rounded-lg bg-slate-950 p-3 text-sm text-slate-100">
                                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">{output.format}</p>
                                {output.title ? <p className="mt-2 font-semibold text-slate-50">{output.title}</p> : null}
                                <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words text-xs leading-6 text-slate-200">
                                  {output.content}
                                </pre>
                              </div>
                            ))}
                          </div>
                        ) : null}

                        {activePrompt && activePromptStepId === step.stepId ? (
                          <div className="mt-4 space-y-4 rounded-xl border border-titan-border bg-slate-50 p-5">
                            <div>
                              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                                Prompt · {activePrompt.prompt_type}
                              </p>
                              <p className="mt-2 text-sm text-slate-700">{activePrompt.message}</p>
                            </div>

                            {activePrompt.prompt_type === 'confirm' ? (
                              <div className="flex gap-3">
                                <button
                                  type="button"
                                  className="rounded-xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white"
                                  onClick={() => submitPromptResponse(true)}
                                >
                                  Confirm
                                </button>
                                <button
                                  type="button"
                                  className="rounded-xl border border-titan-border bg-white px-4 py-3 text-sm font-semibold text-slate-700"
                                  onClick={() => submitPromptResponse(false)}
                                >
                                  Cancel
                                </button>
                              </div>
                            ) : (
                              <form className="space-y-3" onSubmit={handlePromptSubmit}>
                                <input
                                  className="w-full rounded-xl border border-titan-border bg-white px-4 py-3 text-sm text-slate-900 outline-none ring-0 transition focus:border-titan-accent"
                                  value={promptDraft}
                                  onChange={(event) => setPromptDraft(event.target.value)}
                                  placeholder={typeof activePrompt.default === 'string' ? activePrompt.default : 'Response'}
                                />
                                <button
                                  type="submit"
                                  className="rounded-xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white"
                                >
                                  Submit response
                                </button>
                              </form>
                            )}
                          </div>
                        ) : null}
                      </div>
                    ))
                  )}
                </div>
              </div>
            </article>
          </section>
        ) : null}
      </div>
    </main>
  )
}
