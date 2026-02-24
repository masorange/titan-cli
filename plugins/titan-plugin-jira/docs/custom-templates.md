# Plantillas Personalizadas para Issues

El workflow **Crear Issue de JIRA** permite usar plantillas personalizadas para generar descripciones de issues.

## Ubicación de Plantillas

### Plantilla del Proyecto (Recomendada)

Crea tu plantilla personalizada en:

```
.titan/templates/issue_templates/default.md.j2
```

Esta plantilla se usará automáticamente cuando ejecutes el workflow.

### Plantilla por Defecto del Plugin

Si no existe una plantilla de proyecto, se usa la plantilla por defecto del plugin:

```
plugins/titan-plugin-jira/titan_plugin_jira/config/templates/generic_issue.md.j2
```

## Formato de la Plantilla

Las plantillas usan **Jinja2** y reciben las siguientes variables desde la IA:

| Variable | Tipo | Descripción |
|----------|------|-------------|
| `description` | string | Descripción expandida de la tarea |
| `objective` | string | Objetivo de la issue |
| `acceptance_criteria` | string | Criterios de aceptación (checkboxes) |
| `technical_notes` | string o None | Notas técnicas (opcional) |
| `dependencies` | string o None | Dependencias (opcional) |

## Ejemplo de Plantilla Personalizada

```jinja2
## 📋 Descripción

{{ description }}

## 🎯 Objetivo

{{ objective }}

## ✅ Criterios de Aceptación

{{ acceptance_criteria }}

{% if technical_notes %}
---

### 🔧 Notas Técnicas

{{ technical_notes }}
{% endif %}

{% if dependencies %}
---

### 🔗 Dependencias

{{ dependencies }}
{% endif %}

---

*Creado con Titan CLI*
```

## Crear Tu Plantilla Personalizada

1. **Crea el directorio** (si no existe):

```bash
mkdir -p .titan/templates/issue_templates
```

2. **Crea la plantilla**:

```bash
cat > .titan/templates/issue_templates/default.md.j2 << 'EOF'
## Descripción

{{ description }}

## Objetivo

{{ objective }}

## Criterios de Aceptación

{{ acceptance_criteria }}

{% if technical_notes %}
### Notas Técnicas

{{ technical_notes }}
{% endif %}
EOF
```

3. **Ejecuta el workflow**:

El workflow automáticamente detectará y usará tu plantilla.

## Consejos

- **Usa Markdown**: Las plantillas soportan Markdown completo
- **Secciones opcionales**: Usa `{% if variable %}` para contenido condicional
- **Formato limpio**: La IA genera el contenido, tu plantilla lo estructura
- **Emojis**: Añade emojis para mejor legibilidad (opcional)
- **Commits**: Versiona tu plantilla con Git para compartirla con el equipo

## Ejemplo Avanzado: Plantilla con Checklist de QA

```jinja2
## 📋 Descripción

{{ description }}

## 🎯 Objetivo

{{ objective }}

## ✅ Criterios de Aceptación

{{ acceptance_criteria }}

{% if technical_notes %}
---

### 🔧 Implementación

{{ technical_notes }}
{% endif %}

{% if dependencies %}
---

### 🔗 Dependencias

{{ dependencies }}
{% endif %}

---

## 🧪 QA Checklist

- [ ] Tests unitarios implementados
- [ ] Tests de integración pasando
- [ ] Documentación actualizada
- [ ] Code review aprobado
- [ ] Funciona en staging

---

*Generado automáticamente por Titan CLI*
```

## Hooks y Extensibilidad

Este workflow es extensible mediante hooks en Titan. Puedes añadir pasos custom antes o después de cualquier step del workflow.

Consulta la documentación de Titan para más información sobre hooks.
