# Titan V1 Desktop PoC

## Objetivo
Validar la arquitectura basica de vista y la comunicacion con engine/core.

## Alcance
1. Lanzar un workflow demo desde desktop.
2. Escuchar `event stream`.
3. Renderizar:
- header del run
- lista de steps
- panel de output
- prompt activo
4. Enviar `submit_prompt_response`.
5. Recibir `run_result`.

## Vista principal PoC
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

## Notas de vista
1. Los estados `pending`, `running`, `success`, `failed` y `skipped` de la lista visual son estado derivado del stream de eventos.
2. No deben confundirse con `RunResult`, que es un snapshot terminal del run.
