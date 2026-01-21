# Guía de Instalación y Uso - Titan CLI

**Versión**: v0.1.0
**Fecha**: 2026-01-20

---

## ✅ Instalación Completada

Titan CLI ya está instalado globalmente con pipx y puede ejecutarse desde cualquier directorio.

### Ubicaciones:

```bash
# Comando titan
which titan
# → /Users/rpedraza/.local/bin/titan

# Entorno virtual de pipx
~/.local/pipx/venvs/titan-cli/

# Plugins instalados
~/.local/pipx/venvs/titan-cli/lib/python3.13/site-packages/
├── titan_plugin_git/
├── titan_plugin_github/
└── titan_plugin_jira/
```

---

## 🚀 Cómo Usar Titan CLI

### Modelo Basado en Proyectos

**IMPORTANTE**: Titan CLI ahora funciona con un modelo basado en proyectos. Debes ejecutarlo **desde el directorio del proyecto**:

```bash
# ✅ CORRECTO
cd /Users/rpedraza/Documents/MasMovil/ragnarok-ios
titan  # Lanza el TUI

# ❌ INCORRECTO
cd /Users/rpedraza/Documents/MasMovil/titan-cli
titan  # No encontrará los workflows del proyecto
```

### Comandos Principales

#### 1. **Lanzar el TUI (Textual Interface)**

```bash
cd /Users/rpedraza/Documents/MasMovil/ragnarok-ios
titan  # O titan tui
```

**Qué hace**:
- Muestra menú interactivo con todas las opciones
- Permite ejecutar workflows
- Configurar plugins
- Gestionar AI providers

#### 2. **Ejecutar Workflow (desde TUI)**

```bash
cd /Users/rpedraza/Documents/MasMovil/ragnarok-ios
titan  # Abre TUI
# Navegar con flechas → Seleccionar "Workflows" → "release-notes-ios"
```

#### 3. **Modo Legacy (Rich Menu)**

```bash
cd /Users/rpedraza/Documents/MasMovil/ragnarok-ios
titan menu
```

**Nota**: El modo legacy todavía usa el sistema antiguo de configuración.

#### 4. **Comandos de Configuración**

```bash
# Ver versión
titan version

# Configurar AI providers
titan ai

# Gestionar plugins
titan plugins

# Inicializar configuración global
titan init
```

---

## 📁 Estructura de Configuración

### Global Config (`~/.titan/config.toml`)

**Solo almacena configuración de AI providers** (compartida entre proyectos):

```toml
[ai.providers.default]
name = "My Claude"
type = "individual"
provider = "anthropic"
model = "claude-sonnet-4-5"

[ai]
default = "default"
```

### Project Config (`.titan/config.toml` en cada proyecto)

**Configuración específica del proyecto** (plugins, JIRA, GitHub):

```toml
# ragnarok-ios/.titan/config.toml
[project]
name = "ragnarok-ios"
type = "generic"

[plugins.github]
enabled = true
[plugins.github.config]
repo_owner = "masmovil"
repo_name = "ragnarok-ios"

[plugins.jira]
enabled = true
[plugins.jira.config]
base_url = "https://jiranext.masorange.es"
email = "raul.pedraza@masmovil.com"
default_project = "ECAPP"

[plugins.git]
enabled = true
[plugins.git.config]
protected_branches = ["develop"]
```

### Project Workflows (`.titan/workflows/*.yaml`)

**Workflows específicos del proyecto**:

```yaml
# ragnarok-ios/.titan/workflows/release-notes-ios.yaml
name: "Generate Release Notes (iOS)"
description: "Generate multi-brand weekly release notes..."

params:
  project_key: "ECAPP"
  platform: "iOS"
  notes_directory: "ReleaseNotes"

steps:
  - id: list_versions
    plugin: jira
    step: list_versions
    # ... etc
```

---

## 🎯 Ejemplo Completo: Generar Release Notes

### Para Ragnarok iOS

