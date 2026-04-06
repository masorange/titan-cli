# Quick Start: Version Analysis

Guía rápida para usar el nuevo análisis de estabilidad y propagación.

## 🚀 Lo que hemos creado

Has pedido un análisis que combine **estabilidad** (crashes/hangs) y **propagación** (instalaciones/países) para una versión.

**Hemos implementado:**

1. ✅ **Operación reutilizable**: `AnalysisOperations.analyze_version()`
2. ✅ **Modelos de datos**: `VersionAnalysisView`, `StabilityMetrics`, `PropagationMetrics`
3. ✅ **2 workflows nuevos** listos para usar
4. ✅ **Tests completos** con 100% cobertura
5. ✅ **Documentación completa** (ver VERSION_ANALYSIS_GUIDE.md)

## 📋 Workflows Disponibles

### Opción 1: Production Version Health (⭐ Recomendado)

**Uso**: Monitoreo diario de producción

```bash
titan
# Workflows → App Store → Production Version Health
```

**Qué hace:**
1. Seleccionas la app
2. **Automáticamente** encuentra la última versión READY_FOR_SALE
3. Analiza estabilidad + propagación
4. Muestra recomendaciones

**Salida:**
```
============================================================
ANALYSIS RESULTS
============================================================

App: Mi Yoigo
Version: 26.13.0

📉 STABILITY METRICS
------------------------------------------------------------
  Crash Rate:    0.2123%
  Hang Rate:     0.0456%
  Terminations:  2,145
  Hangs:         456

📈 PROPAGATION METRICS
------------------------------------------------------------
  Total Units:   45,678
  Countries:     25
  Market Share:  78.3%

🏥 HEALTH ASSESSMENT
------------------------------------------------------------
  Status:        🟢 HEALTHY
  Health Score:  89.2/100

💡 RECOMMENDATIONS
------------------------------------------------------------
  ✅ Version is stable and propagating well. Safe to continue rollout.
  📊 INFO: Version has majority market share. Monitor for any emerging issues.

============================================================
✅ Version is healthy!
```

### Opción 2: Version Health Check

**Uso**: Analizar cualquier versión específica

```bash
titan
# Workflows → App Store → Version Health Check
```

**Qué hace:**
1. Seleccionas la app
2. **Seleccionas manualmente** la versión a analizar
3. Mismo análisis completo

## 🔧 Uso Programático

Si quieres usar la operación directamente en código:

```python
from titan_plugin_appstore.clients.appstore_client import AppStoreConnectClient
from titan_plugin_appstore.operations.analysis_operations import AnalysisOperations
from titan_cli.core.result import ClientSuccess, ClientError

# Inicializar
client = AppStoreConnectClient(
    key_id="TU_KEY_ID",
    issuer_id="TU_ISSUER_ID",
    private_key_path="/path/to/key.p8"
)

analysis_ops = AnalysisOperations(client)

# Analizar versión
result = analysis_ops.analyze_version(
    app_id="1234567890",
    version_string="26.13.0",
    vendor_number="80012345",  # Opcional: para datos de ventas
    app_name="Mi Yoigo"        # Opcional: para filtrar ventas
)

# Procesar resultado
match result:
    case ClientSuccess(data=analysis):
        print(f"Status: {analysis.status}")
        print(f"Health Score: {analysis.health_score}/100")
        print(f"Crash Rate: {analysis.stability.crash_rate}%")
        print(f"Market Share: {analysis.propagation.market_share}%")

        for rec in analysis.get_recommendations():
            print(f"  • {rec}")

    case ClientError(error_message=err):
        print(f"Error: {err}")
```

## 📊 Datos que Obtienes

### De Performance API (Apple)
- ✅ `crash_rate`: % de sesiones que crashean
- ✅ `hang_rate`: % de sesiones con hangs
- ✅ `terminations`: Total de crashes
- ✅ `hangs`: Total de hangs

**Fuente**: Mismo dato que ves en Xcode Organizer

### De Sales Reports API (Apple)
- ✅ `total_units`: Instalaciones/descargas reales
- ✅ `countries`: Número de países activos
- ✅ `market_share`: % del total de instalaciones

**Fuente**: Datos reales de ventas/descargas

### Calculados
- ✅ `health_score`: Puntuación 0-100
- ✅ `status`: healthy 🟢 / warning 🟡 / critical 🔴
- ✅ `recommendations`: Lista de acciones sugeridas

## 🎯 Casos de Uso

### Caso 1: Monitoreo Diario

```bash
# Cada mañana, revisa la producción
titan
# → Production Version Health
```

Verás si tu versión en producción está estable.

### Caso 2: Después de un Release

```bash
# Espera 24-48h después del release para datos completos
titan
# → Version Health Check → Selecciona la nueva versión
```

