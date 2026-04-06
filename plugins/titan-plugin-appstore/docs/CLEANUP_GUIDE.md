# Cleanup Guide - Archivos a Mantener/Eliminar

Guía para limpiar archivos duplicados y migrar al nuevo plugin.

---

## ✅ MANTENER - Plugin Nuevo (Producción)

### Ubicación: `plugins/titan-plugin-appstore/`

**Archivos esenciales** (NO eliminar):

```
plugins/titan-plugin-appstore/
├── pyproject.toml                    ✅ MANTENER - Package manifest
├── README.md                         ✅ MANTENER - Documentación principal
├── QUICKSTART.md                     ✅ MANTENER - Guía rápida
│
├── titan_plugin_appstore/            ✅ MANTENER TODO - Código del plugin
│   ├── __init__.py
│   ├── exceptions.py
│   ├── credentials.py
│   ├── plugin.py
│   ├── models/                       (4 archivos)
│   ├── clients/                      (7 archivos)
│   ├── operations/                   (2 archivos)
│   └── steps/                        (4 archivos)
│
├── workflows/                        ✅ MANTENER - Workflows de producción
│   └── create-app-version.yaml
│
└── tests/                            ✅ MANTENER - Tests
    ├── conftest.py
    ├── services/                     (3 archivos)
    └── operations/                   (2 archivos)
```

**Archivos de documentación** (opcionales pero recomendados):

```
✅ MANTENER:
├── QUICKSTART.md          - Guía de inicio rápido
├── README.md              - Documentación principal
├── STRUCTURE.md           - Arquitectura técnica
├── MIGRATION_GUIDE.md     - Guía de migración

⚠️ OPCIONALES (puedes eliminar después de leer):
├── SUMMARY.md             - Resumen ejecutivo (ya leído)
├── TEST_RESULTS.md        - Resultados de tests (referencia)
├── CLEANUP_GUIDE.md       - Esta guía (eliminar después)
└── verify_plugin.py       - Script de verificación (desarrollo)
```

---

## ❌ ELIMINAR - Código Antiguo (Duplicado)

### Ubicación: `.titan/steps/appstore_connect/`

**Todo este directorio es DUPLICADO** y puede eliminarse:

```
.titan/steps/appstore_connect/        ❌ ELIMINAR TODO
├── __init__.py                       ❌ Duplicado
├── plugin.py                         ❌ Duplicado
├── config.example.toml               ❌ No necesario
│
├── helpers/                          ❌ Reemplazado por clients/
│   ├── __init__.py
│   ├── api_client.py                 ❌ → clients/network/appstore_api.py
│   └── credentials.py                ❌ → credentials.py
│
├── steps/                            ❌ Reemplazados
│   ├── check_credentials_step.py     ❌ No necesario
│   ├── create_version_step.py        ❌ → steps/create_version_step.py
│   ├── list_apps_step.py             ❌ No necesario
│   ├── list_versions_step.py         ❌ No necesario
│   ├── prompt_version_step.py        ❌ → steps/prompt_version_step.py
│   ├── select_app_step.py            ❌ → steps/select_app_step.py
│   └── setup_*.py (7 archivos)       ❌ No necesarios
│
└── requirements.txt                  ❌ → pyproject.toml

TOTAL: ~20 archivos duplicados
```

**También eliminar estos pasos sueltos** (ya están en el plugin):

```
.titan/steps/
├── check_credentials_step.py         ❌ ELIMINAR
├── create_version_step.py            ❌ ELIMINAR
├── list_apps_step.py                 ❌ ELIMINAR
├── list_versions_step.py             ❌ ELIMINAR
├── prompt_version_step.py            ❌ ELIMINAR
├── select_app_step.py                ❌ ELIMINAR
├── setup_*.py (7 archivos)           ❌ ELIMINAR

TOTAL: ~13 archivos
```

---

## ⚠️ EVALUAR - Workflows Antiguos

### Ubicación: `.titan/workflows/`

```
.titan/workflows/
├── create-app-version.yaml           ⚠️ EVALUAR
└── setup-appstore-connect.yaml       ⚠️ EVALUAR
```

**Decisión:**

- Si usan `plugin: project` → ❌ ELIMINAR (obsoleto)
- Si usan `plugin: appstore` → ✅ MANTENER (actualizado)

**Verificar contenido:**
```bash
grep "plugin:" .titan/workflows/create-app-version.yaml
```

Si dice `plugin: project`, reemplazar con workflow nuevo:
```bash
rm .titan/workflows/create-app-version.yaml
rm .titan/workflows/setup-appstore-connect.yaml
# Usar workflows/create-app-version.yaml del plugin
```

