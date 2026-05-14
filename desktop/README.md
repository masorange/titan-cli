# Titan Desktop PoC

Proyecto Kotlin/Compose Desktop para la PoC V1 del adapter desktop.

## Alcance de P2-001

Este modulo cubre solo el esqueleto minimo para:

1. Lanzar Titan como subprocess local.
2. Arrancar el workflow demo `headless-v1-demo` en modo `event_stream`.
3. Dejar una shell Compose lista para la futura pantalla unica de ejecucion.

Todavia no implementa el modelo completo de estado desktop ni la proyeccion final del stream sobre header, steps, output y prompt. Eso queda para `P2-002` y `P2-003`.

## Requisitos

1. JDK 21.
2. Acceso a red la primera vez que Gradle descargue dependencias.
3. Titan CLI disponible desde la raiz del repo via `poetry run titan`.

## Quick Start

### Ejecutar headless

Modo oficial `event_stream`:

```bash
poetry run titan headless runs start headless-v1-demo \
  --project-path /home/alex/git/titan-cli
```

### Ejecutar desktop

Desde la raiz del repo:

```bash
./desktop/gradlew -p desktop run
```

No hace falta `gradle` global. El modulo usa el wrapper local de `desktop/`.

## Ejecucion

Desde la raiz del repo:

```bash
./desktop/gradlew -p desktop run
```

## Resolucion de Titan

Por defecto la app lanza Titan con:

```text
poetry run titan
```

Y usa como `project_path` el directorio padre de `desktop/`, es decir, la raiz del repo.

Variables opcionales:

1. `TITAN_CLI_COMMAND`: reemplaza el comando base. Ejemplo: `TITAN_CLI_COMMAND="poetry run titan"`
2. `TITAN_PROJECT_ROOT`: fija explicitamente el `project_path`

## Comando demo usado por el adapter

```text
titan headless runs start headless-v1-demo --project-path <repo-root>
```

La app desktop consume los eventos del protocolo por `stdout`, incluido el evento terminal `run_result_emitted`, y deja `stderr` para diagnostico tecnico.

## Verificacion rapida

```bash
./docs/harness/validate_desktop_poc.sh
./desktop/gradlew -p desktop run
```

## Validacion manual de la PoC

### Flujo completed

1. Ejecuta `./desktop/gradlew -p desktop run`.
2. Pulsa `Start`.
3. Verifica que `Run Header` muestra el run activo.
4. Verifica que aparece `Emit Text` en `Step List` y su output en `Output Timeline`.
5. Espera a que aparezca `Active Prompt` con `Confirm` y `Cancel`.
6. Pulsa `Confirm`.
7. Verifica que el prompt desaparece, aparece `Emit Markdown`, y el run termina en `completed`.
8. Verifica que el estado final queda consolidado por el evento `run_result_emitted`.

### Flujo cancelled

1. Ejecuta `./desktop/gradlew -p desktop run`.
2. Pulsa `Start`.
3. Cuando aparezca `Active Prompt`, pulsa `Cancel`.
4. Verifica que el run termina en estado terminal consistente y que el prompt desaparece.
5. Verifica que el estado final queda consolidado por el evento `run_result_emitted`.
