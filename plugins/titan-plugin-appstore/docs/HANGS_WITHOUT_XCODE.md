# Cómo Ver Hangs Sin Xcode Organizer

Guía completa para acceder a crash logs y hang reports cuando generas builds por CI/CD.

## 🎯 Tu Situación

```
✅ Generas builds por CI/CD (Fastlane, Jenkins, GitHub Actions, etc.)
❌ NO tienes el binario en Xcode Organizer local
❓ Necesitas ver hangs y crashes
```

**Problema**: Xcode Organizer solo muestra crashes/hangs de binarios que tú compilaste localmente.

**Solución**: Usar alternativas que no requieren Xcode Organizer.

---

## 🌐 Opción 1: Web UI de App Store Connect (⭐ Recomendado)

### La Forma Más Rápida

**Acceso directo**: https://appstoreconnect.apple.com

### Pasos:

```
1. Inicia sesión en App Store Connect
2. App Store → Selecciona tu app
3. Menú lateral izquierdo:
   - TestFlight → [Tu app]
   - O: App Store → [Tu app]

4. En el menú lateral, busca:
   "Crashes & Hangs" o "Diagnostics"

5. Verás dos pestañas:
   📊 Crashes  |  ⏱️ Hangs

6. Filtra por:
   - Versión: 26.12.0
   - Periodo: Últimos 7 días (o el que necesites)
   - Estado: Abiertos
```

### Lo Que Verás:

```
TOP HANGS (ordenados por frecuencia)
────────────────────────────────────────────────
1. Main Thread Blocked - UIViewController
   Frecuencia: 1,234 veces
   Duración media: 350ms
   Dispositivos afectados: 567
   Stack Trace: [Ver detalles]

2. Network Request Blocking UI
   Frecuencia: 890 veces
   Duración media: 520ms
   ...
```

**Ventajas**:
- ✅ No necesitas Xcode
- ✅ Datos completos y actualizados
- ✅ Stack traces simbolizados automáticamente
- ✅ Gráficos de tendencias
- ✅ Filtros avanzados (dispositivo, iOS version, etc.)
- ✅ Puedes descargar crash logs (.crash files)

---

## 🤖 Opción 2: Titan CLI (Nuevo Workflow)

### Análisis Automático desde Terminal

**Comando**:
```bash
titan
# → Workflows → App Store → Production Version Health
```

**Lo que hace**:
1. ✅ Obtiene métricas de estabilidad (crash rate, hang rate)
2. ✅ Intenta descargar top hangs vía API
3. ✅ Te da el link directo a App Store Connect si API no tiene todo

**Output**:
```
============================================================
📊 DIAGNOSTICS - Version 26.12.0
============================================================

📈 METRICS SUMMARY
------------------------------------------------------------
  Crash Rate:    3.4600%
  Hang Rate:     22.9000%
  Terminations:  346
  Hangs:         2,290

⏱️  TOP HANGS (Most Frequent)
------------------------------------------------------------
1. Signature: MainThreadBlock_UIViewController
   Frequency: 1,234 occurrences
   Duration:  350ms avg
   Devices:   567

⚠️  Detailed hang reports not available via API

   To view detailed hang reports:
   1. Go to: https://appstoreconnect.apple.com
   2. Your App → Crashes & Hangs → Hangs tab
   3. Filter by version: 26.12.0
```

**Ventajas**:
- ✅ Desde terminal (perfecto para scripts)
- ✅ Integrado con tu análisis de versión
- ✅ Automatizable en CI/CD
- ⚠️ Puede que no tenga todos los detalles (usa web UI para eso)

---

## 📱 Opción 3: Fastlane Pilot

### Descargar Crash Logs Automáticamente

Si usas Fastlane, puedes descargar crash logs:

```ruby
# Fastfile
lane :download_crashes do
  download_dsyms(
    app_identifier: "com.tuapp.bundle",
    version: "26.12.0"
  )

  # Esto descarga los dSYMs necesarios para simbolizar
  # Los crash logs están en App Store Connect web UI
end
```

