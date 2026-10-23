# AI-DLC Inception: Problema, Estado del Arte y Competidores
**Proyecto:** Solución Distribuida en la Nube para el Procesamiento Masivo de Órdenes Médicas en un Sistema Público de Salud (Chernovia)  
**Marco Metodológico:** AWS Labs AI-DLC (`awslabs/aidlc-workflows`) - Fase de Inception  
**Autores / Afiliación:** Proyecto COIL Interdisciplinario (UPB - Universidad Panamericana)

---

## 1. Contexto y Planteamiento del Problema

Los sistemas públicos de salud no solo vigilan eventos epidemiológicos, sino que deben resolver a diario y a escala masiva la viabilidad y cobertura de servicios médicos solicitados por millones de ciudadanos. La falta de interoperabilidad y la fragmentación de los sistemas tradicionales generan cuellos de botella críticos, retrasos en la atención y sobrecostos por fraudes o clasificaciones erróneas.

### El Reto Operativo
El gobierno federal busca automatizar la recepción, extracción, clasificación y liquidación de cobertura de órdenes médicas:
* **Escala objetivo:** 12 millones de órdenes médicas.
* **Ventana de servicio (SLA):** Menos de 24 horas continuas (rendimiento mínimo $\ge 139$ órdenes/segundo).
* **Entrada de datos:** Archivos con fecha, medio emisor, valor del procedimiento, entidad emisora y glosa semiestructurada.
* **Estructura de la glosa:** `Paciente: <nombre>; DNO: <id>; SeguroSocial: <id>; Edad: <edad>; PerfilCobertura: <perfil>; ServicioSolicitado: <servicio>; Medicacion: <med1>|<med2>|...`
* **Regla de Negocio:**
  * Si el servicio está en el catálogo de 20 servicios cubiertos:
    * Perfil PRIORITARIO: Reconocimiento del 100%.
    * Perfil ESTÁNDAR: Reconocimiento del 50%.
    * Perfil COPAGO: Reconocimiento del 25%.
  * Si el servicio NO está en el catálogo cubierto: Reconocimiento del 0% (Estado `NO CUBRE`).
* **Línea Base del Dataset de Prueba (1.2M órdenes):**
  * Solicitado total: \$1,583,859,890,309 COP.
  * Reconocido legítimo: \$57,328,752,396 COP (3.6% del total solicitado).
  * 65% de órdenes cubiertas / 35% no cubiertas.
  * Una clasificación incorrecta tiene un impacto multimillonario directo en las finanzas del Estado.

---

## 2. Estado del Arte y Análisis de Competidores

| Competidor / Sistema | Operación y Enfoque | Arquitectura Tecnológica | Brecha / Limitación Documentada |
| :--- | :--- | :--- | :--- |
| **FPS – CMS (Estados Unidos)** | Analiza reclamaciones de 3 a 5 días post-envío; modelos predictivos y analistas humanos (GAO, 2012). | Sistema web en centro de datos privado de contratista; 25 modelos (reglas, anomalías). | No integrado con el motor de pagos; alta tasa de falsos positivos por falta de contexto local. |
| **TMS / NHCX – NHA (India)** | Preautorización y reclamación con adjudicación humana en cadena y plazos de 6 horas (Nirmitee, s.f.). | Gateway de intercambio con API, mensajería cifrada FHIR R4 y callbacks asíncronos. | Dependencia de adjudicación manual en TMS; migración gradual en curso. |
| **MUV FEV-RIPS (Colombia)** | Valida factura electrónica XML y RIPS JSON emitiendo el código CUV (MinSalud, 2024). | Validador centralizado en SISPRO con reglas codificadas y APIs cliente-servidor. | Solo valida estructura e interoperabilidad fiscal; no liquida cobertura clínica ni pagos. |
| **NHIA (Taiwán)** | Monitoreo centralizado inteligente de asegurador único para reducir duplicidades (NHIA, 2025). | Repositorio nacional centralizado con capa de big data analítica (MediCloud). | Detalle de infraestructura no público; centralización cerrada. |
| **Arquitectura de Referencia AWS / Mapfre Atenea** | Procesamiento de pólizas y fraude desacoplado en paralelo (Shea & Mahapatro, 2023; Kuniyil et al., 2026). | Lago de datos Iceberg/Parquet en S3, procesamiento Spark con EMR Serverless / Glue. | Requiere adaptación a estándares y reglas específicas del sector público de salud. |

---

## 3. Brechas Identificadas y Oportunidad del Proyecto

Ninguno de los competidores o referencias analizadas reúne de forma conjunta:
1. **Decisión y liquidación 100% automática** de cobertura y valor para el 100% del volumen.
2. **Trazabilidad estricta y linaje de auditoría** por registro (versión de catálogo, regla, corrida).
3. **Seudonimización rigurosa de PII (SHA-256)** conforme a normativas de privacidad (Ley 1581 de 2012).
4. **Costo por volumen optimizado** (< \$0.15 USD por corrida de 12 millones de órdenes) liberando recursos al finalizar la ejecución.
