# Titan V1 Protocol

## Modelo General
El protocolo tiene 3 piezas:

1. Outbound
- `EngineEvent`

2. Inbound
- `EngineCommand`

3. Terminal snapshot
- `RunResult`

## Transporte V1

### Protocolo canonico
El protocolo oficial V1 es bidireccional, orientado a sesion y basado en mensajes.

No depende de un transporte concreto. `stdio`, sockets, WebSocket o HTTP son bindings posibles, no parte del contrato abstracto.

### Modos
1. Final result mode
- devuelve un unico `RunResult`

2. Event stream mode
- devuelve `EngineEvent` en JSON Lines

### Binding headless V1
El binding oficial V1 para headless local usa subprocess y `stdio`:

1. `stdout`
- contiene solo mensajes del protocolo

2. `stdin`
- recibe comandos inbound del protocolo mientras el run esta vivo

3. `stderr`
- contiene logs tecnicos y diagnostico operativo
- no forma parte del protocolo abstracto

### Reglas del binding headless V1
1. En `event_stream`, `stdout` emite `EngineEvent` en JSON Lines.
2. En `run_result`, `stdout` emite un unico `RunResult` serializado como JSON.
3. En `event_stream`, `stdin` recibe `EngineCommand` en JSON Lines.
4. `stdout` nunca debe mezclar logs humanos con mensajes del protocolo.
5. `stderr` puede contener errores operativos y logs tecnicos.
6. `start_run` queda fuera del runtime protocol y pertenece al nivel adapter/comando.

### Desktop v1
- lanza Titan como subprocess local
- consume stream de eventos desde el binding headless V1
- envia comandos/respuestas por el canal inbound del binding headless V1

## Envelope comun

### Event envelope
```json
{
  "type": "step_started",
  "run_id": "run-123",
  "sequence": 12,
  "timestamp": "2026-05-12T10:00:00Z",
  "payload": {}
}
```

### Command envelope
```json
{
  "type": "submit_prompt_response",
  "run_id": "run-123",
  "timestamp": "2026-05-12T10:00:05Z",
  "payload": {}
}
```

## Reglas generales
1. `type` es obligatorio.
2. `run_id` es obligatorio en todos los mensajes de ejecucion.
3. `sequence` es obligatorio en eventos y monotono por run.
4. `timestamp` en ISO-8601 UTC.
5. `payload` siempre es un objeto JSON.
6. Campos en `snake_case`.

## Subobjetos comunes V1

### `StepRef`
```json
{
  "step_id": "check_status",
  "step_name": "Check Status",
  "step_index": 1
}
```

## Reglas del modelo outbound V1
1. Todos los eventos outbound usan el mismo `Event envelope`.
2. Todos los eventos asociados a un step reutilizan `StepRef` dentro de `payload.step`.
3. Todo output semantico del engine se emite mediante `output_emitted`.
4. Toda solicitud estructurada de input se emite mediante `prompt_requested`.
5. V1 no anade mas familias de eventos outbound salvo necesidad real de PoC.

## Outbound: `EngineEvent`

### Lista oficial de eventos V1
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

### 1. `run_started`
Se emite cuando empieza un run.

```json
{
  "type": "run_started",
  "run_id": "run-123",
  "sequence": 1,
  "timestamp": "2026-05-12T10:00:00Z",
  "payload": {
    "workflow_name": "demo-workflow",
    "workflow_title": "Demo Workflow",
    "project_path": "/path/to/project",
    "total_steps": 3
  }
}
```

### 2. `step_started`
```json
{
  "type": "step_started",
  "run_id": "run-123",
  "sequence": 2,
  "timestamp": "2026-05-12T10:00:01Z",
  "payload": {
    "step": {
      "step_id": "check_status",
      "step_name": "Check Status",
      "step_index": 1
    },
    "plugin": "git",
    "step_kind": "plugin"
  }
}
```

### 3. `output_emitted`
Evento generico de salida semantica.

