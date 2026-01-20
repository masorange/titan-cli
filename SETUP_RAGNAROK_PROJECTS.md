# Setup Rápido - Ragnarok iOS/Android

Instrucciones para configurar los workflows de release notes en los proyectos Ragnarok.

## Para Ragnarok iOS

```bash
# 1. Ir al proyecto
cd /path/to/ragnarok-ios

# 2. Copiar workflow
mkdir -p .titan/workflows
cp /path/to/titan-cli/examples/ragnarok-ios-release-notes-workflow.yaml \
   .titan/workflows/generate-release-notes-ios.yaml

# 3. Crear configuración
cat > .titan/config.toml << 'TOML'
[project]
name = "Ragnarok iOS"

[jira]
base_url = "https://your-domain.atlassian.net"
email = "your-email@example.com"
project_key = "ECAPP"

[github]
owner = "your-org"
repo = "ragnarok-ios"
default_branch = "develop"

[git]
main_branch = "develop"

[ai]
default = "anthropic"
model = "claude-sonnet-4-5"
TOML

# 4. Configurar secrets
titan config secrets set JIRA_API_TOKEN
titan config secrets set GITHUB_TOKEN
titan config secrets set ANTHROPIC_API_KEY

# 5. Verificar
titan workflow list
# Debe mostrar SOLO: generate-release-notes-ios

# 6. Ejecutar (ejemplo)
titan workflow run generate-release-notes-ios
# Crea: ReleaseNotes/release-notes-{version}.md
```

## Para Ragnarok Android

```bash
# 1. Ir al proyecto
cd /path/to/ragnarok-android

# 2. Copiar workflow
mkdir -p .titan/workflows
cp /path/to/titan-cli/examples/ragnarok-android-release-notes-workflow.yaml \
   .titan/workflows/generate-release-notes-android.yaml

# 3. Crear configuración
cat > .titan/config.toml << 'TOML'
[project]
name = "Ragnarok Android"

[jira]
base_url = "https://your-domain.atlassian.net"
email = "your-email@example.com"
project_key = "ECAPP"

[github]
owner = "your-org"
repo = "ragnarok-android"
default_branch = "develop"

[git]
main_branch = "develop"

[ai]
default = "anthropic"
model = "claude-sonnet-4-5"
TOML

# 4. Configurar secrets
titan config secrets set JIRA_API_TOKEN
titan config secrets set GITHUB_TOKEN
titan config secrets set ANTHROPIC_API_KEY

# 5. Verificar
titan workflow list
# Debe mostrar SOLO: generate-release-notes-android

# 6. Ejecutar (ejemplo)
titan workflow run generate-release-notes-android
# Crea: docs/release-notes/release-notes-{version}.md
```

## Tokens/Secrets Requeridos

### JIRA_API_TOKEN
1. Ir a: https://id.atlassian.com/manage-profile/security/api-tokens
2. Crear nuevo token
3. Copiar y pegar cuando `titan config secrets set` lo pida

### GITHUB_TOKEN
1. Ir a: https://github.com/settings/tokens
2. Crear "Personal access token (classic)"
3. Permisos necesarios: `repo`, `workflow`
4. Copiar y pegar cuando `titan config secrets set` lo pida

### ANTHROPIC_API_KEY
1. Ir a: https://console.anthropic.com/settings/keys
2. Crear nueva API key
3. Copiar y pegar cuando `titan config secrets set` lo pida

## Verificación Post-Setup

### iOS
```bash
cd /path/to/ragnarok-ios

# Debe existir
ls -la .titan/config.toml
ls -la .titan/workflows/generate-release-notes-ios.yaml

# Debe mostrar solo 1 workflow
titan workflow list

# Debe listar plugins activos
titan plugins doctor
```

### Android
```bash
cd /path/to/ragnarok-android

# Debe existir
ls -la .titan/config.toml
ls -la .titan/workflows/generate-release-notes-android.yaml

# Debe mostrar solo 1 workflow
titan workflow list

# Debe listar plugins activos
titan plugins doctor
```

## Troubleshooting

### "No workflows found"
- Verificar que el archivo `.titan/workflows/*.yaml` existe
- Verificar que el nombre del workflow coincide en el archivo YAML

### "Plugin not initialized"
- Ejecutar: `titan plugins doctor` para ver qué plugin falta
- Instalar plugins faltantes desde Titan CLI

### "JIRA authentication failed"
- Verificar que JIRA_API_TOKEN está configurado correctamente
- Verificar que email y base_url son correctos en config.toml

### "GitHub authentication failed"
- Verificar que GITHUB_TOKEN tiene permisos `repo` y `workflow`
- Verificar que owner y repo son correctos en config.toml

## Estructura de Archivos Final

### iOS
```
ragnarok-ios/
├── .titan/
│   ├── config.toml
│   └── workflows/
│       └── generate-release-notes-ios.yaml
├── ReleaseNotes/
│   └── release-notes-26.4.0.md  # Generado por workflow
└── ... (código del proyecto)
```

### Android
```
ragnarok-android/
├── .titan/
│   ├── config.toml
│   └── workflows/
│       └── generate-release-notes-android.yaml
├── docs/
│   └── release-notes/
│       └── release-notes-26.4.0.md  # Generado por workflow
└── ... (código del proyecto)
```

---

**Actualizado**: 2026-01-20
