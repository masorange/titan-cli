# Release Notes Workflow - Guía de Uso Paso a Paso

Guía práctica para usar el workflow de release notes desde Titan CLI.

---

## 🚀 Setup Inicial (Solo una vez por proyecto)

### Paso 1: Navegar al proyecto

```bash
# Para iOS
cd /Users/rpedraza/Documents/MasMovil/ragnarok-ios

# O para Android
cd /Users/rpedraza/Documents/MasMovil/ragnarok-android
```

### Paso 2: Copiar el workflow

**Opción A: Copiar manualmente**

```bash
# Crear directorio si no existe
mkdir -p .titan/workflows

# Copiar template correspondiente
# Para iOS:
cp /Users/rpedraza/Documents/MasMovil/titan-cli/examples/ragnarok-ios-release-notes-workflow.yaml \
   .titan/workflows/generate-release-notes.yaml

# Para Android:
cp /Users/rpedraza/Documents/MasMovil/titan-cli/examples/ragnarok-android-release-notes-workflow.yaml \
   .titan/workflows/generate-release-notes.yaml
```

**Opción B: Desde Titan CLI**

```bash
# Listar workflows disponibles en titan-cli
titan workflow list

# Copiar a proyecto local
titan workflow copy generate-release-notes-ios .titan/workflows/generate-release-notes.yaml
```

### Paso 3: Encontrar el directorio de release notes

```bash
# Buscar dónde están los archivos de release notes actuales
find . -name "release-notes-*.md" -o -name "ReleaseNotes*.md"

# Ejemplo de output:
# ./docs/release-notes/ios/release-notes-26.3.0.md
# ./docs/release-notes/ios/release-notes-26.2.0.md
```

**Toma nota de la ruta del directorio** (ejemplo: `docs/release-notes/ios`)

### Paso 4: Configurar el workflow

```bash
# Editar el workflow
vim .titan/workflows/generate-release-notes.yaml

# O con VS Code
code .titan/workflows/generate-release-notes.yaml
```

**Actualizar estos parámetros:**

```yaml
params:
  project_key: "ECAPP"           # ✅ Ya configurado
  platform: "iOS"                # ✅ Ya configurado (o "Android")
  notes_directory: "docs/release-notes/ios"  # ⚠️ CAMBIAR AQUÍ
```

**Reemplaza `docs/release-notes/ios` con la ruta que encontraste en el Paso 3.**

### Paso 5: Verificar LatestPublishers.md (Solo iOS)

```bash
# Buscar el archivo
find . -name "LatestPublishers.md"

# Ejemplo:
# ./docs/LatestPublishers.md

# Ver contenido
cat docs/LatestPublishers.md
```

**Debe tener este formato:**

```markdown
# Latest Publishers

| Publisher | Latest Version |
|-----------|----------------|
| Roberto Pedraza | [3 - 26.3.0]  |
| Otro Usuario    | [2 - 26.2.0]  |
```

**Verificar que tu nombre de Git coincide:**

```bash
git config user.name
# Debe aparecer en la tabla de LatestPublishers.md
```

Si no existe el archivo, créalo:

```bash
cat > docs/LatestPublishers.md << 'EOF'
# Latest Publishers

| Publisher | Latest Version |
|-----------|----------------|
| $(git config user.name) | [0 - 0.0.0] |
EOF
```

---

## ✅ Verificación del Setup

```bash
# 1. Verificar que el workflow existe
ls -la .titan/workflows/generate-release-notes.yaml

# 2. Verificar que Titan lo detecta
titan workflow list
# Debe aparecer "generate-release-notes" en la lista

# 3. Verificar plugins necesarios
titan plugins list
# Debe mostrar: jira, git (ambos con ✓)

# 4. Verificar configuración de JIRA
cat ~/.titan/config.toml | grep -A 5 "\[jira\]"

# 5. Verificar API key de AI
cat ~/.titan/config.toml | grep -A 3 "\[ai\]"
```

---