```json
{
  "type": "output_emitted",
  "run_id": "run-123",
  "sequence": 3,
  "timestamp": "2026-05-12T10:00:02Z",
  "payload": {
    "step": {
      "step_id": "check_status",
      "step_name": "Check Status",
      "step_index": 1
    },
    "output": {
      "format": "markdown",
      "title": "Repository Status",
      "content": "## Clean working tree",
      "metadata": {}
    }
  }
}
```

### 4. `prompt_requested`
```json
{
  "type": "prompt_requested",
  "run_id": "run-123",
  "sequence": 4,
  "timestamp": "2026-05-12T10:00:03Z",
  "payload": {
    "step": {
      "step_id": "confirm_push",
      "step_name": "Confirm Push",
      "step_index": 2
    },
    "prompt": {
      "prompt_id": "prompt-1",
      "prompt_type": "confirm",
      "message": "Do you want to continue?",
      "default": true,
      "required": true,
      "options": []
    }
  }
}
```

### 5. `step_finished`
```json
{
  "type": "step_finished",
  "run_id": "run-123",
  "sequence": 5,
  "timestamp": "2026-05-12T10:00:06Z",
  "payload": {
    "step": {
      "step_id": "check_status",
      "step_name": "Check Status",
      "step_index": 1
    },
    "status": "success",
    "message": "Status retrieved",
    "metadata": {}
  }
}
```

### 6. `step_failed`
```json
{
  "type": "step_failed",
  "run_id": "run-123",
  "sequence": 6,
  "timestamp": "2026-05-12T10:00:07Z",
  "payload": {
    "step": {
      "step_id": "push",
      "step_name": "Push",
      "step_index": 3
    },
    "message": "Push rejected",
    "error_type": "GitError",
    "recoverable": false
  }
}
```

### 7. `step_skipped`
```json
{
  "type": "step_skipped",
  "run_id": "run-123",
  "sequence": 7,
  "timestamp": "2026-05-12T10:00:07Z",
  "payload": {
    "step": {
      "step_id": "create_commit",
      "step_name": "Create Commit",
      "step_index": 2
    },
    "message": "No changes to commit"
  }
}
```

### 8. `run_completed`
```json
{
  "type": "run_completed",
  "run_id": "run-123",
  "sequence": 8,
  "timestamp": "2026-05-12T10:00:08Z",
  "payload": {
    "message": "Workflow completed successfully"
  }
}
```

### 9. `run_failed`
```json
{
  "type": "run_failed",
  "run_id": "run-123",
  "sequence": 9,
  "timestamp": "2026-05-12T10:00:08Z",
  "payload": {
    "message": "Workflow failed at step 'push'",
    "error_type": "WorkflowExecutionError"
  }
}
```

### 10. `run_cancelled`
```json
{
  "type": "run_cancelled",
  "run_id": "run-123",
  "sequence": 10,
  "timestamp": "2026-05-12T10:00:08Z",
  "payload": {
    "message": "Run cancelled by user"
  }
}
```

## `OutputPayload`

```json
{
  "format": "text | markdown | table | diff | warning | error | json",
  "title": "optional title",
  "content": "string",
  "metadata": {}
}
```

### Campos base V1
1. `format` define el formato semantico del output.
2. `title` es opcional.
3. `content` es obligatorio y en V1 siempre es `string`.
4. `metadata` es opcional y siempre es un objeto JSON.

### Reglas V1 de output
1. `format=text`
- `content` string

2. `format=markdown`
- `content` markdown string

3. `format=table`
- diferido para despues de la PoC inicial

4. `format=diff`
- diferido para despues de la PoC inicial

5. `format=warning`
- diferido para despues de la PoC inicial

6. `format=error`
- diferido para despues de la PoC inicial

7. `format=json`
- diferido para despues de la PoC inicial

### Formatos definidos en el contrato
- `text`
- `markdown`
- `table`
- `diff`
- `warning`
- `error`
- `json`

### Formatos soportados oficialmente en V1
- `text`
- `markdown`

### Formatos diferidos para despues de la PoC inicial
- `table`
- `diff`
- `warning`
- `error`
- `json`