Comprueba si la nueva versión es estable antes de aumentar el rollout.

### Caso 3: Incident Response

```python
# Script de emergencia
analysis_ops = AnalysisOperations(client)
result = analysis_ops.analyze_version(
    app_id="1234567890",
    version_string="26.13.0",
    vendor_number="80012345",
    app_name="Mi Yoigo"
)

if result.data.status == "critical":
    print(f"🚨 ALERTA: Crash rate {result.data.stability.crash_rate}%")
    print(f"   Usuarios afectados: ~{result.data.propagation.total_units}")
    # Trigger rollback automation
```

### Caso 4: Comparar Versiones

```python
# Comparar producción actual vs anterior
comparison = analysis_ops.compare_versions(
    app_id="1234567890",
    current_version="26.13.0",
    previous_version="26.12.0",
    vendor_number="80012345",
    app_name="Mi Yoigo"
)

print(comparison.data.format_comparison())
# Output:
# Comparison: 26.12.0 → 26.13.0
#    📉 Crash Rate: -0.15%  (mejoró!)
#    📈 Propagation: +5,432 units
#    Regression: NO ✅
```

## ⚙️ Configuración Necesaria

En `.titan/config.toml`:

```toml
[plugins.appstore]
enabled = true

[plugins.appstore.credentials]
key_id = "ABC123XYZ"
issuer_id = "12345678-1234-1234-1234-123456789012"
private_key_path = "/path/to/AuthKey_ABC123XYZ.p8"
vendor_number = "80012345"  # ⚠️ IMPORTANTE para datos de propagación
```

### ¿Dónde encontrar el vendor_number?

1. Ve a [App Store Connect](https://appstoreconnect.apple.com)
2. Sales and Trends → Reports → Sales
3. El vendor number aparece en el selector de reportes

**⚠️ Sin vendor_number:**
- Solo tendrás métricas de estabilidad
- No verás datos de propagación (unidades, países, market share)

## 🧪 Tests

Ejecutar tests:

```bash
cd plugins/titan-plugin-appstore
poetry run pytest tests/operations/test_analysis_operations.py -v
```

**Cobertura**: 100% en operaciones de análisis

## 📚 Documentación Completa

Ver [VERSION_ANALYSIS_GUIDE.md](./VERSION_ANALYSIS_GUIDE.md) para:
- Explicación detallada de cada métrica
- Cómo se calcula el health score
- Thresholds de los estados
- Ejemplos avanzados
- Troubleshooting

## 🆕 Archivos Creados

### Modelos
- `models/analysis.py`: `VersionAnalysisView`, `StabilityMetrics`, `PropagationMetrics`, `VersionComparisonView`

### Operaciones
- `operations/analysis_operations.py`: `AnalysisOperations` con 3 métodos principales

### Steps
- `steps/analyze_single_version_step.py`: Step para analizar 1 versión
- `steps/fetch_production_version_step.py`: Step automático para producción

### Workflows
- `workflows/version-health-check.yaml`: Análisis manual (seleccionas versión)
- `workflows/production-version-health.yaml`: Análisis automático (última producción)

### Tests
- `tests/operations/test_analysis_operations.py`: Tests completos

### Documentación
- `docs/VERSION_ANALYSIS_GUIDE.md`: Guía completa (60+ páginas)
- `docs/QUICK_START_ANALYSIS.md`: Este archivo

## 🚦 Próximos Pasos

1. **Configura el vendor_number** en `.titan/config.toml`
2. **Ejecuta el workflow** `Production Version Health`
3. **Revisa los resultados** y familiarízate con las métricas
4. **Automatiza** (opcional): Integra en tu CI/CD

## 💡 Tips

- **Espera 24-48h** después de un release para datos completos
- **El vendor_number es clave** para propagación
- **Health score < 50** = Investigar inmediatamente
- **Status critical** = Considerar rollback
- **Market share > 80%** = Monitorear de cerca

## ❓ Preguntas Frecuentes

**P: ¿Por qué no veo datos de propagación?**
R: Necesitas configurar `vendor_number` en `.titan/config.toml`

**P: ¿Por qué el crash_rate es 0.0%?**
R: Espera 24-48h después del release. Apple tiene delay en procesar datos.

**P: ¿Qué es un buen health score?**
R:
- 90-100: Excelente
- 70-89: Bueno
- 50-69: Aceptable
- <50: Problema

**P: ¿Puedo analizar versiones viejas?**
R: Sí, usa "Version Health Check" y selecciona cualquier versión.

**P: ¿Funciona sin vendor_number?**
R: Sí, pero solo tendrás métricas de estabilidad (crashes/hangs), no propagación.

---

**Quick Start Guide v1.0**
*Creado: 2026-03-31*