**Limitación**: Fastlane descarga **dSYMs**, pero los crash logs aún necesitas verlos en la web UI.

---

## 🔧 Opción 4: App Store Connect API (Programático)

### Para Integración Custom

Hemos creado una operación en Titan para acceder vía API:

```python
from titan_plugin_appstore.operations.diagnostics_operations import DiagnosticsOperations

# Inicializar
diag_ops = DiagnosticsOperations(client)

# Obtener hang reports
result = diag_ops.get_hang_reports(
    app_id="1234567890",
    version_string="26.12.0",
    limit=10
)

# Obtener crash reports
crash_result = diag_ops.get_crash_reports(
    app_id="1234567890",
    version_string="26.12.0",
    limit=10
)
```

**Ventajas**:
- ✅ Programático (ideal para automation)
- ✅ Integrable en dashboards custom
- ⚠️ API puede no tener todos los detalles de la web UI

---

## 📊 Comparación de Opciones

| Opción | Facilidad | Completitud | Automatizable | Stack Traces |
|--------|-----------|-------------|---------------|--------------|
| **App Store Connect Web** ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ❌ | ✅ Completos |
| **Titan CLI Workflow** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ✅ | ⚠️ Básicos |
| **Fastlane** | ⭐⭐⭐ | ⭐⭐ | ✅ | ❌ Solo dSYMs |
| **API Directa** | ⭐⭐ | ⭐⭐⭐ | ✅ | ⚠️ Limitado |

---

## 🎯 Caso de Uso: Tu Problema Actual

Tienes **22.9% hang rate** en la versión 26.12.0. Aquí está cómo investigarlo:

### Paso 1: Ve a App Store Connect Web

```
https://appstoreconnect.apple.com
→ Tu App
→ Crashes & Hangs
→ Pestaña: Hangs
→ Filtro: Version 26.12.0
→ Ordenar por: Frequency (más frecuente primero)
```

### Paso 2: Identifica el Top Hang

Ejemplo de lo que verás:

```
#1 - MainThreadBlocked_NetworkRequest
────────────────────────────────────────
Frecuencia:    1,456 ocurrencias (63% del total)
Duración avg:  450ms
Dispositivos:  789 únicos

Stack Trace:
  0  MyApp                  -[NetworkManager fetchData] + 234
  1  MyApp                  -[ViewController viewDidLoad] + 567
  2  UIKitCore              -[UIViewController loadViewIfRequired] + 123
  ...

Análisis:
  → Llamada de red SÍNCRONA en main thread
  → Bloqueando UI durante viewDidLoad
```

### Paso 3: Fix el Problema

```swift
// ❌ ANTES (bloqueante)
func viewDidLoad() {
    super.viewDidLoad()
    let data = networkManager.fetchData() // Síncrono - BLOQUEA UI
    updateUI(with: data)
}

// ✅ DESPUÉS (asíncrono)
func viewDidLoad() {
    super.viewDidLoad()

    Task {
        let data = await networkManager.fetchData() // Asíncrono
        await MainActor.run {
            updateUI(with: data)
        }
    }
}
```

### Paso 4: Verifica el Fix

```bash
# Después de release hotfix v26.12.1
titan
# → Production Version Health

# Comprueba que hang rate bajó:
# Era: 22.9% → Esperado: <5%
```

---

## 🚨 Tipos Comunes de Hangs

### 1. Network en Main Thread

**Síntoma**: Stack trace muestra `URLSession` o `Alamofire` en main thread

**Causa**:
```swift
// Código problemático
let data = try! Data(contentsOf: url) // Síncrono!
```

**Fix**:
```swift
// Correcto
Task {
    let (data, _) = try await URLSession.shared.data(from: url)
}
```

### 2. Core Data en Main Thread

**Síntoma**: `NSManagedObjectContext` blocking main thread

**Causa**:
```swift
// Operación pesada en main context
context.fetch(request) // Bloqueante
```

