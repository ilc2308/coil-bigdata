# ENTREGABLE 03: IMPLEMENTACIÓN Y EVIDENCIAS EXPERIMENTALES (25%)
**Proyecto COIL Interdisciplinario:** Big Data y Metodología de la Investigación  
**Institución:** Universidad Pontificia Bolivariana (UPB)  
**Tema:** Diseño e implementación de una solución distribuida en la nube para el procesamiento masivo de órdenes médicas  
**Entregable:** Prototipo Funcional, Código Fuente, Pruebas y Evidencias de Resultados

---

## 🌐 Enlaces de Acceso al Prototipo Desplegado en AWS Learner Lab

El prototipo funcional se encuentra desplegado y accesible públicamente para evaluación:

* 🖥️ **Dashboard Web (Streamlit):** [http://54.226.55.125](http://54.226.55.125)
* 📑 **API REST y Documentación Interactiva (Swagger):** [http://54.226.55.125/docs](http://54.226.55.125/docs)
* 💓 **Health Check del Sistema:** [http://54.226.55.125/health](http://54.226.55.125/health)

### 🔐 Credenciales de Inicio de Sesión
* **Usuario:** `admin`
* **Contraseña:** `coil2026`

---

## 1. Componentes del Prototipo Funcional Desarrollado

El prototipo ha sido implementado y probado exhaustivamente, estructurado en módulos bajo las directrices del framework **AI-DLC** de AWS Labs:

```
src/
├── utils/
│   ├── glosa_parser.py       # CGU-01: Extractor regex de los 7 subcampos y hash SHA-256 PII
│   └── rule_engine.py        # CGU-02: Motor de reglas, cruce de catálogos y cálculo de cobertura
├── batch_processor.py        # CGU-03: Procesador de lotes de alta velocidad con particionamiento
├── aws_glue_job.py           # CGU-04: Script distribuido Apache Spark / AWS Glue 4.0
├── oracle_validator.py       # CGU-05: Oráculo independiente de verificación al 100%
└── scaler_12m.py             # CGU-06: Generador sintético de pruebas de estrés a 12M de órdenes
```

---

## 2. Evidencias de Ejecución Experimental sobre el Dataset Oficial (1,200,000 Órdenes)

Se ejecutó la corrida de validación sobre el archivo completo de órdenes médicas (`COIL_dataset_glosas_salud_1_2M.csv`, 360.3 MB).

### Registro de Salida de la Ejecución del Lote

```text
================ RESUMEN DE EJECUCIÓN (DATASET OFICIAL 1.2M) ================
ID Corrida: RUN-20261023-OFFICIAL-1.2M
Duración Total: 12.94 segundos
Rendimiento Sostenido: 92,735.70 órdenes/segundo
Total Órdenes Recibidas: 1,200,000
Total Órdenes Procesadas: 1,200,000
  - Órdenes Cubiertas: 780,000 (65.00%)
  - Órdenes No Cubiertas: 420,000 (35.00%)
Total Órdenes en Cuarentena: 0
Monto Total Solicitado: $1,583,859,890,309 COP
Monto Total Reconocido: $57,328,752,396 COP (3.62% del total solicitado)

Distribución por Perfil de Cobertura:
  - ESTANDAR (50%): 480,255 órdenes (40.02%)
  - PRIORITARIO (100%): 419,653 órdenes (34.97%)
  - COPAGO (25%): 300,092 órdenes (25.01%)

Conciliación de Integridad Contable:
  - Recibidas: 1,200,000 | Procesadas + Cuarentena: 1,200,000
  - Estado: CUADRADA_PERFECTA (0 registros perdidos, 0 duplicados)

Estimación de Costo en Cómputo AWS Glue (2 DPUs): $0.002213 USD
Cumple SLA de 24 horas: SÍ (Margen de holgura: > 6,600x)
Cumple Rendimiento Mínimo (>= 139 órdenes/s): SÍ (Margen: > 660x)
=============================================================================
```

---

## 3. Evidencias de Validación Formal con el Oráculo Independiente

Para asegurar que la lógica no contenga sesgos ni errores de redondeo, el script `oracle_validator.py` recalculó de manera totalmente desacoplada e independiente cada una de las solicitudes médicas.

### Resultado de la Auditoría del Oráculo

```text
============================================================
INICIANDO VALIDACIÓN INDEPENDIENTE CON ORÁCULO DE NEGOCIO
============================================================
Total registros leídos de la capa Gold: 1,200,000

---------------- RESULTADOS DEL ORÁCULO ----------------
Total registros auditados: 1,200,000
Exactitud en Decisión de Cobertura: 100.00% (Discrepancias: 0)
Exactitud en Porcentaje Aplicado: 100.00% (Discrepancias: 0)
Exactitud en Valor Reconocido (COP): 100.00% (Discrepancias: 0)
Fugas de Datos Personales (PII): 0 detectadas
Estado de Auditoría: APROBADO_100_EXACTITUD
Tiempo de validación: 14.82 segundos
--------------------------------------------------------
```

---

## 4. Evidencias de Pruebas Unitarias Automatizadas

Las pruebas unitarias fueron ejecutadas con el marco `unittest` de Python:

```text
......
----------------------------------------------------------------------
Ran 6 tests in 0.004s

OK
```

Detalle de casos probados:
1. `test_glosa_parsing_valid`: Extracción correcta de los 7 campos y hash SHA-256.
2. `test_glosa_parsing_invalid`: Detección de glosas corruptas y generación de causa de error.
3. `test_coverage_prioritario_100`: Asignación del 100% en servicios cubiertos prioritarios.
4. `test_coverage_estandar_50`: Asignación del 50% en servicios estándar cubiertos.
5. `test_coverage_copago_25`: Asignación del 25% en servicios copago cubiertos.
6. `test_coverage_non_covered_0`: Rechazo (0% y valor 0) ante servicios excluidos del catálogo.

---

## 5. Pruebas de Escalabilidad y Proyección a 12 Millones de Órdenes

| Indicador | Prueba Base (1.2M) | Proyección / Escala Objetivo (12M) | Meta Reto COIL | Estado de Cumplimiento |
| :--- | :--- | :--- | :--- | :--- |
| **Tiempo de Corrida** | 12.94 s | 110.60 s (~1.84 min) | $< 24$ horas | **Superado ampliamente** |
| **Rendimiento** | 92,735 órdenes/s | 108,500 órdenes/s | $\ge 139$ órdenes/s | **Superado ampliamente** |
| **Órdenes Cubiertas** | 780,000 | 7,800,000 | Coherente | **100%** |
| **Órdenes No Cubiertas** | 420,000 | 4,200,000 | Coherente | **100%** |
| **Valor Reconocido** | \$57,328,752,396 COP | \$573,287,523,960 COP | Coherente | **100%** |
| **Costo de Cómputo AWS** | \$0.0022 USD | \$0.0189 USD | $< \$50$ USD Lab | **Dentro de presupuesto** |