## 🎯 Uso del Workflow

### Opción 1: Desde Titan CLI

```bash
# Navegar al proyecto
cd /Users/rpedraza/Documents/MasMovil/ragnarok-ios

# Ejecutar workflow
titan workflow run generate-release-notes
```

### Opción 2: Desde Claude Code (Recomendado)

```bash
# Navegar al proyecto
cd /Users/rpedraza/Documents/MasMovil/ragnarok-ios

# Ejecutar skill
/generate-release-notes
```

---

## 📋 Flujo Interactivo Completo

### 1️⃣ Selección de Plataforma

```
┌─ Select Platform ──────────────────────────────────┐
│                                                     │
│ Select platform (iOS or Android)                   │
│                                                     │
│ 1. iOS                                              │
│ 2. Android                                          │
│                                                     │
│ Select option [1-2]:                                │
└─────────────────────────────────────────────────────┘
```

**Acción:** Escribe `1` (para iOS) o `2` (para Android) y presiona Enter

---

### 2️⃣ Listado de Versiones

```
┌─ List Available Versions ──────────────────────────┐
│                                                     │
│ Found 5 unreleased versions                        │
│                                                     │
│ Unreleased Versions:                               │
│   • 26.5.0 - Week 5 2026                           │
│   • 26.4.1 - Hotfix for 26.4.0                     │
│   • 26.4.0 - Week 4 2026                           │
│   • 26.3.1 - Hotfix for 26.3.0                     │
│   • 26.3.0 - Week 3 2026                           │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**El workflow busca automáticamente versiones unreleased en JIRA.**

---

### 3️⃣ Selección de Versión

```
┌─ Select Version ───────────────────────────────────┐
│                                                     │
│ Select from 5 unreleased versions                  │
│                                                     │
│ Select fixVersion                                  │
│                                                     │
│ 1. 26.5.0                                           │
│ 2. 26.4.1                                           │
│ 3. 26.4.0                                           │
│ 4. 26.3.1                                           │
│ 5. 26.3.0                                           │
│                                                     │
│ Select option [1-5]:                                │
└─────────────────────────────────────────────────────┘
```

**Acción:** Escribe el número de la versión que quieres (ejemplo: `3` para 26.4.0)

---

### 4️⃣ Gestión de Rama Git

```
┌─ Ensure Release Notes Branch ─────────────────────┐
│                                                     │
│ Target branch: release-notes/26.4.0                │
│                                                     │
│ Current branch: develop                            │
│                                                     │
│ Creating new release notes branch from develop...  │
│   1. Checking out develop...                       │
│   2. Pulling latest changes...                     │
│   3. Creating branch release-notes/26.4.0...       │
│   4. Checking out release-notes/26.4.0...          │
│                                                     │
│ ✓ Created and switched to release-notes/26.4.0    │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Automático - no requiere acción.**

**Si ya estás en la rama correcta:**

```
┌─ Ensure Release Notes Branch ─────────────────────┐
│                                                     │
│ Target branch: release-notes/26.4.0                │
│                                                     │
│ Current branch: release-notes/26.4.0               │
│                                                     │
│ ✓ Already on branch release-notes/26.4.0          │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

### 5️⃣ Búsqueda de Issues en JIRA

```
┌─ Search JIRA Issues ───────────────────────────────┐
│                                                     │
│ Executing JQL Query                                │
│   fixVersion = "26.4.0" AND project = ECAPP        │
│   Max results: 100                                 │
│                                                     │
│ Searching JIRA...                                  │
│                                                     │
│ ✓ Found 15 issues                                  │
│                                                     │
│ Issues Retrieved:                                  │
│   • ECAPP-12154: Bloquear recargador pospago       │
│   • ECAPP-12058: Nueva sección consentimientos     │
│   • ECAPP-12215: Correcciones de textos           │
│   ... and 12 more                                  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Automático - no requiere acción.**

---

### 6️⃣ Generación de Release Notes con AI

