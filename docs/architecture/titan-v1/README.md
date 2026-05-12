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
- `run_result`
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
- snapshot terminal: `run_result`

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

## Transicion Arquitectonica
1. La planificacion V1 de 4 capas prevalece sobre la estructura heredada del repositorio.
2. No se asume que `application/`, `interaction/`, `commands/` o `headless/` representen la arquitectura final.
3. Esas areas se consideran transitorias y podran cambiar durante la PoC para separar mejor runtime, contratos y adapters.
4. La documentacion previa a esta planificacion tampoco se toma como canon cuando entre en conflicto con este plan V1.

## Arquitectura Fisica Minima
1. Los contratos aprobados del protocolo V1 viven en `titan_cli/ports/protocol/`.
2. La ejecucion de workflows y la semantica de `run` viven en `titan_cli/engine/`.
3. `commands/headless/` permanece como adapter y no como runtime core.
4. `application/` se considera transicional y no debe recibir nuevos contratos V1.
5. La infraestructura concreta de `run` debe empezar con la forma minima necesaria para la PoC.
6. No se asume de entrada una estructura fuerte con `RunStore`, `EventBus`, `RunSession` compleja o modulos separados de proyeccion salvo necesidad real de PoC.

## Alcance de Protocolo V1

### Incluido en V1
1. Un contrato bidireccional entre `Engine` y `UI Adapters`.
2. Salida estructurada basada en `EngineEvent`.
3. Entrada estructurada basada en `EngineCommand`.
4. Prompts estructurados para solicitar input al usuario.
5. Output semantico emitido por el engine.
6. Snapshot terminal `RunResult` para cerrar un run.
7. Dos modos oficiales de consumo:
- `event stream`
- `run_result`
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
V1 debe permanecer intencionalmente pequeno. Las siguientes tareas de fase 0 refinan la forma exacta de `events`, `commands`, `PromptRequest`, `OutputPayload` y `RunResult`, pero no deben reabrir el alcance base salvo necesidad real de PoC.

## Documentos Relacionados
1. `protocol.md` - contrato aprobado del protocolo V1.
2. `poc-desktop.md` - alcance y comportamiento de la PoC desktop.
3. `decisions.md` - decisiones duraderas de arquitectura y protocolo.
4. `progress.md` - snapshot corto del estado actual.
5. `feature-list.json` - backlog estructurado de tareas.

## Primeros pasos de implementacion

### Fase 0
1. Congelar este contrato V1 como draft.
2. Decidir el transporte bidireccional exacto del subprocess.
3. Aplicar la arquitectura fisica minima sin hacer crecer la estructura heredada.

### Fase 1
1. Hacer que `headless` soporte:
- `run_result`
- `event stream`

2. Alinear engine para emitir:
- `step_id`
- `step_index`
- `plugin`
- `output_emitted`
- `prompt_requested`

### Fase 2
1. Desktop PoC en Kotlin/Compose.
2. Estado de vista basado en:
- `run header`
- `step list`
- `output timeline`
- `active prompt`

### Fase 3
1. Validar ida y vuelta completa.
2. Decidir evolucion de Textual.
3. Abrir soporte posterior a:
- `select_one`
- `table`
- `diff`
- persistencia de runs