---

## 📁 MANTENER - Configuración y Credenciales

### Ubicación: `.appstore_connect/`

```
.appstore_connect/                    ✅ MANTENER TODO
├── credentials.json                  ✅ Credenciales activas
├── AuthKey_*.p8                      ✅ Private key
├── .gitignore                        ✅ Seguridad
└── README.md                         ⚠️ Opcional
```

**IMPORTANTE**: Nunca eliminar:
- `credentials.json` (configuración activa)
- `AuthKey_*.p8` (private key)
- `.gitignore` (seguridad)

---

## 🧹 Plan de Limpieza Recomendado

### Fase 1: Backup (Precaución)

```bash
# Crear backup del código antiguo
tar -czf appstore_connect_old_backup.tar.gz \
  .titan/steps/appstore_connect \
  .titan/steps/*_step.py \
  .titan/workflows/create-app-version.yaml \
  .titan/workflows/setup-appstore-connect.yaml

# Verificar backup
tar -tzf appstore_connect_old_backup.tar.gz | head
```

### Fase 2: Eliminar Código Antiguo

```bash
# Eliminar directorio antiguo completo
rm -rf .titan/steps/appstore_connect/

# Eliminar steps sueltos
rm .titan/steps/check_credentials_step.py
rm .titan/steps/create_version_step.py
rm .titan/steps/list_apps_step.py
rm .titan/steps/list_versions_step.py
rm .titan/steps/prompt_version_step.py
rm .titan/steps/select_app_step.py
rm .titan/steps/setup_*.py

# Eliminar workflows antiguos (si usan plugin: project)
rm .titan/workflows/create-app-version.yaml
rm .titan/workflows/setup-appstore-connect.yaml
```

### Fase 3: Verificar Plugin Nuevo

```bash
# Verificar instalación
python -c "from titan_plugin_appstore import AppStoreConnectClient; print('✅ OK')"

# Ejecutar tests
cd plugins/titan-plugin-appstore
pytest

# Ejecutar verificación
python verify_plugin.py
```

### Fase 4: Cleanup Documentación (Opcional)

```bash
cd plugins/titan-plugin-appstore

# Eliminar archivos temporales
rm SUMMARY.md          # Ya leído
rm CLEANUP_GUIDE.md    # Esta guía
rm verify_plugin.py    # Script de desarrollo
rm TEST_RESULTS.md     # Opcional

# Mantener:
# - README.md (esencial)
# - QUICKSTART.md (útil)
# - STRUCTURE.md (referencia técnica)
# - MIGRATION_GUIDE.md (referencia)
```

---

## 📊 Resumen de Limpieza

### Antes
```
Total archivos: ~55
├── Plugin nuevo: 30 archivos
├── Código antiguo: ~20 archivos (duplicado)
└── Docs temporales: ~5 archivos
```

### Después
```
Total archivos: ~30
├── Plugin producción: 20 archivos (código + tests)
├── Workflows: 1 archivo
├── Docs esenciales: 3-4 archivos
└── Config: 5 archivos
```

**Espacio liberado**: ~25 archivos duplicados eliminados

---

## ✅ Checklist Final

**Antes de eliminar, verificar:**

- [ ] Plugin nuevo instalado (`pip list | grep titan-plugin-appstore`)
- [ ] Tests pasando (`pytest` en plugin nuevo)
- [ ] Credenciales copiadas a `.appstore_connect/`
- [ ] Backup creado del código antiguo
- [ ] Workflows actualizados para usar `plugin: appstore`

**Después de eliminar, verificar:**

- [ ] No quedan referencias a `.titan/steps/appstore_connect/`
- [ ] Workflows funcionan con plugin nuevo
- [ ] Tests siguen pasando
- [ ] Importaciones funcionan

---

## 🚨 NO ELIMINAR

**NUNCA eliminar:**

```
❌ .appstore_connect/credentials.json
❌ .appstore_connect/AuthKey_*.p8
❌ plugins/titan-plugin-appstore/ (plugin completo)
❌ .gitignore (en cualquier carpeta)
```

---

## 📞 Si Algo Sale Mal

### Restaurar backup
```bash
tar -xzf appstore_connect_old_backup.tar.gz
```

### Reinstalar plugin
```bash
cd plugins/titan-plugin-appstore
pip uninstall titan-plugin-appstore
pip install -e .
```

### Verificar estado
```bash
python plugins/titan-plugin-appstore/verify_plugin.py
```

---

**Recomendación**: Hacer limpieza gradual, verificando después de cada fase.
