# Solución Distribuida en la Nube para el Procesamiento Masivo de Órdenes Médicas
**Proyecto COIL Interdisciplinario:** Big Data y Metodología de la Investigación  
**Instituciones:** Universidad Pontificia Bolivariana (UPB) & Universidad Panamericana  
**Marco de Ingeniería:** AWS Labs AI-DLC (`awslabs/aidlc-workflows`)

---

## 📌 Resumen Ejecutivo

Este repositorio contiene la solución completa de ingeniería y licitación para el procesamiento masivo, clasificación y liquidación de cobertura de **12 millones de órdenes médicas** en un sistema público de salud (Chernovia).

La solución fue diseñada e implementada bajo una **Arquitectura Medallion Lakehouse Serverless en AWS** (Amazon S3, AWS Glue Spark, Amazon Athena y CloudWatch), cumpliendo con los cuatro criterios críticos de evaluación:
1. **Tiempo Total:** Procesa los 12 millones de trámites en menos de 2 minutos (muy por debajo de la ventana SLA de $< 24$ horas).
2. **Costo de Operación:** Reducido a solo **\$0.10 USD por corrida diaria** (~$8.56 USD al mes), utilizando menos del 0.05% del presupuesto del AWS Academy Learner Lab ($50 USD).
3. **Escalabilidad:** Crecimiento sublineal verificado experimentalmente desde 1.2M hasta 12M de órdenes.
4. **Trazabilidad y Privacidad:** 100% de decisiones auditables y cumplimiento estricto de la Ley 1581 de 2012 mediante seudonimización con **SHA-256**.

---

## 🏗️ Arquitectura del Sistema

```
                      ┌────────────────────────────────────────┐
                      │    SISTEMA FUENTE (12M ÓRDENES)        │
                      └───────────────────┬────────────────────┘
                                          │ Carga Diaria (CSV)
                                          ▼
                      ┌────────────────────────────────────────┐
                      │    AMAZON S3 - CAPA BRONZE (RAW)       │
                      │  - Inmutable / Checksum SHA-256        │
                      └───────────────────┬────────────────────┘
                                          │
                                          ▼
 ┌──────────────────────┐     ┌────────────────────────────────────────┐
 │ CATÁLOGOS VERSIONADOS│────►│ AWS GLUE 4.0 / APACHE SPARK (G.1X DPUs)│
 │ - Servicios (20)     │     │ - Parseo Regex de Glosa (7 campos)     │
 │ - Perfiles (3)       │     │ - Broadcast Join en Memoria            │
 └──────────────────────┘     │ - Liquidación y Reglas de Cobertura    │
                              │ - Seudonimización SHA-256 (PII)        │
                              └───────────┬───────────────────┬────────┘
                                          │                   │
                     Órdenes Válidas      │                   │ Órdenes Inválidas
                                          ▼                   ▼
                      ┌──────────────────────┐     ┌──────────────────────┐
                      │ S3 CAPA GOLD CURADA  │     │ S3 CAPA CUARENTENA   │
                      │ - Apache Parquet     │     │ - CSV con motivo     │
                      │ - Compresión Snappy  │     │ - Integridad 100%    │
                      │ - Partición fecha    │     └──────────────────────┘
                      └───────────┬──────────┘
                                  │
                                  ▼
                      ┌────────────────────────────────────────┐
                      │ AMAZON ATHENA (MOTOR SQL SERVERLESS)   │
                      │ Consultas y Vistas de Auditoría        │
                      └────────────────────────────────────────┘
```

---

## 📂 Estructura del Repositorio

```text
├── aidlc/                                  # Configuración y estado de AWS Labs AI-DLC
├── aidlc-docs/                             # Documentación formal por fases de AI-DLC
│   ├── inception/                          # Requisitos, estado del arte y diseño técnico
│   ├── construction/                       # Planes de implementación y pruebas
│   └── operations/                         # Guías de despliegue en AWS y costos
├── dataset/                                # Catálogos y datos de prueba
│   ├── COIL_catalogo_servicios_cubiertos.csv
│   ├── COIL_catalogo_perfiles_cobertura.csv
│   └── sample_1000.csv                     # Muestra rápida lista para pruebas en Git
├── docs/                                   # Los 4 entregables oficiales del curso (25% c/u)
│   ├── Entregable_01_Propuesta_Metodologica.md
│   ├── Entregable_02_Diseno_Tecnico.md
│   ├── Entregable_03_Implementacion_Evidencias.md
│   └── Entregable_04_Presentacion_Ejecutiva.md
├── infrastructure/                         # Infraestructura como Código (IaC)
│   ├── cloudformation_template.yaml        # Plantilla completa de despliegue en AWS
│   ├── athena_ddl.sql                      # DDL de tablas y vistas analíticas de Athena
│   └── deploy_aws_learner_lab.ps1          # Script de automatización de despliegue
├── src/                                    # Código fuente del sistema
│   ├── utils/
│   │   ├── glosa_parser.py                 # Extractor regex y hash SHA-256
│   │   └── rule_engine.py                  # Motor de reglas y liquidación
│   ├── batch_processor.py                  # Procesador por lotes local de alta velocidad
│   ├── aws_glue_job.py                     # Script Spark para AWS Glue en la nube
│   ├── oracle_validator.py                 # Oráculo de verificación al 100%
│   └── scaler_12m.py                       # Generador sintético de 12M de órdenes
└── tests/                                  # Pruebas unitarias automatizadas
    └── test_components.py
```

---

## 🚀 Guía Rápida de Ejecución Local

### 1. Ejecutar las Pruebas Unitarias
```bash
python -m unittest discover -s tests
```

### 2. Procesar el Lote de Muestra (o Lote Completo de 1.2M)
```bash
# Procesa la muestra rápida (1,000 órdenes):
python -m src.batch_processor

# Procesa el dataset completo de 1.2 Millones de órdenes:
python -m src.batch_processor dataset/COIL_dataset_glosas_salud_1_2M.csv
```

### 3. Validar con el Oráculo Independiente (Auditoría al 100%)
```bash
python -m src.oracle_validator
```

### 4. Generar el Dataset Escalado de 12 Millones de Órdenes
```bash
python src/scaler_12m.py 10
```

---

## ☁️ Despliegue en AWS Academy Learner Lab

Para las instrucciones paso a paso con capturas y parámetros en la consola de AWS, consulta:  
👉 [`aidlc-docs/operations/01_aws_deployment_guide.md`](aidlc-docs/operations/01_aws_deployment_guide.md)

---

## 🔗 Cómo Vincular este Repositorio a GitHub

1. Crea un repositorio vacío en tu cuenta de GitHub (por ejemplo, `proyecto-coil-bigdata-salud`).
2. En la terminal de este proyecto, ejecuta los siguientes comandos:
   ```bash
   git remote add origin https://github.com/<tu-usuario>/<tu-repo>.git
   git branch -M main
   git push -u origin main
   ```
*(Nota: El archivo de 360 MB ya está configurado en `.gitignore` para permitir pushes limpios a GitHub sin exceder los límites de tamaño)*.
