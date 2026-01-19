# Release Notes Workflow - Guía de Implementación

Guía completa para implementar el workflow automatizado de release notes en proyectos Ragnarok (iOS y Android).

---

## 📋 Resumen

El workflow automatiza:

1. ✅ **Gestión de rama Git** - Crea/cambia a rama `release-notes/{version}` desde `develop`
2. ✅ **Consulta JIRA** - Busca issues del fixVersion usando queries centralizadas
3. ✅ **Generación AI** - Crea release notes multi-brand en español
4. ✅ **Creación de archivos** - Genera `.md` siguiendo nomenclatura del proyecto
5. ✅ **Actualización iOS** - Modifica `LatestPublishers.md` con versión y usuario
6. ✅ **Commit automático** - Commitea cambios con mensaje estándar

---

## 🚀 Implementación por Proyecto

### Paso 1: Copiar Workflow al Proyecto

**Para iOS:**
```bash
cd /path/to/ragnarok-ios
mkdir -p .titan/workflows
cp /path/to/titan-cli/examples/ragnarok-ios-release-notes-workflow.yaml \
   .titan/workflows/generate-release-notes.yaml
```

**Para Android:**
```bash
cd /path/to/ragnarok-android
mkdir -p .titan/workflows
cp /path/to/titan-cli/examples/ragnarok-android-release-notes-workflow.yaml \
   .titan/workflows/generate-release-notes.yaml
```

---

### Paso 2: Configurar Rutas del Proyecto

Editar `.titan/workflows/generate-release-notes.yaml` y actualizar parámetros:

```yaml
params:
  project_key: "ECAPP"
  platform: "iOS"  # o "Android"
  notes_directory: "docs/release-notes/ios"  # ⚠️ ACTUALIZAR con ruta real
```

**Cómo encontrar la ruta correcta:**

```bash
# Buscar directorios de release notes
find . -type d -name "*release*" -o -name "*ReleaseNotes*"

# Buscar archivos .md de release notes existentes
find . -name "release-notes-*.md"
```

---

### Paso 3: Configurar LatestPublishers.md (Solo iOS)

**Ubicación típica:** `docs/LatestPublishers.md`

**Formato esperado:**
```markdown
# Latest Publishers

| Publisher | Latest Version |
|-----------|----------------|
| John Doe  | [4 - 26.4.0]   |
| Jane Smith| [3 - 26.3.0]   |
```

El workflow actualizará automáticamente la línea del usuario que ejecuta el comando.

**Verificar nombre de usuario Git:**
```bash
git config user.name
# Debe coincidir con el nombre en LatestPublishers.md
```

---

## 🎯 Uso del Workflow

### Ejecución

```bash
cd /path/to/ragnarok-ios  # o ragnarok-android
titan workflow run generate-release-notes
```

O desde Claude Code:
```bash
/generate-release-notes
```

### Flujo Interactivo

1. **Seleccionar plataforma** → iOS o Android
2. **Listar versiones** → Muestra versiones unreleased de JIRA
3. **Seleccionar versión** → Menú numerado (1, 2, 3...)
4. **Crear/cambiar rama** → `release-notes/26.4.0`
5. **Buscar issues** → Query JIRA con fixVersion
6. **Generar notas** → AI transforma summaries a español
7. **Descubrir directorio** → Busca o usa configurado
8. **Crear archivo** → `release-notes-26.4.0.md`
9. **Actualizar LatestPublishers** → Solo iOS
10. **Commit** → `docs: Add release notes for 26.4.0`

---

## 📁 Estructura de Archivos Generados

### iOS

```
ragnarok-ios/
├── docs/
│   ├── release-notes/
│   │   └── ios/
│   │       └── release-notes-26.4.0.md  ✅ Nuevo
│   └── LatestPublishers.md              ✅ Actualizado
└── .titan/
    └── workflows/
        └── generate-release-notes.yaml
```

### Android

```
ragnarok-android/
├── docs/
│   └── release-notes/
│       └── android/
│           └── release-notes-26.4.0.md  ✅ Nuevo
└── .titan/
    └── workflows/
        └── generate-release-notes.yaml
```

---

## 🔧 Personalización del Workflow

### Cambiar Patrón de Nombre de Archivo

Editar step `create_notes_file`:

```yaml
- id: create_notes_file
  command: |
    # Cambiar patrón aquí
    FILENAME="release-notes-${fix_version}.md"  # Patrón actual
    # FILENAME="RN-${fix_version}.md"          # Alternativa
    # FILENAME="v${fix_version}-notes.md"      # Alternativa
```

### Cambiar Formato del Archivo

```yaml
- id: create_notes_file
  command: |
    cat > "$FILEPATH" << 'EOF'
# Release Notes ${fix_version} - iOS

**Fecha:** $(date +"%Y-%m-%d")
**Versión:** ${fix_version}
**Build:** TBD

## Cambios

${release_notes}

## Testing Notes

- Test on iOS 15+
- Verify brand-specific features

EOF
```

