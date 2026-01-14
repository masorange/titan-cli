# Release Workflow Specification

> **Status**: 📋 Specification (Not Implemented)
> **Priority**: High
> **Estimated Effort**: 2-3 days

---

## 🎯 Objetivo

Automatizar el proceso completo de release de Titan CLI mediante un workflow que:

1. **Genera documentación** de la versión (CHANGELOG.md) usando IA
2. **Crea git tag** con la versión correspondiente
3. **Construye packages** (wheel + tarball)
4. **Valida instalación** con pipx
5. **Crea GitHub Release** con assets adjuntos
6. **Publica distribución** (opcional: PyPI)

---

## 📋 Workflow Propuesto

### Nombre del Workflow
`release-version.yaml`

### Ubicación
`.titan/workflows/release-version.yaml`

### Parámetros de Entrada

```yaml
params:
  version: null          # e.g., "1.0.0", "1.1.0", "2.0.0-beta.1"
  release_type: "stable" # stable | beta | alpha
  skip_validation: false # Skip pipx installation validation
  skip_tests: false      # Skip test suite (not recommended)
  publish_pypi: false    # Publish to PyPI (requires credentials)
  draft: false           # Create GitHub release as draft
```

---

## 🔧 Estructura del Workflow

### Step 1: Validación Previa

**ID**: `validate_preconditions`
**Tipo**: Custom Step
**Descripción**: Verifica que se cumplen las condiciones para hacer release

**Verificaciones**:
- ✅ Branch actual es `master` o `main`
- ✅ Working directory está limpio (no hay cambios uncommitted)
- ✅ Todos los tests pasan
- ✅ Version en `pyproject.toml` coincide con parámetro `version`
- ✅ No existe tag con esa versión
- ✅ GitHub token configurado (para crear release)

**Salida**:
```python
{
  "can_proceed": bool,
  "issues": list[str],
  "warnings": list[str]
}
```

---

### Step 2: Generación de CHANGELOG con IA

**ID**: `ai_generate_changelog`
**Tipo**: AI Step (nuevo plugin o step del git plugin)
**Descripción**: Usa IA para generar CHANGELOG.md basado en commits desde última versión

#### Implementación Sugerida

**Agente IA**: `ChangelogGeneratorAgent`

**Inputs**:
- Commits desde último tag hasta HEAD
- Tipo de release (stable/beta/alpha)
- Template de CHANGELOG existente (si existe)
- PRs merged desde último release

**Prompt Template**:
```jinja2
You are a technical writer creating a CHANGELOG.md for version {{ version }}.

## Context
- **Project**: Titan CLI (Python CLI tool)
- **Version**: {{ version }}
- **Release Type**: {{ release_type }}
- **Previous Version**: {{ previous_version }}

## Commits Since Last Release
{{ commits }}

## Merged Pull Requests
{{ pull_requests }}

## Instructions
Generate a CHANGELOG.md entry following Keep a Changelog format:
- Group changes by type: Features, Bug Fixes, Refactoring, Documentation, Breaking Changes
- Use clear, user-friendly language
- Include PR/issue references where applicable
- Highlight breaking changes prominently
- Add migration guide if needed

## Format
```markdown
## [{{ version }}] - {{ date }}