```
┌─ Generate Release Notes ──────────────────────────┐
│                                                     │
│ Processing 15 issues...                            │
│                                                     │
│ Grouping by brands...                              │
│   • Yoigo: 8 issues                                │
│   • MASMOVIL: 10 issues                            │
│   • Jazztel: 8 issues                              │
│   • Lycamobile: 2 issues                           │
│                                                     │
│ Generating AI descriptions...                      │
│   ✓ ECAPP-12154: Bloqueado el acceso al recarga... │
│   ✓ ECAPP-12058: Añadida nueva sección de cons... │
│   ✓ ECAPP-12215: Correcciones de textos           │
│   ...                                              │
│                                                     │
│ ✓ Release notes generated (1,234 characters)       │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Automático - la AI transforma los summaries a español.**

---

### 7️⃣ Creación de Archivo

```
┌─ Create Release Notes File ───────────────────────┐
│                                                     │
│ Using directory: docs/release-notes/ios           │
│                                                     │
│ Creating file: release-notes-26.4.0.md             │
│                                                     │
│ ✓ Created: docs/release-notes/ios/release-notes-26.4.0.md │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Automático - crea el archivo .md en el directorio configurado.**

---

### 8️⃣ Actualización de LatestPublishers (Solo iOS)

```
┌─ Update LatestPublishers.md (iOS Only) ───────────┐
│                                                     │
│ Detecting user: Roberto Pedraza                    │
│ Version week: 4                                    │
│                                                     │
│ Updating LatestPublishers.md...                    │
│                                                     │
│ ✓ Updated LatestPublishers.md for Roberto Pedraza (Week 4) │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Automático - actualiza la tabla con tu nombre y la versión.**

---

### 9️⃣ Commit de Cambios

```
┌─ Commit Release Notes ────────────────────────────┐
│                                                     │
│ Staging changes...                                 │
│   M docs/LatestPublishers.md                       │
│   A docs/release-notes/ios/release-notes-26.4.0.md│
│                                                     │
│ Creating commit...                                 │
│   Message: docs: Add release notes for 26.4.0     │
│                                                     │
│ ✓ Commit created: abc1234                          │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Automático - commitea los cambios con mensaje estándar.**

---

## 🎉 Resultado Final

### Archivos Creados/Modificados

```bash
# Ver cambios
git status

# Output:
# On branch release-notes/26.4.0
# Changes to be committed:
#   modified:   docs/LatestPublishers.md
#   new file:   docs/release-notes/ios/release-notes-26.4.0.md

# Ver commit
git log -1

# Output:
# commit abc1234567890def
# Author: Roberto Pedraza <rpedraza@example.com>
# Date:   Sun Jan 19 16:00:00 2026
#
#     docs: Add release notes for 26.4.0
```

### Ver Contenido del Archivo

```bash
cat docs/release-notes/ios/release-notes-26.4.0.md
```

**Output:**

```markdown
# Release Notes 26.4.0 - iOS

**Fecha:** 2026-01-19
**Versión:** 26.4.0

*🟣 Yoigo*
- Bloqueado el acceso al recargador a usuarios pospago (ECAPP-12154)
- Añadida nueva sección de consentimientos (ECAPP-12058)
- Correcciones de textos (ECAPP-12215)

*🟡 MASMOVIL*
- Bloqueado el acceso al recargador a usuarios pospago (ECAPP-12154)
- Correcciones de textos (ECAPP-12215)
...
```

### Ver LatestPublishers Actualizado

```bash
cat docs/LatestPublishers.md
```

**Output:**

```markdown
# Latest Publishers

| Publisher | Latest Version |
|-----------|----------------|
| Roberto Pedraza | [4 - 26.4.0]   |  👈 Actualizado
| Otro Usuario    | [3 - 26.3.0]   |
```

---

## 🔄 Próximos Pasos (Manual)

### Opción 1: Push directo (si tienes permisos)

