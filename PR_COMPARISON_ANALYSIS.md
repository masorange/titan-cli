# Análisis Comparativo: PR #3629 vs PR #3601

**Proyecto**: ragnarok-ios
**Feature**: Release Notes 26.4
**Fecha de Análisis**: 2026-01-21

---

## 📊 Resumen Ejecutivo

### PR #3601 (Edi - Manual)
- **Autor**: @EdiLT (Edi)
- **Fecha**: 2026-01-19
- **Archivo**: `ReleaseNotes/26.4.0.md`
- **Issues**: 28 líneas
- **Método**: **Manual** (redacción humana)

### PR #3629 (Raúl - Titan CLI)
- **Autor**: @r-pedraza (Raúl)
- **Fecha**: 2026-01-20 (primer commit) / 2026-01-21 (segundo commit)
- **Archivo**: `ReleaseNotes/26.4.md`
- **Issues**: 60 líneas
- **Método**: **Automatizado** (Titan CLI workflow con AI)

---

## 🔍 Diferencias Principales

### 1. **Nombre del Archivo**

| PR | Nombre de Archivo | Formato |
|----|------------------|---------|
| #3601 | `26.4.0.md` | Versión completa (YY.W.B) |
| #3629 | `26.4.md` | Versión corta (YY.W) |

**❌ PROBLEMA**: Inconsistencia en formato de nombre.

**✅ SOLUCIÓN**: El workflow de Titan debería usar `26.4.0.md` (formato completo) para consistencia.

### 2. **Cantidad de Issues**

| PR | Total de Issues | Issues por Marca |
|----|----------------|------------------|
| #3601 | **7 issues únicos** | Distribuidos en 8 marcas |
| #3629 | **27 issues únicos** | Distribuidos en 9 marcas |

**⚠️ OBSERVACIÓN**: PR #3629 tiene **casi 4x más issues** que PR #3601.

**Posible Causa**:
- PR #3601: Filtrado manual (solo issues más importantes)
- PR #3629: Todos los issues del fixVersion en JIRA

### 3. **Marcas Incluidas**

| Marca | PR #3601 | PR #3629 |
|-------|----------|----------|
| 🟣 Yoigo | ✅ 2 issues | ✅ 5 issues |
| 🟡 MASMOVIL | ✅ 1 issue | ❌ Sin cambios |
| 🔴 Jazztel | ✅ 3 issues | ✅ 9 issues |
| 🔵 Lycamobile | ✅ 1 issue | ❌ Sin cambios |
| 🟤 Lebara | ✅ 1 issue | ✅ 2 issues |
| 🟠 Llamaya | ✅ 1 issue | ❌ Sin cambios |
| 🟢 Guuk | ✅ 1 issue | ✅ 2 issues |
| ⚪️ Sweno | ✅ 1 issue | ✅ 2 issues |
| ⚫️ Marca Desconocida | ❌ No incluida | ✅ 19 issues |

**🎯 DIFERENCIA CLAVE**: PR #3629 incluye **"Marca Desconocida"** con 19 issues.

### 4. **Calidad de Descripciones**

#### PR #3601 (Manual - Edi)
```markdown
*🟣 Yoigo*
- Adaptar el proyecto al nuevo POE (ECAPP-12341)
- Quitar la opción de control parental en Disney (ECAPP-12021)
```

**Características**:
- ✅ Infinitivo ("Adaptar", "Quitar")
- ✅ Conciso y directo
- ✅ Lenguaje técnico pero claro

#### PR #3629 (AI - Titan CLI)
```markdown
*🟣 Yoigo*
- Eliminado el control parental de Disney (ECAPP-12021)
- Actualizado el proyecto según nuevo POE (ECAPP-12341)
- Actualizado el proyecto según nuevo POE (ECAPP-12361)
- Corregida la aparición del popup informativo al regresar de enlaces en consentimientos (ECAPP-12369)
- Corregidos errores en permanencias de OTTs mostradas con el fijo (ECAPP-12372)
```

**Características**:
- ✅ Participio pasado ("Eliminado", "Actualizado", "Corregida")
- ✅ Más detallado
- ✅ Lenguaje consistente
- ⚠️ Algunos duplicados (ECAPP-12341 y ECAPP-12361 son similares)

---

## 🔎 Análisis Detallado por Issue