**Fix**:
```swift
// Usa background context
context.perform {
    let results = try context.fetch(request)
}
```

### 3. File I/O Síncrono

**Síntoma**: `FileManager` operations en main thread

**Causa**:
```swift
let contents = try String(contentsOf: fileURL) // Bloqueante
```

**Fix**:
```swift
Task.detached {
    let contents = try String(contentsOf: fileURL)
    await MainActor.run {
        // Update UI
    }
}
```

### 4. Image Processing

**Síntoma**: `UIImage`, `CIFilter` en main thread

**Causa**:
```swift
let resized = image.resize(to: size) // CPU-intensive
```

**Fix**:
```swift
Task.detached(priority: .userInitiated) {
    let resized = image.resize(to: size)
    await MainActor.run {
        imageView.image = resized
    }
}
```

---

## 📋 Checklist de Debugging

Cuando investigues hangs sin Xcode Organizer:

- [ ] Accede a App Store Connect web UI
- [ ] Filtra por versión problemática
- [ ] Ordena hangs por frecuencia
- [ ] Identifica el top hang (>50% del total)
- [ ] Analiza el stack trace
- [ ] Identifica operación bloqueante
- [ ] Mueve operación a background thread
- [ ] Prueba fix localmente con Instruments
- [ ] Deploy hotfix
- [ ] Verifica hang rate bajó en App Store Connect

---

## 🛠️ Herramientas Complementarias

### Instruments (Local Testing)

Antes de deployar el fix:

```
1. Xcode → Product → Profile
2. Selecciona template: "Time Profiler"
3. Reproduce el flujo que causa hangs
4. Busca "Main Thread" en timeline
5. Identifica picos > 250ms
```

### Firebase Performance Monitoring

Si tienes Firebase integrado:

```swift
// Instrumenta código sospechoso
let trace = Performance.startTrace(name: "viewDidLoad")

// Tu código
networkManager.fetchData()

trace?.stop()
```

Firebase mostrará:
- Duración de cada traza
- Distribución de tiempos
- Percentiles (p50, p95, p99)

---

## 💡 Tips Pro

### 1. Automatiza el Análisis

Crea un script que ejecute el workflow diariamente:

```bash
#!/bin/bash
# check_production_health.sh

titan --non-interactive << EOF
workflows
appstore
Production Version Health
EOF

# Parse output y envía a Slack si hay problemas
```

### 2. Alertas Automáticas

```bash
# En tu CI/CD post-deploy
if titan_hang_rate > 10%; then
    send_slack_alert "⚠️ Hang rate alto en producción: ${hang_rate}%"
fi
```

### 3. Historial de Métricas

```bash
# Guarda métricas para comparar
titan workflows run production-version-health > metrics_$(date +%Y%m%d).txt
```

---

## 🔗 Enlaces Útiles

- **App Store Connect**: https://appstoreconnect.apple.com
- **Documentación Hangs**: https://developer.apple.com/documentation/xcode/diagnosing-performance-issues-with-xcode-organizer
- **Best Practices**: https://developer.apple.com/videos/play/wwdc2021/10087/

---

## ❓ FAQ

**P: ¿Puedo ver hangs de versiones antiguas?**
R: Sí, Apple conserva datos de versiones hasta 90 días después de que salgan de producción.

**P: ¿Los datos son en tiempo real?**
R: No, hay delay de 24-48h. Para monitoreo real-time usa Firebase Performance.

**P: ¿Necesito dSYMs para ver hangs?**
R: No para las métricas generales. Sí para stack traces detallados y simbolizados.

**P: ¿Puedo descargar todos los hang logs?**
R: Desde la web UI puedes descargar muestras representativas, no todos los logs individuales.

**P: ¿Qué hago si el API no me da detalles?**
R: Usa la web UI de App Store Connect - siempre tiene más información que el API.

---

**Guía de Hangs Sin Xcode v1.0**
*Creado: 2026-03-31*
