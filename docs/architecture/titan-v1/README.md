# Titan V1 Plan

## Objetivo Global
Separar Titan en 4 capas bien definidas y validadas con una primera integracion real entre ejecucion y vista:

1. `Core`
2. `Engine`
3. `Ports / Contracts`
4. `UI Adapters`

Con foco inmediato en:

- `Headless adapter` como canal oficial del protocolo
- `Desktop adapter` como cliente principal futuro
- PoC minima de vista principal de ejecucion de workflow

## Decisiones Cerradas
1. Salida del protocolo: ambos
- `final_result`
- `event stream`

2. Desktop PoC:
- comunicacion via subprocess local

3. Textual:
- se mantiene solo como transicion

## Capas

### 1. Core
Responsable de:

- configuracion global y por proyecto
- secretos
- logging
- descubrimiento y carga de plugins
- descubrimiento y resolucion de workflows

No conoce UI ni widgets.

### 2. Engine
Responsable de:

- ejecutar workflows
- gestionar contexto de ejecucion
- emitir eventos de ejecucion
- solicitar input cuando sea necesario
- aplicar control de flujo, errores, cancelacion y resultados

No conoce UI concreta.

### 3. Ports / Contracts
Responsable de definir el contrato bidireccional entre engine y adapters:

- salida: `events`
- entrada: `commands`
- snapshot terminal: `final_result`

Es la frontera oficial entre motor y clientes.

### 4. UI Adapters
Implementaciones del contrato:

- `headless`
- `desktop`
- `textual` como transicion

Los adapters renderizan, transportan y devuelven respuestas, pero no contienen logica de ejecucion.

## Principios
1. `Core` y `Engine` no hablan con Textual, Rich, Compose ni widgets.
2. El contrato oficial entre engine y adapters es un protocolo estructurado.
3. JSON no define el dominio; define el primer transporte oficial.
4. Desktop y headless consumen el mismo protocolo conceptual.
5. Textual deja de ser referencia arquitectonica.

## Alcance de Protocolo V1

### Incluido en V1
1. Un contrato bidireccional entre `Engine` y `UI Adapters`.
2. Salida estructurada basada en `EngineEvent`.
3. Entrada estructurada basada en `EngineCommand`.
4. Prompts estructurados para solicitar input al usuario.
5. Output semantico emitido por el engine.
6. Snapshot terminal `FinalResult` para cerrar un run.
7. Dos modos oficiales de consumo:
- `event stream`
- `final_result`
8. Transporte serializable y apto para boundaries de proceso.
9. Un mismo contrato conceptual para `headless` y `desktop`.

### Fuera de alcance en V1
1. Concerns de rendering avanzado.
2. Widgets concretos, layout visual o decisiones de UX finales.
3. Acoplamiento del runtime a Textual o a cualquier UI concreta.
4. Persistencia de runs como capacidad oficial del protocolo.
5. Orquestacion de multiples runs concurrentes en la primera PoC desktop.
6. Tipos avanzados de output o prompts que no sean necesarios para la primera PoC.
7. Multiples estrategias de transporte mas alla de la primera integracion necesaria para headless y desktop.

### Restriccion de iteracion
V1 debe permanecer intencionalmente pequeno. Las siguientes tareas de fase 0 refinan la forma exacta de `events`, `commands`, `PromptRequest`, `OutputPayload` y `FinalResult`, pero no deben reabrir el alcance base salvo necesidad real de PoC.

## Especificacion V1 del Protocolo

### Modelo General
El protocolo tiene 3 piezas:

1. Outbound
- `EngineEvent`

2. Inbound
- `EngineCommand`

3. Terminal snapshot
- `FinalResult`

### Transporte V1

#### Headless
- `stdout`: protocolo JSON
- `stderr`: logs y diagnosticos tecnicos

#### Modos
1. Final result mode
- devuelve un unico `FinalResult`

2. Event stream mode
- devuelve `EngineEvent` en JSON Lines

#### Desktop v1
- lanza Titan como subprocess local
- consume stream de eventos
- envia comandos/respuestas por el canal acordado del subprocess

### Envelope comun

#### Event envelope
```json
{
  "type": "step_started",
  "run_id": "run-123",
  "sequence": 12,
  "timestamp": "2026-05-12T10:00:00Z",
  "payload": {}
}
```

#### Command envelope
```json
{
  "type": "submit_prompt_response",
  "run_id": "run-123",
  "timestamp": "2026-05-12T10:00:05Z",
  "payload": {}
}
```

### Reglas generales
1. `type` es obligatorio.
2. `run_id` es obligatorio en todos los mensajes de ejecucion.
3. `sequence` es obligatorio en eventos y monotono por run.
4. `timestamp` en ISO-8601 UTC.
5. `payload` siempre es un objeto JSON.
6. Campos en `snake_case`.

### Subobjetos comunes V1

#### `StepRef`
```json
{
  "step_id": "check_status",
  "step_name": "Check Status",
  "step_index": 1
}
```

### Reglas del modelo outbound V1
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

### Recomendacion V1
Para simplificar la PoC:
- soportar oficialmente solo:
  - `text`
  - `markdown`

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

### Recomendacion PoC
Soportar solo:
- `confirm`
- `text`

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

## `FinalResult`

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

## PoC de Vista Desktop

### Objetivo
Validar la arquitectura basica de vista y la comunicacion con engine/core.

### Alcance
1. Lanzar un workflow demo desde desktop
2. Escuchar `event stream`
3. Renderizar:
- header del run
- lista de steps
- panel de output
- prompt activo
4. Enviar `submit_prompt_response`
5. Recibir `final_result`

### Vista principal PoC
1. Header
- workflow name
- run status
- project path

2. Lista de steps
- pending
- running
- success
- failed
- skipped

3. Output panel
- timeline de `output_emitted`
- `text`
- `markdown`

4. Prompt panel
- visible cuando llega `prompt_requested`
- inputs soportados:
  - `confirm`
  - `text`

5. Actions
- Start
- Cancel
- Submit

## Workflow Demo PoC

### Flujo
1. Step 1
- emite `text`
- termina `success`

2. Step 2
- pide `confirm`
- si `true`, continua
- si `false`, cancela o falla controladamente

3. Step 3
- emite `markdown`
- termina `success`

4. Run
- `run_completed`

## Primeros pasos de implementacion

### Fase 0
1. Congelar este contrato V1 como draft
2. Decidir dos detalles aun abiertos:
- si `output.content` sera siempre string en V1
- si `start_run` vive dentro del protocolo o solo como accion de adapter

### Fase 1
1. Hacer que `headless` soporte:
- `final_result`
- `event stream`

2. Alinear engine para emitir:
- `step_id`
- `step_index`
- `plugin`
- `output_emitted`
- `prompt_requested`

### Fase 2
1. Desktop PoC en Kotlin/Compose
2. Estado de vista basado en:
- `run header`
- `step list`
- `output timeline`
- `active prompt`

### Fase 3
1. Validar ida y vuelta completa
2. Decidir evolucion de Textual
3. Abrir soporte posterior a:
- `select_one`
- `table`
- `diff`
- persistencia de runs
