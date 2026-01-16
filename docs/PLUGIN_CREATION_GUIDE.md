# Guía para Crear y Publicar Plugins de Titan CLI

## 🎯 Dos Caminos: Local vs Marketplace

### Camino A: Plugin Local (Privado/Experimental)
**Uso:** Plugins internos, experimentales, o específicos de tu organización
**Proceso:** Simple, sin aprobación
**Duración:** 30 minutos

### Camino B: Plugin Oficial (Marketplace)
**Uso:** Plugins públicos que quieres compartir con la comunidad
**Proceso:** Con revisión de código
**Duración:** 1-2 semanas (incluye revisión)

---

## 🚀 Camino A: Crear Plugin Local

### Paso 1: Generar Estructura del Plugin

```bash
# Crear directorio del plugin
mkdir -p titan-plugin-custom
cd titan-plugin-custom

# Inicializar con Poetry
poetry init --name titan-plugin-custom \
            --description "My custom Titan plugin" \
            --author "Your Name <email@example.com>"
```

### Paso 2: Crear Estructura de Archivos

```
titan-plugin-custom/
├── pyproject.toml              # Configuración Poetry
├── plugin.json                 # Manifest del plugin (opcional para local)
├── README.md
├── titan_plugin_custom/
│   ├── __init__.py
│   ├── plugin.py               # Clase principal
│   ├── client.py               # Cliente del servicio (opcional)
│   └── steps/                  # Workflow steps
│       ├── __init__.py
│       └── my_step.py
└── tests/
    ├── __init__.py
    └── test_plugin.py
```

### Paso 3: Implementar Plugin Base

**`titan_plugin_custom/plugin.py`:**

```python
from typing import Dict, Any, Optional
from titan_cli.core.plugins.plugin_base import TitanPlugin


class CustomPlugin(TitanPlugin):
    """
    Custom plugin for Titan CLI.
    """

    def __init__(self):
        super().__init__()
        self._client: Optional[Any] = None

    @property
    def name(self) -> str:
        return "custom"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Custom functionality for Titan CLI"

    @property
    def dependencies(self) -> list[str]:
        """Plugins que este plugin necesita."""
        return []  # Ejemplo: ["git"] si necesitas GitPlugin

    def initialize(self, config: Any, secrets: Any) -> None:
        """
        Inicializa el plugin con configuración y secretos.

        Args:
            config: TitanConfig instance
            secrets: SecretManager instance
        """
        # Obtener configuración del plugin
        plugin_config = config.config.plugins.get(self.name)

        if not plugin_config or not plugin_config.enabled:
            return

        # Ejemplo: Leer API token de secrets
        api_token = secrets.get("CUSTOM_API_TOKEN")

        # Inicializar tu cliente
        from .client import CustomClient
        self._client = CustomClient(
            api_token=api_token,
            base_url=plugin_config.config.get("base_url")
        )

    def is_available(self) -> bool:
        """Retorna True si el plugin está listo para usar."""
        return self._client is not None

    def get_client(self):
        """Retorna el cliente inicializado."""
        if not self.is_available():
            raise RuntimeError(f"{self.name} plugin not initialized")
        return self._client

    def get_steps(self) -> Dict[str, Any]:
        """
        Retorna los workflow steps que este plugin provee.
        """
        from .steps.my_step import my_custom_step

        return {
            "my_custom_step": my_custom_step,
        }
```

### Paso 4: Implementar Workflow Step (Opcional)

**`titan_plugin_custom/steps/my_step.py`:**

```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error


def my_custom_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Workflow step example.

    Args:
        ctx: WorkflowContext con acceso a plugins, UI, config, etc.

    Returns:
        Success, Error, o Skip
    """
    # 1. Mostrar header (opcional)
    if ctx.views:
        ctx.views.step_header("my_custom_step", ctx.current_step, ctx.total_steps)

    # 2. Verificar que el plugin esté disponible
    if not ctx.custom:  # ctx.{plugin_name}
        return Error("Custom plugin not available")

    # 3. Obtener cliente
    client = ctx.custom.get_client()

    # 4. Ejecutar lógica
    try:
        result = client.do_something()

        # 5. Mostrar resultado en UI
        if ctx.ui:
            ctx.ui.text.success(f"Operation completed: {result}")

        # 6. Retornar éxito con metadata
        return Success(
            message="Step completed successfully",
            metadata={"result": result}
        )

    except Exception as e:
        return Error(f"Step failed: {str(e)}", exception=e)
```

### Paso 5: Configurar Entry Point

**`pyproject.toml`:**

