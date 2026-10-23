# AI-DLC Operations: Reporte y Justificación Económica en AWS
**Proyecto:** Solución Distribuida en la Nube para el Procesamiento Masivo de Órdenes Médicas en un Sistema Público de Salud  
**Marco Metodológico:** AWS Labs AI-DLC (`awslabs/aidlc-workflows`)

---

## 1. Modelo de Costos de la Arquitectura Seleccionada (Opción 1: Lotes con AWS Glue)

La solución fue diseñada bajo el principio de **eficiencia de recursos (Cost Optimization Pillar del AWS Well-Architected Framework)**:
* El clúster Spark es **100% transitorio/serverless**: solo se factura por los segundos exactos en que los workers procesan las órdenes.
* El almacenamiento en Amazon S3 adopta compresión columnar Parquet Snappy, reduciendo en más del **70%** el espacio en disco y el costo de escaneo en Amazon Athena.

### Precios Unitarios de Referencia (Región US East - N. Virginia, Octubre 2026)
* **AWS Glue (Spark 4.0/5.0):** \$0.308 USD por DPU-hora (1 DPU = 4 vCPU, 16 GB RAM).
* **AWS Glue Flex (Cargas no urgentes):** \$0.203 USD por DPU-hora.
* **Amazon S3 Standard:** \$0.023 USD por GB-mes / \$0.005 USD por 1,000 solicitudes PUT.
* **Amazon Athena:** \$5.00 USD por TB escaneado (gracias a Parquet Snappy, las consultas escanean solo columnas requeridas).

---

## 2. Comparación de Escenarios de Costo

Se contrastan cuatro alternativas técnicas para procesar una corrida diaria de **12 millones de órdenes médicas** (30 corridas mensuales):

| Concepto de Costo | Escenario 1a: Glue Estándar (Recomendado) | Escenario 1b: Glue Flex | Escenario 1c: EMR Serverless | Escenario 2: Híbrido (Firehose + Glue) |
| :--- | :--- | :--- | :--- | :--- |
| **Cómputo por corrida (12M órdenes)** | **\$0.10 USD** | **\$0.07 USD** | \$0.15 USD | \$0.20 USD |
| **Costo de cómputo por millón de órdenes** | **\$0.009 USD** | **\$0.006 USD** | \$0.013 USD | \$0.017 USD |
| **Cómputo mensual (30 corridas)** | **\$3.08 USD** | **\$2.03 USD** | \$4.54 USD | \$6.09 USD |
| **Almacenamiento S3 (Mes 1)** | \$0.53 USD | \$0.53 USD | \$0.53 USD | \$0.53 USD |
| **Consultas Athena (100 diarias)** | \$3.75 USD | \$3.75 USD | \$3.75 USD | \$3.75 USD |
| **Monitoreo & Orquestación** | \$1.00 USD | \$1.00 USD | \$1.00 USD | \$1.00 USD |
| **Ingesta Streaming (Firehose 24/7)** | \$0.00 USD | \$0.00 USD | \$0.00 USD | \$0.87 USD |
| **TOTAL ESTIMADO MES 1** | **\$8.56 USD** | **\$7.51 USD** | **\$10.02 USD** | **\$11.57 USD** |
| **TOTAL ACUMULADO MES 12 (con 1 año de datos)** | **\$20.91 USD** | **\$19.86 USD** | **\$22.37 USD** | **\$23.92 USD** |

---

## 3. Análisis de Sensibilidad (Escenario Pesimista / Estrés)

Se proyectó un escenario pesimista en el cual la corrida diaria requiera **10 workers G.1X (10 DPUs) durante 1 hora completa** (por reintentos de red masivos o auditorías extendidas):
* **Cómputo por corrida pesimista:** $10 \text{ DPUs} \times 1\text{ hora} \times \$0.308 = \$3.08\text{ USD}$.
* **Cómputo mensual pesimista (30 días):** \$92.40 USD.
* **Costo por orden en el peor caso:** Menos de \$0.00026 USD por orden médica (menos de tres diezmilésimas de dólar).

---

## 4. Conclusión para la Defensa ante el Comité

1. **Cumplimiento Holgado de Presupuesto:**
   El costo real de una prueba en el AWS Academy Learner Lab con 1.2 millones de órdenes es de tan solo **~\$0.02 USD**, lo que deja un 99.96% del presupuesto de \$50 USD totalmente libre para iteraciones y pruebas de auditoría.
2. **Retorno de Inversión (ROI) y Justificación Pública:**
   Para un sistema que analiza \$1.58 billones COP (\$395 millones USD aprox.) y liquida \$57,328 millones COP, un costo de infraestructura de **~\$0.10 USD por corrida diaria** representa una fracción despreciable (menos del 0.000001% del presupuesto de salud protegido), ofreciendo una justificación económica inexpugnable ante cualquier comité evaluador o tribunal de cuentas.
