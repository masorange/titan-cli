import { useEffect, useMemo, useState } from 'react'

type SessionOpenedPayload = {
  session_id: string
  adapter: string
  transport: string
}

type MessageEnvelope = {
  type: string
  payload?: unknown
}

function createWebSocketUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/ws`
}

export default function App() {
  const [connectionStatus, setConnectionStatus] = useState('Connecting...')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messageLog, setMessageLog] = useState<MessageEnvelope[]>([])

  useEffect(() => {
    const socket = new WebSocket(createWebSocketUrl())

    socket.addEventListener('open', () => {
      setConnectionStatus('Connected to local backend')
      socket.send(JSON.stringify({ type: 'open_session', payload: {} }))
    })

    socket.addEventListener('message', (event) => {
      const message: MessageEnvelope = JSON.parse(event.data)
      setMessageLog((current) => [...current, message])

      if (message.type === 'session_opened') {
        const payload = message.payload as SessionOpenedPayload
        setSessionId(payload.session_id)
        setConnectionStatus(`Session ready on ${payload.transport}`)
      }

      if (message.type === 'session_error') {
        const payload = message.payload as { message?: string }
        setConnectionStatus(payload.message ?? 'Session error')
      }
    })

    socket.addEventListener('close', () => {
      setConnectionStatus('Connection closed')
    })

    socket.addEventListener('error', () => {
      setConnectionStatus('Connection error')
    })

    return () => {
      socket.close()
    }
  }, [])

  const lastMessage = useMemo(
    () => (messageLog.length > 0 ? messageLog[messageLog.length - 1] : undefined),
    [messageLog],
  )

  return (
    <main className="min-h-screen bg-titan-background text-titan-ink">
      <div className="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-6 px-6 py-10 lg:px-10">
        <section className="rounded-2xl bg-titan-panel p-8 shadow-titan ring-1 ring-titan-border">
          <div className="flex flex-col gap-4">
            <div>
              <p className="text-sm font-medium uppercase tracking-[0.24em] text-slate-500">
                Titan UI
              </p>
              <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-900">
                Local web adapter shell
              </h1>
            </div>
            <p className="max-w-3xl text-base leading-7 text-slate-600">
              This is the first real browser shell for <code>titan ui</code>. It connects to the
              localhost backend over WebSocket and keeps the runtime on your machine.
            </p>
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
          <article className="rounded-2xl bg-titan-panel p-6 shadow-titan ring-1 ring-titan-border">
            <header className="mb-4 flex items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">Session</h2>
                <p className="text-sm text-slate-500">WebSocket handshake and adapter state</p>
              </div>
              <span className="rounded-full bg-titan-soft px-3 py-1 text-sm font-medium text-titan-accent">
                {connectionStatus}
              </span>
            </header>

            <dl className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-xl border border-titan-border bg-slate-50 p-4">
                <dt className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                  Session id
                </dt>
                <dd className="mt-2 break-all text-sm font-medium text-slate-900">
                  {sessionId ?? 'Waiting for session_opened'}
                </dd>
              </div>
              <div className="rounded-xl border border-titan-border bg-slate-50 p-4">
                <dt className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                  Last message type
                </dt>
                <dd className="mt-2 text-sm font-medium text-slate-900">
                  {lastMessage?.type ?? 'No messages yet'}
                </dd>
              </div>
            </dl>
          </article>

          <article className="rounded-2xl bg-titan-panel p-6 shadow-titan ring-1 ring-titan-border">
            <header className="mb-4">
              <h2 className="text-lg font-semibold text-slate-900">Next slice</h2>
              <p className="text-sm text-slate-500">What P4-005 will wire on top of this shell</p>
            </header>
            <ul className="space-y-3 text-sm leading-6 text-slate-600">
              <li>1. Start a real workflow run from the browser.</li>
              <li>2. Stream protocol-shaped runtime events live.</li>
              <li>3. Render workflow header, steps, and semantic outputs.</li>
              <li>4. Answer prompts and richer interactions through the same channel.</li>
            </ul>
          </article>
        </section>

        <section className="rounded-2xl bg-titan-panel p-6 shadow-titan ring-1 ring-titan-border">
          <header className="mb-4">
            <h2 className="text-lg font-semibold text-slate-900">Message log</h2>
            <p className="text-sm text-slate-500">
              Raw WebSocket envelopes are shown here until the workflow run renderer lands.
            </p>
          </header>
          <pre className="overflow-x-auto rounded-2xl bg-slate-950 p-5 text-sm leading-6 text-slate-100">
            {JSON.stringify(messageLog, null, 2)}
          </pre>
        </section>
      </div>
    </main>
  )
}