### Issues Únicos en PR #3601 (No en #3629)
**Ninguno** - Todos los issues de PR #3601 están en PR #3629.

### Issues Únicos en PR #3629 (No en #3601)

**Total**: 20 issues adicionales

**Por Marca**:
- **Yoigo**: 3 adicionales
  - ECAPP-12361, ECAPP-12369, ECAPP-12372

- **Jazztel**: 6 adicionales
  - ECAPP-12261, ECAPP-12327, ECAPP-12332, ECAPP-12347, ECAPP-12360, ECAPP-12361

- **Lebara**: 1 adicional
  - ECAPP-12361

- **Guuk**: 1 adicional
  - ECAPP-12361

- **Sweno**: 1 adicional
  - ECAPP-12361

- **Marca Desconocida**: 19 issues (todos nuevos)
  - ECAPP-12205, ECAPP-12206, ECAPP-12250, ECAPP-12287, ECAPP-12311, ECAPP-12317, ECAPP-12341, ECAPP-12361, ECAPP-12369, ECAPP-12372, ECAPP-12451, ECAPP-12452, ECAPP-12455, ECAPP-12462, ECAPP-12470, ECAPP-12480, ECAPP-12481, ECAPP-12482, ECAPP-12483

**⚠️ OBSERVACIÓN CRÍTICA**:
- ECAPP-12341 y ECAPP-12361 aparecen en **múltiples marcas** en PR #3629
- En PR #3601, ECAPP-12341 aparece en **todas las marcas**
- Posible **duplicación de issues** que afectan a todas las marcas

---

## 🐛 Issues Detectados

### Issue #1: Nombre de Archivo Inconsistente

**Archivo en PR #3601**: `26.4.0.md` ✅
**Archivo en PR #3629**: `26.4.md` ❌

**Impacto**: Inconsistencia en versionado.

**Solución**:
- El step `normalize_version_step` en Titan CLI ya existe
- Debe usarse en el workflow para normalizar a `YY.W.B` format
- Actualizar `save_release_notes_file_step` para usar versión normalizada

### Issue #2: "Marca Desconocida" con 19 Issues

**Causa**: Issues sin `customfield_11931` (campo de marca) en JIRA.

**Impacto**:
- Confusión sobre qué marcas realmente afecta
- Release notes menos útiles

**Solución**:
- Filtrar issues sin marca definida en JIRA
- O agregar paso manual para clasificar issues sin marca

### Issue #3: Duplicación de Issues "All Brands"

**Ejemplo**: ECAPP-12341 y ECAPP-12361 aparecen en 8 marcas cada uno.

**Causa**: Issues con marca "All" en JIRA se duplican en todas las marcas.

**Impacto**:
- Release notes muy repetitivas
- Difícil de leer

**Solución**:
- Crear sección especial "Todas las marcas"
- O agrupar issues comunes al inicio

### Issue #4: LatestPublishers.md Update

**PR #3601**:
```diff
-5. Edi: 47
+5. Edi: 4
```
**Week**: 4

**PR #3629**:
```diff
 8. Jose: 41
+9. Raúl: 4
```
**Week**: 4 (añadido como nuevo publisher)

**Observación**: Ambos PRs son para semana 4 del 2026.

---

## 📊 Comparación de Traducciones AI

### Issue: ECAPP-12341 (Adaptar proyecto al nuevo POE)

**PR #3601 (Manual)**:
```
Adaptar el proyecto al nuevo POE
```

**PR #3629 (AI)**:
```
Actualizado el proyecto según nuevo POE
```

**Análisis**:
- Manual: Infinitivo, imperativo
- AI: Participio pasado, descriptivo
- Ambas correctas, pero **estilos diferentes**

### Issue: ECAPP-12021 (Control parental Disney)

**PR #3601 (Manual)**:
```
Quitar la opción de control parental en Disney
```

**PR #3629 (AI)**:
```
Eliminado el control parental de Disney
```

**Análisis**:
- Manual: "Quitar la opción"
- AI: "Eliminado"
- AI es más conciso

### Issue: ECAPP-12317 (Doble-marca Lyca/Llamaya)

**PR #3601 (Manual)**:
```
Integrar a los usuarios de Lyca en la aplicación de LlamaYa con suporte doble-marca
```