### Agregar Validaciones

```yaml
- id: validate_directory
  name: "Validate Directory Exists"
  command: |
    if [ ! -d "${notes_directory}" ]; then
      echo "ERROR: Directory ${notes_directory} does not exist"
      echo "Create it with: mkdir -p ${notes_directory}"
      exit 1
    fi
```

---

## 🐛 Troubleshooting

### Error: "Git client not available"

**Solución:**
```bash
# Verificar que Git está instalado
which git

# Verificar configuración de Titan
titan plugins list | grep git
```

### Error: "JIRA client not available"

**Solución:**
```bash
# Verificar configuración JIRA
titan plugins list | grep jira

# Verificar credenciales
cat ~/.titan/config.toml | grep jira
```

### Error: "No se encontró directorio de release notes"

**Solución:**
1. Buscar directorio real:
   ```bash
   find . -name "release-notes-*.md"
   ```

2. Actualizar parámetro en workflow:
   ```yaml
   params:
     notes_directory: "ruta/real/encontrada"
   ```

### Error: "LatestPublishers.md not found"

**Para iOS** (archivo requerido):
1. Crear archivo si no existe:
   ```bash
   mkdir -p docs
   cat > docs/LatestPublishers.md << 'EOF'
   # Latest Publishers

   | Publisher | Latest Version |
   |-----------|----------------|
   | $(git config user.name) | [0 - 0.0.0] |
   EOF
   ```

**Para Android** (archivo opcional):
- El workflow muestra WARNING pero continúa

### Rama incorrecta

Si el workflow crea rama desde rama incorrecta:

```bash
# Borrar rama incorrecta
git branch -D release-notes/26.4.0

# Cambiar a develop y actualizar
git checkout develop
git pull

# Ejecutar workflow de nuevo
```

---

## 📊 Ejemplo de Salida

### Archivo Generado (release-notes-26.4.0.md)

```markdown
# Release Notes 26.4.0 - iOS

**Fecha:** 2026-01-19
**Versión:** 26.4.0

*🟣 Yoigo*
- Bloqueado el acceso al recargador a usuarios pospago (ECAPP-12154)
- Añadida nueva sección de consentimientos (ECAPP-12058)

*🟡 MASMOVIL*
- Bloqueado el acceso al recargador a usuarios pospago (ECAPP-12154)
- Correcciones de textos (ECAPP-12215)

*🔴 Jazztel*
- Bloqueado el acceso al recargador a usuarios pospago (ECAPP-12154)
```

### LatestPublishers.md Actualizado

```markdown
# Latest Publishers

| Publisher | Latest Version |
|-----------|----------------|
| Roberto Pedraza | [4 - 26.4.0]   |  ✅ Actualizado
| Jane Smith     | [3 - 26.3.0]   |
```

### Commit Creado

```
commit abc1234567890def
Author: Roberto Pedraza <rpedraza@example.com>
Date:   Sun Jan 19 15:30:00 2026

    docs: Add release notes for 26.4.0

    - Created release-notes-26.4.0.md
    - Updated LatestPublishers.md (Week 4)
```

---

## 🔄 Integración con CI/CD

### GitHub Actions

```yaml
name: Generate Release Notes

on:
  workflow_dispatch:
    inputs:
      version:
        description: 'Fix Version (e.g., 26.4.0)'
        required: true

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Titan CLI
        run: |
          pip install titan-cli
          titan plugins install

      - name: Generate Release Notes
        run: |
          titan workflow run generate-release-notes
        env:
          JIRA_API_TOKEN: ${{ secrets.JIRA_API_TOKEN }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}

      - name: Create Pull Request
        uses: peter-evans/create-pull-request@v5
        with:
          branch: release-notes/${{ inputs.version }}
          title: "docs: Release notes for ${{ inputs.version }}"
```

---

## 📚 Referencias

- [Workflow Examples](../examples/) - Ejemplos completos de workflows
- [JIRA Plugin](../plugins/titan-plugin-jira/) - Plugin JIRA con steps
- [Git Plugin](../plugins/titan-plugin-git/) - Plugin Git con steps
- [Saved Queries](../plugins/titan-plugin-jira/titan_plugin_jira/utils/saved_queries.py) - JQLs centralizadas

---

## ✅ Checklist de Implementación

- [ ] Workflow copiado a `.titan/workflows/generate-release-notes.yaml`
- [ ] Parámetro `notes_directory` actualizado con ruta correcta
- [ ] Directorio de release notes existe en el proyecto
- [ ] (iOS) `LatestPublishers.md` existe y tiene formato correcto
- [ ] (iOS) Nombre de usuario Git coincide con LatestPublishers.md
- [ ] Plugins JIRA y Git configurados
- [ ] Credenciales JIRA disponibles
- [ ] API Key de AI configurada (Claude o Gemini)
- [ ] Probado workflow con versión de prueba
- [ ] Commit generado correctamente

---

**Última actualización:** 2026-01-19
**Versión:** 1.0.0