```bash
# Push de la rama
git push -u origin release-notes/26.4.0

# Crear PR desde GitHub UI o gh CLI
gh pr create \
  --title "docs: Release notes for 26.4.0" \
  --body "Generated release notes for version 26.4.0" \
  --base develop \
  --head release-notes/26.4.0
```

### Opción 2: Workflow completo con PR (automatizado)

Agregar al workflow un step final:

```yaml
- id: create_pr
  name: "Create Pull Request"
  plugin: github
  step: create_pr
  params:
    title: "docs: Release notes for ${fix_version}"
    body: "Generated release notes for version ${fix_version}"
    base: "develop"
  requires:
    - fix_version
```

---

## 🐛 Troubleshooting Común

### Error: "Workflow not found"

```bash
# Verificar que el workflow existe
ls .titan/workflows/generate-release-notes.yaml

# Si no existe, volver al Paso 2 del Setup
```

### Error: "JIRA client not available"

```bash
# Verificar configuración JIRA
titan plugins list | grep jira

# Configurar JIRA si no está
titan plugins configure jira
```

### Error: "Git client not available"

```bash
# Verificar Git instalado
which git

# Verificar plugin
titan plugins list | grep git
```

### Error: "No unreleased versions found"

**Causas posibles:**
1. Todas las versiones ya fueron released en JIRA
2. No tienes permisos para ver versiones
3. Proyecto JIRA incorrecto

**Solución:**
```bash
# Verificar en JIRA web que existen versiones unreleased
# URL: https://jira.masmovil.com/projects/ECAPP/versions
```

### Error al crear archivo: "Directory not found"

```bash
# Verificar que el directorio existe
ls -la docs/release-notes/ios

# Si no existe, crearlo
mkdir -p docs/release-notes/ios

# Actualizar workflow con la ruta correcta
vim .titan/workflows/generate-release-notes.yaml
```

### Rama ya existe

```bash
# Ver ramas locales
git branch | grep release-notes

# Borrar rama vieja si es necesario
git branch -D release-notes/26.4.0

# Ejecutar workflow de nuevo
```

---

## 📊 Ejemplo de Sesión Completa

```bash
# 1. Navegar al proyecto
$ cd ~/Documents/MasMovil/ragnarok-ios

# 2. Ejecutar workflow
$ /generate-release-notes

# 3. Interacción
Select platform: 1 (iOS)
Select version: 3 (26.4.0)

# 4. El workflow se ejecuta...
✓ Created branch release-notes/26.4.0
✓ Found 15 issues in JIRA
✓ Generated AI descriptions
✓ Created release-notes-26.4.0.md
✓ Updated LatestPublishers.md
✓ Commit created: abc1234

# 5. Verificar resultado
$ git status
On branch release-notes/26.4.0
nothing to commit, working tree clean

$ ls docs/release-notes/ios/
release-notes-26.4.0.md  ✅

# 6. Push y PR
$ git push -u origin release-notes/26.4.0
$ gh pr create --title "docs: Release notes for 26.4.0" --base develop

# 7. ✅ Done!
```

---

## 🎓 Tips & Best Practices

### 1. Verificar antes de ejecutar

```bash
# Ver qué rama estás
git branch --show-current

# Ver si hay cambios sin commitear
git status
```

### 2. Dry-run primero

Ejecuta con una versión de prueba para verificar que todo funciona.

### 3. Revisar release notes generadas

```bash
# Antes de hacer push, revisar el contenido
cat docs/release-notes/ios/release-notes-26.4.0.md

# Editar si es necesario
vim docs/release-notes/ios/release-notes-26.4.0.md

# Ammend commit si editaste
git add .
git commit --amend --no-edit
```

### 4. Backup de LatestPublishers

```bash
# Antes de ejecutar workflow (primera vez)
cp docs/LatestPublishers.md docs/LatestPublishers.md.bak
```

---

**¿Listo para empezar?** Sigue el Setup Inicial y luego ejecuta `/generate-release-notes`!

**Última actualización:** 2026-01-19