```toml
[tool.poetry]
name = "titan-plugin-custom"
version = "1.0.0"
description = "Custom plugin for Titan CLI"
authors = ["Your Name <email@example.com>"]

[tool.poetry.dependencies]
python = "^3.10"
titan-cli = "^1.0.0"  # Dependencia del core
requests = "^2.31.0"  # Ejemplo de dependencia externa

[tool.poetry.group.dev.dependencies]
pytest = "^8.0"

# 🔥 CRITICAL: Entry point para que Titan descubra el plugin
[tool.poetry.plugins."titan.plugins"]
custom = "titan_plugin_custom.plugin:CustomPlugin"

[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"
```

### Paso 6: Construir e Instalar Localmente

```bash
# Construir el plugin
poetry build

# Instalar en Titan CLI
pipx inject titan-cli ./dist/titan_plugin_custom-1.0.0-py3-none-any.whl

# O instalar en modo desarrollo (editable)
pipx inject titan-cli --editable .
```

### Paso 7: Verificar Instalación

```bash
# Listar plugins instalados
titan plugins list

# Deberías ver:
# custom    ✓    (tu configuración)

# Ver info del plugin
titan plugins info custom
```

### Paso 8: Configurar Plugin (si necesita config)

```bash
# Opción 1: Manual en ~/.titan/config.toml
[plugins.custom]
enabled = true

  [plugins.custom.config]
  base_url = "https://api.example.com"

# Opción 2: Vía CLI (si implementas wizard)
titan plugins configure custom
```

### Paso 9: Usar en Workflow

**`.titan/workflows/my-workflow.yaml`:**

```yaml
name: "My Custom Workflow"
description: "Uses custom plugin"

steps:
  - id: step1
    name: "Run Custom Step"
    plugin: custom
    step: my_custom_step
```

```bash
# Ejecutar workflow
titan workflow run my-workflow
```

---

## 🏛️ Camino B: Publicar Plugin Oficial (Marketplace)

Este camino incluye todos los pasos del Camino A, más:

### Paso 10: Crear `plugin.json` Manifest

**`plugin.json`** (en raíz del plugin):

```json
{
  "name": "custom",
  "display_name": "Custom Integration",
  "version": "1.0.0",
  "description": "Integration with Custom Service",
  "author": "Your Name <email@example.com>",
  "license": "MIT",
  "category": "community",
  "verified": false,

  "entry_point": "titan_plugin_custom.plugin:CustomPlugin",
  "min_titan_version": "1.0.0",

  "dependencies": [],
  "python_dependencies": ["requests>=2.31.0"],

  "installation": {
    "pre_install": null,
    "post_install": null
  },

  "configSchema": {
    "type": "object",
    "title": "Custom Plugin Configuration",
    "description": "Configure connection to Custom Service",
    "properties": {
      "base_url": {
        "type": "string",
        "title": "API Base URL",
        "description": "Your Custom Service API URL",
        "required": true,
        "format": "uri",
        "prompt": {
          "message": "Enter Custom Service API URL:",
          "placeholder": "https://api.example.com"
        }
      },
      "api_token": {
        "type": "string",
        "title": "API Token",
        "description": "API Token for authentication",
        "required": true,
        "secret": true,
        "prompt": {
          "message": "Enter API Token:",
          "type": "password"
        }
      }
    }
  },

  "security": {
    "checksum": null,
    "signature": null
  }
}
```

### Paso 11: Escribir Tests

**`tests/test_plugin.py`:**

```python
import pytest
from titan_plugin_custom.plugin import CustomPlugin


def test_plugin_metadata():
    """Test plugin basic metadata."""
    plugin = CustomPlugin()

    assert plugin.name == "custom"
    assert plugin.version == "1.0.0"
    assert plugin.description != ""


def test_plugin_steps():
    """Test plugin provides expected steps."""
    plugin = CustomPlugin()
    steps = plugin.get_steps()

    assert "my_custom_step" in steps
    assert callable(steps["my_custom_step"])


def test_plugin_initialization(mocker):
    """Test plugin initialization with config."""
    plugin = CustomPlugin()

    # Mock config and secrets
    mock_config = mocker.MagicMock()
    mock_secrets = mocker.MagicMock()
    mock_secrets.get.return_value = "test-token"

    # Mock plugin config
    mock_plugin_config = mocker.MagicMock()
    mock_plugin_config.enabled = True
    mock_plugin_config.config = {"base_url": "https://api.test.com"}
    mock_config.config.plugins.get.return_value = mock_plugin_config

    # Initialize
    plugin.initialize(mock_config, mock_secrets)

    # Assert client is initialized
    assert plugin.is_available()
```