### ✨ Features
- Feature 1 (#123)

### 🐛 Bug Fixes
- Fix 1 (#124)

### 🔄 Refactoring
- Refactor 1 (#125)

### 📚 Documentation
- Docs update (#126)

### 🚨 Breaking Changes
- Breaking change description

### 🔧 Migration Guide
Steps to migrate from {{ previous_version }}...
```

**Output**:
```python
{
  "changelog_content": str,
  "breaking_changes": list[str],
  "migration_needed": bool
}
```

**Step Actions**:
1. Leer CHANGELOG.md existente (si existe)
2. Generar nuevo entry con IA
3. Insertar entry al principio del CHANGELOG
4. Actualizar enlace [Unreleased] si existe
5. Guardar archivo

---

### Step 3: Actualizar Version en pyproject.toml (opcional)

**ID**: `update_version`
**Tipo**: Custom Step
**Descripción**: Actualiza version en pyproject.toml si no coincide con parámetro

**Implementación**:
```python
import tomli
import tomli_w

def update_version_step(ctx: WorkflowContext) -> WorkflowResult:
    version = ctx.params["version"]
    pyproject_path = Path("pyproject.toml")

    with open(pyproject_path, "rb") as f:
        data = tomli.load(f)

    current_version = data["tool"]["poetry"]["version"]

    if current_version == version:
        return Skip(message=f"Version already set to {version}")

    data["tool"]["poetry"]["version"] = version

    with open(pyproject_path, "wb") as f:
        tomli_w.dump(data, f)

    return Success(
        message=f"Updated version: {current_version} → {version}",
        metadata={"old_version": current_version, "new_version": version}
    )
```

---

### Step 4: Ejecutar Test Suite

**ID**: `run_tests`
**Tipo**: Custom Step (pytest runner)
**Descripción**: Ejecuta todos los tests antes de proceder

**Configuración**:
```yaml
- id: run_tests
  name: "Run Test Suite"
  skip_if: params.skip_tests == true
  command: "poetry run pytest --tb=short -q"
  fail_on_error: true
```

---

### Step 5: Build Distribution Packages

**ID**: `build_packages`
**Tipo**: Custom Step
**Descripción**: Construye wheel y tarball

**Implementación**:
```python
def build_packages_step(ctx: WorkflowContext) -> WorkflowResult:
    # Clean previous build
    shutil.rmtree("dist", ignore_errors=True)

    # Build with poetry
    result = subprocess.run(
        ["poetry", "build"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        return Error(f"Build failed: {result.stderr}")

    # Get package info
    dist_files = list(Path("dist").glob("*"))
    wheel = next((f for f in dist_files if f.suffix == ".whl"), None)
    tarball = next((f for f in dist_files if f.suffix == ".gz"), None)

    return Success(
        message=f"Built {len(dist_files)} packages",
        metadata={
            "wheel": str(wheel),
            "tarball": str(tarball),
            "wheel_size": wheel.stat().st_size if wheel else 0,
            "tarball_size": tarball.stat().st_size if tarball else 0
        }
    )
```

---

### Step 6: Validar Instalación con pipx

**ID**: `validate_installation`
**Tipo**: Custom Step
**Descripción**: Valida que el package se instala correctamente

**Implementación**:
```python
def validate_installation_step(ctx: WorkflowContext) -> WorkflowResult:
    wheel_path = ctx.context.get("build_packages", {}).get("wheel")

    if not wheel_path:
        return Error("No wheel found to validate")

    # Uninstall if exists
    subprocess.run(["pipx", "uninstall", "titan-cli"], capture_output=True)

    # Install from wheel
    result = subprocess.run(
        ["pipx", "install", wheel_path],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        return Error(f"Installation failed: {result.stderr}")

    # Verify command works
    result = subprocess.run(
        ["titan", "version"],
        capture_output=True,
        text=True
    )

    if ctx.params["version"] not in result.stdout:
        return Error(f"Version mismatch in installed package")

    return Success(
        message="Installation validated successfully",
        metadata={"installed_version": result.stdout.strip()}
    )
```

---

### Step 7: Commit Changes

**ID**: `commit_changes`
**Tipo**: Git Step
**Descripción**: Commitea CHANGELOG y pyproject.toml (si se actualizó)

**Configuración**:
```yaml
- id: commit_changes
  name: "Commit Release Preparation"
  plugin: git
  step: create_commit
  params:
    message: |
      chore: prepare release v{{ params.version }}

      - Updated CHANGELOG.md with release notes
      - Version bumped to {{ params.version }}

      Co-Authored-By: Claude <noreply@anthropic.com>
    files:
      - CHANGELOG.md
      - pyproject.toml
```

---

### Step 8: Crear Git Tag

**ID**: `create_git_tag`
**Tipo**: Git Step
**Descripción**: Crea tag anotado con la versión

**Implementación**:
```python
def create_git_tag_step(ctx: WorkflowContext) -> WorkflowResult:
    version = ctx.params["version"]
    tag_name = f"v{version}"

    # Check if tag exists
    result = subprocess.run(
        ["git", "tag", "-l", tag_name],
        capture_output=True,
        text=True
    )

    if result.stdout.strip():
        return Error(f"Tag {tag_name} already exists")

    # Create annotated tag
    tag_message = f"Release Titan CLI v{version}"

    result = subprocess.run(
        ["git", "tag", "-a", tag_name, "-m", tag_message],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        return Error(f"Failed to create tag: {result.stderr}")

    return Success(
        message=f"Created tag {tag_name}",
        metadata={"tag": tag_name, "message": tag_message}
    )
```

---

### Step 9: Push Tag to Remote

**ID**: `push_tag`
**Tipo**: Git Step
**Descripción**: Push tag a GitHub

**Implementación**:
```python
def push_tag_step(ctx: WorkflowContext) -> WorkflowResult:
    version = ctx.params["version"]
    tag_name = f"v{version}"

    result = subprocess.run(
        ["git", "push", "origin", tag_name],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        return Error(f"Failed to push tag: {result.stderr}")

    return Success(
        message=f"Pushed tag {tag_name} to origin",
        metadata={"tag": tag_name}
    )
```

---

### Step 10: Crear GitHub Release

**ID**: `create_github_release`
**Tipo**: GitHub Step (nuevo)
**Descripción**: Crea GitHub Release y sube assets

**Implementación usando `gh` CLI**:
```python
def create_github_release_step(ctx: WorkflowContext) -> WorkflowResult:
    version = ctx.params["version"]
    tag_name = f"v{version}"
    wheel = ctx.context.get("build_packages", {}).get("wheel")
    tarball = ctx.context.get("build_packages", {}).get("tarball")

    # Get CHANGELOG entry for this version
    changelog_entry = extract_changelog_entry(version)

    # Build release notes
    release_notes = f"""# Titan CLI v{version}

{changelog_entry}

## 📦 Installation

```bash
pipx install https://github.com/masmovil/titan-cli/releases/download/{tag_name}/titan_cli-{version}-py3-none-any.whl
```

See [INSTALLATION.md](INSTALLATION.md) for complete instructions.
"""

    # Create release
    cmd = [
        "gh", "release", "create", tag_name,
        "--title", f"v{version} - Release",
        "--notes", release_notes
    ]

    if ctx.params["draft"]:
        cmd.append("--draft")

    if ctx.params["release_type"] == "beta":
        cmd.append("--prerelease")

    # Add assets
    cmd.extend([wheel, tarball])

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        return Error(f"Failed to create release: {result.stderr}")

    release_url = result.stdout.strip()

    return Success(
        message=f"Created GitHub release {tag_name}",
        metadata={
            "release_url": release_url,
            "tag": tag_name,
            "assets": [wheel, tarball]
        }
    )
```

---

### Step 11: Publicar a PyPI (opcional)

**ID**: `publish_pypi`
**Tipo**: Custom Step
**Descripción**: Publica package a PyPI si `publish_pypi=true`

**Implementación**:
```python
def publish_pypi_step(ctx: WorkflowContext) -> WorkflowResult:
    if not ctx.params.get("publish_pypi"):
        return Skip("PyPI publishing not requested")

    # Requires PYPI_TOKEN in secrets
    token = ctx.secrets.get("PYPI_TOKEN")
    if not token:
        return Error("PYPI_TOKEN not configured")

    result = subprocess.run(
        ["poetry", "publish", "--username", "__token__", "--password", token],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        return Error(f"PyPI publish failed: {result.stderr}")

    version = ctx.params["version"]

    return Success(
        message=f"Published to PyPI: https://pypi.org/project/titan-cli/{version}/",
        metadata={"pypi_url": f"https://pypi.org/project/titan-cli/{version}/"}
    )
```

---

## 🎨 Workflow Completo (YAML)

```yaml
name: "Release Version"
description: "Complete release workflow with AI-generated changelog, git tag, and GitHub release"

params:
  version: null
  release_type: "stable"
  skip_validation: false
  skip_tests: false
  publish_pypi: false
  draft: false

steps:
  # 1. Validación previa
  - id: validate_preconditions
    name: "Validate Release Preconditions"
    plugin: release
    step: validate_preconditions

  # 2. Generar CHANGELOG con IA
  - id: ai_generate_changelog
    name: "Generate CHANGELOG with AI"
    plugin: release
    step: ai_generate_changelog

  # 3. Actualizar version (si es necesario)
  - id: update_version
    name: "Update Version in pyproject.toml"
    plugin: release
    step: update_version

  # 4. Ejecutar tests
  - id: run_tests
    name: "Run Test Suite"
    skip_if: params.skip_tests
    command: "poetry run pytest --tb=short -q"

  # 5. Build packages
  - id: build_packages
    name: "Build Distribution Packages"
    plugin: release
    step: build_packages

  # 6. Validar instalación
  - id: validate_installation
    name: "Validate Installation with pipx"
    skip_if: params.skip_validation
    plugin: release
    step: validate_installation

  # 7. Commit cambios
  - id: commit_changes
    name: "Commit Release Preparation"
    plugin: git
    step: create_commit
    params:
      message: "chore: prepare release v{{ params.version }}"
      files: ["CHANGELOG.md", "pyproject.toml"]

  # 8. Push commit
  - id: push_commit
    name: "Push Commit"
    plugin: git
    step: push

  # 9. Crear tag
  - id: create_tag
    name: "Create Git Tag"
    plugin: release
    step: create_git_tag

  # 10. Push tag
  - id: push_tag
    name: "Push Tag to Remote"
    plugin: release
    step: push_tag

  # 11. Crear GitHub Release
  - id: create_github_release
    name: "Create GitHub Release"
    plugin: release
    step: create_github_release

  # 12. Publicar a PyPI (opcional)
  - id: publish_pypi
    name: "Publish to PyPI"
    skip_if: "not params.publish_pypi"
    plugin: release
    step: publish_pypi
```

---

## 🔌 Nuevo Plugin: `titan-plugin-release`

### Estructura

```
plugins/titan-plugin-release/
├── pyproject.toml
├── plugin.json
└── titan_plugin_release/
    ├── __init__.py
    ├── plugin.py
    ├── agents/
    │   └── changelog_generator.py
    ├── steps/
    │   ├── validate_preconditions.py
    │   ├── ai_changelog.py
    │   ├── version_update.py
    │   ├── build_packages.py
    │   ├── validate_installation.py
    │   ├── git_tag.py
    │   └── github_release.py
    ├── models.py
    └── messages.py
```

### plugin.json

```json
{
  "name": "release",
  "version": "1.0.0",
  "description": "Automated release management with AI-powered changelog generation",
  "category": "official",
  "verified": true,
  "author": "Titan CLI Team",
  "entry_point": "titan_plugin_release.plugin:ReleasePlugin",
  "dependencies": ["git", "github"],
  "min_titan_version": "1.0.0",
  "configSchema": {
    "type": "object",
    "properties": {
      "default_release_type": {
        "type": "string",
        "enum": ["stable", "beta", "alpha"],
        "default": "stable",
        "description": "Default release type"
      },
      "always_validate_installation": {
        "type": "boolean",
        "default": true,
        "description": "Always validate with pipx before releasing"
      },
      "auto_publish_pypi": {
        "type": "boolean",
        "default": false,
        "description": "Automatically publish to PyPI"
      },
      "changelog_ai_model": {
        "type": "string",
        "enum": ["claude", "gemini"],
        "default": "claude",
        "description": "AI model for changelog generation"
      }
    }
  }
}
```

---

## 📝 Uso del Workflow

### Opción 1: Desde Menu Interactivo

```bash
titan menu
# Seleccionar "Workflows" > "Release Version"
# Ingresar versión: 1.1.0
# Confirmar parámetros
```

### Opción 2: CLI Directo (futuro)

```bash
titan workflow run release-version --version 1.1.0
titan workflow run release-version --version 2.0.0-beta.1 --release-type beta --draft
```

### Opción 3: Programático

```python
from titan_cli.engine import WorkflowEngine

engine = WorkflowEngine(config, secrets)
result = engine.run(
    "release-version",
    params={
        "version": "1.1.0",
        "release_type": "stable",
        "publish_pypi": True
    }
)
```

---

## 🧪 Testing del Workflow

### Unit Tests

```python
# tests/plugins/release/test_changelog_agent.py
def test_changelog_agent_generates_valid_markdown():
    agent = ChangelogGeneratorAgent(ai_client)
    commits = [...]
    result = agent.generate_changelog("1.1.0", commits)
    assert "## [1.1.0]" in result
    assert "### Features" in result

# tests/plugins/release/test_version_update.py
def test_version_update_step(tmp_path):
    result = update_version_step(ctx)
    assert result.success
    # Verify pyproject.toml updated

# tests/plugins/release/test_github_release.py
def test_create_github_release_step(mocker):
    mock_gh = mocker.patch("subprocess.run")
    result = create_github_release_step(ctx)
    assert result.success
    mock_gh.assert_called_once()
```

### Integration Tests

```bash
# Test completo en entorno de prueba
titan workflow run release-version \
  --version 1.0.0-test \
  --skip-validation \
  --draft \
  --dry-run
```

---

## 📅 Implementación Sugerida

### Fase 1: Core Steps (1 semana)
- [ ] Crear plugin base `titan-plugin-release`
- [ ] Implementar steps básicos (validate, build, version update)
- [ ] Tests unitarios

### Fase 2: AI Integration (3-5 días)
- [ ] Implementar `ChangelogGeneratorAgent`
- [ ] Diseñar prompt template óptimo
- [ ] Pruebas con diferentes tipos de releases

### Fase 3: GitHub Integration (2-3 días)
- [ ] Step para crear GitHub Release
- [ ] Upload de assets
- [ ] Manejo de pre-releases y drafts

### Fase 4: PyPI Integration (2 días)
- [ ] Step para publicar a PyPI
- [ ] Manejo de credenciales
- [ ] Rollback en caso de error

### Fase 5: Documentación y Testing (2 días)
- [ ] Documentación completa del workflow
- [ ] Tests de integración end-to-end
- [ ] Guía de troubleshooting

---

## 🔒 Seguridad

### Secrets Requeridos

```yaml
# .titan/secrets.env
GITHUB_TOKEN=ghp_xxxxx  # Para crear releases
PYPI_TOKEN=pypi-xxxxx   # Para publicar (opcional)
```

### Permisos de GitHub Token

- `repo` - Full control of private repositories
- `workflow` - Update GitHub Action workflows

---

## 🚨 Manejo de Errores

### Rollback Strategy

Si falla después de crear el tag:
```bash
git tag -d v1.1.0
git push origin :refs/tags/v1.1.0
```

Si falla después de crear GitHub Release:
```bash
gh release delete v1.1.0 --yes
```

Si falla publicación a PyPI:
- No hay rollback automático
- Versión queda publicada
- Necesario incrementar versión (ej: 1.1.0 → 1.1.1)

---

## 📊 Métricas y Monitoreo

### Métricas a Trackear

- Tiempo total del workflow
- Éxito/fallo por step
- Tamaño de packages generados
- Tiempo de validación con pipx
- Calidad de CHANGELOG generado (manual review)

---

## 🎯 Próximos Pasos

1. **Revisar esta especificación** con el equipo
2. **Crear issue en GitHub** con checklist de implementación
3. **Priorizar en roadmap** (sugerencia: después de v1.0.0 release)
4. **Asignar developer** para implementación
5. **Crear branch** `feat/release-workflow`

---

**Documento creado**: 2026-01-14
**Versión**: 1.0
**Autor**: Claude + r-pedraza