**PR #3629 (AI)**:
```
Mejorado el rendimiento general
```

**⚠️ PROBLEMA CRÍTICO**:
- La traducción de AI **NO coincide** con el issue real
- ECAPP-12317 en JIRA probablemente tiene un summary genérico como "Performance improvements"
- El workflow de AI no está capturando el contexto correcto

---

## 🎯 Recomendaciones

### 1. **Corrección Inmediata**

#### A. Normalizar Nombre de Archivo
```bash
# En ragnarok-ios
cd /Users/rpedraza/Documents/MasMovil/ragnarok-ios
git checkout release-notes/26.4
git mv ReleaseNotes/26.4.md ReleaseNotes/26.4.0.md
git commit -m "fix: normalize release notes filename to 26.4.0.md"
```

#### B. Usar `normalize_version_step` en Workflow
```yaml
# En release-notes-ios.yaml
- id: normalize_version
  name: "Normalize Version Format"
  plugin: jira
  step: normalize_version
  requires:
    - fix_version
```

### 2. **Mejoras al Workflow**

#### A. Filtrar "Marca Desconocida"
```python
# En generate_release_notes_step.py
if brand_name == "Marca Desconocida":
    continue  # Skip issues without brand
```

#### B. Agrupar Issues "All Brands"
```markdown
## Todas las marcas
- Actualizado el proyecto según nuevo POE (ECAPP-12341)
- Actualizado el proyecto según nuevo POE (ECAPP-12361)

## Por Marca

*🟣 Yoigo*
- Eliminado el control parental de Disney (ECAPP-12021)
...
```

#### C. Mejorar Prompt de AI para Traducciones
```python
# Añadir contexto adicional del issue
prompt = f"""
Issue: {issue.key}
Summary: {issue.summary}
Description: {issue.description[:500]}
Components: {issue.components}

Traduce el summary a español en participio pasado...
"""
```

### 3. **Validación Manual**

**Antes de mergear PR #3629**:
- [ ] Verificar que todos los issues son realmente de la versión 26.4
- [ ] Validar traducciones de AI (especialmente ECAPP-12317)
- [ ] Decidir qué hacer con "Marca Desconocida"
- [ ] Normalizar nombre de archivo a `26.4.0.md`

---

## ✅ Conclusiones

### Ventajas del Workflow Automatizado (PR #3629)

1. ✅ **Completitud**: Captura todos los issues del fixVersion
2. ✅ **Consistencia**: Formato uniforme en todas las marcas
3. ✅ **Velocidad**: Generación automática en minutos
4. ✅ **Trazabilidad**: Todos los issues tienen ID de JIRA

### Desventajas del Workflow Automatizado

1. ❌ **Sin filtrado**: Incluye issues técnicos/internos
2. ❌ **Marca Desconocida**: 19 issues sin clasificar
3. ❌ **Duplicación**: Issues "All Brands" repetidos 8 veces
4. ❌ **Traducciones AI**: Algunas pueden no ser precisas (ECAPP-12317)

### Ventajas del Proceso Manual (PR #3601)

1. ✅ **Curación**: Solo issues importantes para usuarios
2. ✅ **Sin duplicados**: Issues "All Brands" aparecen una vez por marca
3. ✅ **Traducciones precisas**: Redacción humana

### Desventajas del Proceso Manual

1. ❌ **Lento**: Requiere tiempo manual
2. ❌ **Incompletitud**: Puede omitir issues
3. ❌ **Inconsistencia**: Formato puede variar

---

## 🎯 Próximos Pasos

1. **Corto Plazo** (Para PR #3629):
   - Normalizar nombre de archivo a `26.4.0.md`
   - Revisar manualmente issues de "Marca Desconocida"
   - Validar traducción de ECAPP-12317

2. **Mediano Plazo** (Workflow):
   - Añadir `normalize_version_step` al workflow
   - Implementar filtro para "Marca Desconocida"
   - Agrupar issues "All Brands" en sección separada

3. **Largo Plazo** (Mejora Continua):
   - Mejorar prompts de AI para traducciones más precisas
   - Añadir validación manual antes de commit
   - Crear dashboard para comparar releases

---

**Generado**: 2026-01-21
**Por**: Claude Code Analysis
**Comparación**: PR #3629 (Automatizado) vs PR #3601 (Manual)