```bash
# Ejecutar tests
poetry run pytest
```

### Paso 12: Crear README Completo

**`README.md`:**

```markdown
# Titan Plugin - Custom Integration

Integration plugin for Titan CLI with Custom Service.

## Installation

### From PyPI (Marketplace)
\`\`\`bash
pipx inject titan-cli titan-plugin-custom
\`\`\`

### From Source
\`\`\`bash
git clone https://github.com/user/titan-plugin-custom.git
cd titan-plugin-custom
poetry build
pipx inject titan-cli ./dist/titan_plugin_custom-1.0.0-py3-none-any.whl
\`\`\`

## Configuration

\`\`\`bash
titan plugins configure custom
\`\`\`

Or manually in `~/.titan/config.toml`:

\`\`\`toml
[plugins.custom]
enabled = true

  [plugins.custom.config]
  base_url = "https://api.example.com"
\`\`\`

Set API token as secret:
\`\`\`bash
export CUSTOM_API_TOKEN="your-token"
\`\`\`

## Usage

### Available Steps

#### \`my_custom_step\`
Executes custom operation.

**Example workflow:**
\`\`\`yaml
steps:
  - id: custom_op
    plugin: custom
    step: my_custom_step
\`\`\`

## Development

\`\`\`bash
# Install dependencies
poetry install

# Run tests
poetry run pytest

# Build
poetry build
\`\`\`

## License

MIT
```

### Paso 13: Publicar a PyPI

```bash
# 1. Crear cuenta en PyPI (si no tienes)
# https://pypi.org/account/register/

# 2. Configurar token en Poetry
poetry config pypi-token.pypi <your-pypi-token>

# 3. Publicar
poetry publish --build

# Tu plugin ahora está en PyPI!
# https://pypi.org/project/titan-plugin-custom/
```

### Paso 14: Fork Marketplace Repository

```bash
# 1. Fork en GitHub
# https://github.com/masmovil/titan-cli-marketplace → Fork

# 2. Clonar tu fork
git clone https://github.com/tu-usuario/titan-cli-marketplace.git
cd titan-cli-marketplace
```

### Paso 15: Añadir Plugin al Registry

**Editar `registry.json`:**

```bash
# Calcular checksum del plugin
sha256sum dist/titan_plugin_custom-1.0.0-py3-none-any.whl
# Resultado: abc123def456...
```

```json
{
  "version": "1.0.0",
  "last_updated": "2026-01-14T12:00:00Z",
  "plugins": {
    "custom": {
      "display_name": "Custom Integration",
      "description": "Integration with Custom Service",
      "latest_version": "1.0.0",
      "source": "https://github.com/tu-usuario/titan-plugin-custom",
      "pypi_package": "titan-plugin-custom",
      "category": "community",
      "verified": false,
      "tags": ["integration", "api"],
      "security": {
        "checksum": "sha256:abc123def456...",
        "last_audit": null
      },
      "stats": {
        "downloads": 0,
        "rating": null
      },
      "pending_review": true,
      "submitted_by": "email@example.com",
      "submitted_at": "2026-01-14T12:00:00Z"
    }
  }
}
```

### Paso 16: Copiar Plugin al Marketplace

```bash
# Crear directorio para tu plugin
mkdir -p plugins/titan-plugin-custom

# Copiar archivos necesarios
cp -r ../titan-plugin-custom/{plugin.json,README.md,LICENSE} plugins/titan-plugin-custom/
```

### Paso 17: Crear Pull Request

```bash
# Commit cambios
git checkout -b add-custom-plugin
git add registry.json plugins/titan-plugin-custom/
git commit -m "feat: add Custom Integration plugin

- Integration with Custom Service API
- Workflow steps for custom operations
- Full test coverage
- PyPI package: titan-plugin-custom==1.0.0"

# Push a tu fork
git push origin add-custom-plugin
```

**Crear PR en GitHub:**
1. Ve a `https://github.com/masmovil/titan-cli-marketplace`
2. Click "Compare & pull request"
3. Llena el template del PR:

```markdown
## Plugin Submission: Custom Integration

### Plugin Information
- **Name**: custom
- **Display Name**: Custom Integration
- **Version**: 1.0.0
- **Category**: Community
- **PyPI Package**: https://pypi.org/project/titan-plugin-custom/

### Description
Integration plugin for Custom Service API.

### Features
- Custom API client
- Workflow steps for operations
- Dynamic configuration via JSON Schema

### Testing
- ✅ All tests passing (pytest)
- ✅ Successfully installed with `pipx inject`
- ✅ Tested in workflows

### Checklist
- [x] `plugin.json` manifest included
- [x] README.md with usage instructions
- [x] Tests with >80% coverage
- [x] Published to PyPI
- [x] Checksum calculated and included
- [x] License included (MIT)

### Additional Notes
This is a community plugin for integration with Custom Service.
```