```bash
# 1. Ir al proyecto
cd /Users/rpedraza/Documents/MasMovil/ragnarok-ios

# 2. Verificar que existe la configuración
ls -la .titan/config.toml
ls -la .titan/workflows/release-notes-ios.yaml

# 3. Lanzar Titan
titan

# 4. En el TUI:
#    - Navegar con ↑↓ a "Workflows"
#    - Presionar Enter
#    - Seleccionar "release-notes-ios"
#    - Presionar Enter
#    - Seguir las instrucciones en pantalla

# 5. El workflow:
#    - Listará versiones de JIRA
#    - Pedirá seleccionar versión (ej: 26.4.0)
#    - Creará branch: release-notes/26.4.0
#    - Consultará issues de JIRA
#    - Generará release notes con AI
#    - Mostrará preview y pedirá confirmación
#    - Creará archivo: ReleaseNotes/release-notes-26.4.0.md
#    - Hará commit y push
#    - Creará Pull Request
```

### Para Ragnarok Android

```bash
# 1. Ir al proyecto
cd /Users/rpedraza/Documents/MasMovil/ragnarok-android

# 2. Lanzar Titan
titan

# 3. Ejecutar workflow "release-notes-android"
#    - Crea archivo en: docs/release-notes/release-notes-26.4.0.md
```

---

## 🔄 Actualizar Titan CLI

Cuando hagas cambios en el código de titan-cli:

```bash
cd /Users/rpedraza/Documents/MasMovil/titan-cli

# Reinstalar titan-cli
pipx install --force .

# Reinstalar plugins
pipx inject --force titan-cli \
  ./plugins/titan-plugin-git \
  ./plugins/titan-plugin-github \
  ./plugins/titan-plugin-jira

# Verificar
titan version
```

---

## 🐛 Troubleshooting

### "No workflows found"

**Causa**: No estás en el directorio del proyecto o falta `.titan/workflows/`

**Solución**:
```bash
# Verificar ubicación
pwd
# Debe ser: /Users/rpedraza/Documents/MasMovil/ragnarok-ios

# Verificar workflows
ls -la .titan/workflows/
```

### "Plugin not initialized"

**Causa**: Falta configuración del plugin en `.titan/config.toml`

**Solución**:
```bash
# Verificar config
cat .titan/config.toml

# Debe tener:
# [plugins.jira]
# enabled = true
```

### "JIRA authentication failed"

**Causa**: Falta JIRA_API_TOKEN

**Solución**:
```bash
# Configurar token
titan menu  # O titan ai
# Seguir wizard de configuración
```

### "Command not found: titan"

**Causa**: PATH no incluye ~/.local/bin

**Solución**:
```bash
# Verificar PATH
echo $PATH | grep -q ".local/bin" && echo "✅ OK" || echo "❌ Falta .local/bin"

# Agregar a PATH (si falta)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

---

## 📊 Comparación: Antes vs Ahora

### Antes (versión antigua)

```bash
# Configuración global con active_project
~/.titan/config.toml:
  [core]
  project_root = "/Users/rpedraza/Documents/MasMovil"
  active_project = "ragnarok-ios"

# Ejecutar desde cualquier lugar
cd /tmp
titan workflow run release-notes-ios  # Funcionaba
```

### Ahora (v0.2.0 - PR #110)

```bash
# Sin configuración global de proyectos
~/.titan/config.toml:
  [ai.providers.default]
  provider = "anthropic"

# Cada proyecto tiene su config
ragnarok-ios/.titan/config.toml:
  [project]
  name = "ragnarok-ios"

# DEBES estar en el proyecto
cd /Users/rpedraza/Documents/MasMovil/ragnarok-ios
titan  # ✅ Funciona

cd /tmp
titan  # ❌ No encuentra workflows
```

---

## 🎓 Recursos

- **Documentación**: `/Users/rpedraza/Documents/MasMovil/titan-cli/CLAUDE.md`
- **Ejemplos de workflows**: `/Users/rpedraza/Documents/MasMovil/titan-cli/examples/`
- **Setup de proyectos**: `/Users/rpedraza/Documents/MasMovil/titan-cli/SETUP_RAGNAROK_PROJECTS.md`

---

## ✅ Checklist de Verificación

Antes de usar Titan en un proyecto:

- [ ] Existe `.titan/config.toml` en el proyecto
- [ ] Existe `.titan/workflows/*.yaml` en el proyecto
- [ ] Plugins habilitados en `.titan/config.toml`
- [ ] Secrets configurados (JIRA_API_TOKEN, GITHUB_TOKEN, ANTHROPIC_API_KEY)
- [ ] Estás en el directorio correcto (`pwd` muestra el proyecto)
- [ ] `titan version` funciona

---

**Actualizado**: 2026-01-20
**Por**: Instalación con pipx
**Versión de Titan**: v0.1.0