## `PromptRequest`

```json
{
  "prompt_id": "prompt-1",
  "prompt_type": "text | multiline | confirm | select_one | multi_select | secret",
  "message": "Question shown to the user",
  "default": null,
  "required": true,
  "options": []
}
```

### Campos base V1
1. `prompt_id` identifica de forma unica el prompt dentro del run.
2. `prompt_type` define el tipo de input solicitado.
3. `message` es el texto principal mostrado al usuario.
4. `default` define el valor por defecto cuando aplique.
5. `required` indica si el prompt requiere respuesta explicita.
6. `options` se reserva para prompts basados en seleccion.

### `PromptOption`
```json
{
  "id": "opt-1",
  "label": "Main",
  "value": "main",
  "description": "Default branch"
}
```

### `options`
Usado en `select_one` y `multi_select`.

```json
[
  {
    "id": "opt-1",
    "label": "Main",
    "value": "main",
    "description": "Default branch"
  }
]
```

### Kinds definidos en el contrato
- `confirm`
- `text`
- `multiline`
- `select_one`
- `multi_select`
- `secret`

### Kinds soportados oficialmente en V1
- `confirm`
- `text`

### Kinds diferidos para despues de la PoC inicial
- `multiline`
- `select_one`
- `multi_select`
- `secret`

## Inbound: `EngineCommand`

### Reglas del modelo inbound V1
1. Todos los comandos inbound V1 usan el mismo `Command envelope`.
2. Todos los comandos inbound V1 requieren `run_id`.
3. V1 solo define comandos inbound para runs ya creados.
4. `submit_prompt_response` es el unico comando V1 para responder a un prompt pendiente.
5. `cancel_run` es el unico comando V1 para terminar anticipadamente un run.
6. V1 no anade mas comandos inbound salvo necesidad real de PoC.

### Lista oficial de comandos inbound V1
1. `submit_prompt_response`
2. `cancel_run`

### `start_run` fuera del runtime protocol V1
`start_run` sigue existiendo como accion de adapter, CLI o API para arrancar un run, pero no forma parte del runtime protocol bidireccional de un run ya iniciado.

```json
{
  "action": "start_run",
  "workflow_name": "demo-workflow",
  "project_path": "/path/to/project",
  "params": {}
}
```

### 1. `submit_prompt_response`
```json
{
  "type": "submit_prompt_response",
  "run_id": "run-123",
  "timestamp": "2026-05-12T10:00:05Z",
  "payload": {
    "prompt_id": "prompt-1",
    "value": true
  }
}
```

### 2. `cancel_run`
```json
{
  "type": "cancel_run",
  "run_id": "run-123",
  "timestamp": "2026-05-12T10:00:06Z",
  "payload": {
    "reason": "user_cancelled"
  }
}
```

## `RunResult`

```json
{
  "run_id": "run-123",
  "workflow_name": "demo-workflow",
  "status": "completed",
  "steps": [
    {
      "id": "check_status",
      "title": "Check Status",
      "status": "success",
      "plugin": "git",
      "error": null,
      "outputs": [
        {
          "format": "markdown",
          "title": "Repository Status",
          "content": "## Clean working tree",
          "metadata": {}
        }
      ],
      "metadata": {}
    }
  ],
  "result": {
    "format": "markdown",
    "title": "Final Summary",
    "content": "# Done",
    "metadata": {}
  },
  "diagnostics": {
    "result_message": "Workflow completed successfully"
  }
}
```

### Reglas V1 de `RunResult`
1. `RunResult` es un snapshot terminal, no un estado vivo del run.
2. `status` del run solo puede ser:
- `completed`
- `failed`
- `cancelled`
3. Cada step summary incluye:
- `id`
- `title`
- `status`
- `plugin`
- `error`
- `outputs`
- `metadata`
4. `status` de step en V1 solo puede ser:
- `success`
- `failed`
- `skipped`
5. `result` es opcional.
6. `diagnostics` incluye al menos `result_message`.