### Paso 18: Proceso de Revisión (Equipo Titan)

**El equipo Titan revisará:**

1. **Código del plugin** (en tu repo GitHub)
   - ✅ Sigue el patrón de `TitanPlugin`
   - ✅ Tests con buena cobertura
   - ✅ Sin vulnerabilidades de seguridad
   - ✅ Documentación completa

2. **Metadata del marketplace**
   - ✅ `plugin.json` bien formado
   - ✅ Checksum correcto
   - ✅ PyPI package accesible

3. **Prueba de instalación**
   ```bash
   pipx inject titan-cli titan-plugin-custom
   titan plugins info custom
   ```

**Posibles resultados:**

- ✅ **Aprobado**: Plugin pasa a `verified: true` y se mergea
- ⚠️  **Cambios solicitados**: Se pide corregir issues
- ❌ **Rechazado**: No cumple estándares (raro)

### Paso 19: Post-Aprobación

Una vez mergeado el PR:

```json
{
  "custom": {
    "category": "community",
    "verified": true,  // ← Cambiado por equipo Titan
    "security": {
      "checksum": "sha256:abc123...",
      "last_audit": "2026-01-14"  // ← Fecha de aprobación
    },
    "pending_review": false  // ← Ya no está pendiente
  }
}
```

**Tu plugin ya está en el marketplace oficial!** 🎉

Usuarios pueden instalarlo con:
```bash
titan plugins discover
# → Aparece "Custom Integration" en la lista

# O directamente
pipx inject titan-cli titan-plugin-custom
```

---

## 📊 Comparación: Local vs Marketplace

| Aspecto | Local | Marketplace |
|---------|-------|-------------|
| **Tiempo** | 30 min | 1-2 semanas |
| **Aprobación** | ❌ No requerida | ✅ Revisión de código |
| **Publicación** | ❌ No necesaria | ✅ PyPI + GitHub |
| **Descubrimiento** | Manual | `titan plugins discover` |
| **Actualizaciones** | Manual | `pipx upgrade` |
| **Visibilidad** | Privada | Pública |
| **Ideal para** | Plugins internos, custom | Plugins compartidos |

---

## 🔥 Ejemplo Real: Plugin JIRA

Puedes ver un ejemplo completo en:
```
plugins/titan-plugin-jira/
├── pyproject.toml              # Entry point configurado
├── plugin.json                 # Manifest completo
├── README.md                   # Documentación
├── titan_plugin_jira/
│   ├── plugin.py               # JiraPlugin(TitanPlugin)
│   ├── client.py               # JiraClient
│   ├── models.py               # Pydantic models
│   ├── steps/                  # Workflow steps
│   └── agents/                 # JiraAgent (AI)
└── tests/
    └── test_plugin.py
```

---

## 🎯 Resumen de Pasos

### Para Plugin Local (Solo Desarrollo)
1. Crear estructura con Poetry
2. Implementar `TitanPlugin` class
3. Configurar entry point en `pyproject.toml`
4. Build: `poetry build`
5. Instalar: `pipx inject titan-cli ./dist/*.whl`

### Para Plugin Marketplace (Publicación)
1. **Todo lo anterior +**
2. Crear `plugin.json` manifest
3. Escribir tests completos
4. Publicar a PyPI: `poetry publish`
5. Fork marketplace repo
6. Añadir a `registry.json`
7. Crear PR con metadata
8. **Esperar revisión del equipo Titan**
9. ✅ Merge → Plugin oficial

---

## ❓ FAQ

**Q: ¿Puedo crear un plugin sin subirlo a PyPI?**
A: Sí, usa instalación local con ruta o wheel.

**Q: ¿Cuánto tarda la revisión del marketplace?**
A: 1-2 semanas típicamente (depende de complejidad).

**Q: ¿Qué pasa si mi plugin es rechazado?**
A: Recibes feedback de qué corregir. Puedes volver a enviar.

**Q: ¿Puedo actualizar un plugin ya en marketplace?**
A: Sí, publicas nueva versión a PyPI y actualizas `registry.json`.

**Q: ¿Los plugins locales pueden usar el mismo `configSchema`?**
A: Sí, aunque el wizard solo funciona si implementas `get_config_schema()`.

---

**Versión:** 1.0.0
**Creado:** 2026-01-14
**Actualizado:** 2026-01-14
