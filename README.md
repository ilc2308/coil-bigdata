# Solución Distribuida en la Nube para el Procesamiento Masivo de Órdenes Médicas
**Proyecto COIL Interdisciplinario:** Big Data y Metodología de la Investigación  
**Institución:** Universidad Pontificia Bolivariana (UPB)  
**Marco de Ingeniería:** AWS Labs AI-DLC (`awslabs/aidlc-workflows`)  
**Versión:** 2.0.0 — FastAPI + Streamlit + PyArrow + Docker

---

## 🌐 Despliegue en Vivo en AWS (Learner Lab)

La plataforma interactiva y la API REST se encuentran desplegadas en una instancia **EC2 (Ubuntu 22.04 LTS)** en AWS Academy Learner Lab:

* 🖥️ **Dashboard Web (Streamlit):** [http://coilupbsalud.duckdns.org](http://coilupbsalud.duckdns.org)
* 📑 **Documentación Interactiva (Swagger API):** [http://coilupbsalud.duckdns.org/docs](http://coilupbsalud.duckdns.org/docs)
* 💓 **Health Check API:** [http://coilupbsalud.duckdns.org/health](http://coilupbsalud.duckdns.org/health)

### 🔐 Credenciales de Acceso a la Plataforma Web
* **Usuario:** `admin`
* **Contraseña:** `coil2026`

*(Las credenciales aplican tanto para el login en el Dashboard web de Streamlit como para la autenticación por token en la API REST de Swagger).*

---

## 🚀 Inicio Rápido — Modo Local

### Opción A: Docker (recomendado)

```bash
# 1. Clonar y entrar al proyecto
git clone <repo> && cd proyecto-coil-bigdata

# 2. Configurar variables de entorno
cp .env.example .env
# (edita .env si necesitas cambiar usuario/contraseña)

# 3. Construir e iniciar los servicios
docker-compose up --build

# 4. Acceder:
#    API REST:  http://localhost:8000
#    Swagger:   http://localhost:8000/docs
#    Dashboard: http://localhost:8501
#    Login:     admin / coil2026
```

### Opción B: Script PowerShell (Windows, sin Docker)

```powershell
.\start_local.ps1
```

### Opción C: Manual

```bash
# Instalar dependencias
pip install -r requirements.txt

# Terminal 1: API FastAPI
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Dashboard Streamlit
streamlit run app/main.py
```

### Ejecutar tests

```bash
# Tests unitarios (parser + motor de reglas)
python -m pytest tests/test_components.py -v

# Tests de integración (API + pipeline)
python -m pytest tests/test_api_integration.py -v

# Todos los tests
python -m pytest tests/ -v
```

### Procesar datos (CLI directo)

```bash
# Muestra rápida (1,000 órdenes)
python -m src.batch_processor

# Dataset completo (1.2M órdenes, ~344 MB)
python -m src.batch_processor dataset/COIL_dataset_glosas_salud_1_2M.csv

# Oráculo de validación independiente
python -m src.oracle_validator
```

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
   git remote add origin https://github.com/ilc2308/coil-bigdata.git
   git branch -M main
   git push -u origin main
   ```
*(Nota: El archivo de 360 MB ya está configurado en `.gitignore` para permitir pushes limpios a GitHub sin exceder los límites de tamaño)*.

---

## 📂 Estructura Completa del Proyecto (v2.0)

```text
proyecto-coil-bigdata/
├── api/                              # Backend FastAPI
│   ├── main.py                       # App principal, CORS, lifespan
│   ├── middleware/auth.py            # JWT HS256
│   ├── routers/                      # 7 routers REST
│   │   ├── auth.py                   # POST /auth/token
│   │   ├── process.py                # POST /process, GET /process/{id}
│   │   ├── results.py                # GET /results (paginado)
│   │   ├── quarantine.py             # GET /quarantine
│   │   ├── coverage.py               # GET /coverage/servicios, POST /evaluate
│   │   ├── audit.py                  # POST /audit/validate, POST /audit/parse
│   │   └── reports.py                # GET /reports/gold/csv, /excel
│   ├── schemas/                      # Modelos Pydantic
│   └── services/                     # Lógica de negocio
│       ├── config.py                 # Settings desde .env
│       ├── storage_service.py        # Lectura paginada Parquet/CSV, S3
│       ├── batch_service.py          # Wrapper async del batch_processor
│       └── report_service.py         # Generador CSV/Excel
│
├── app/                              # Frontend Streamlit
│   ├── main.py                       # Entry point, nav, autenticación
│   ├── components/
│   │   ├── auth.py                   # Login, helpers api_get/post
│   │   ├── charts.py                 # 9 gráficos Plotly reutilizables
│   │   └── paginator.py              # Tabla paginada genérica
│   └── pages/
│       ├── page_01_dashboard.py      # KPIs y gráficos ejecutivos
│       ├── page_02_carga_datos.py    # Upload CSV
│       ├── page_03_procesamiento.py  # Lanzar y monitorear corridas
│       ├── page_04_cobertura.py      # Catálogos y evaluador
│       ├── page_05_glosas.py         # Viewer paginado capa gold
│       ├── page_06_cuarentena.py     # Registros rechazados
│       ├── page_07_auditoria.py      # Oráculo y trazabilidad
│       ├── page_08_reportes.py       # Exportar CSV/Excel
│       └── page_09_configuracion.py  # Estado y guía de uso
│
├── src/                              # Motor de procesamiento (EXISTENTE)
│   ├── utils/glosa_parser.py         # Parser regex + SHA-256
│   ├── utils/rule_engine.py          # Motor de reglas de cobertura
│   ├── batch_processor.py            # Procesador local (Parquet + CSV)
│   ├── oracle_validator.py           # Oráculo de validación 100%
│   ├── aws_glue_job.py               # Job Spark para AWS Glue
│   └── scaler_12m.py                 # Generador sintético 12M
│
├── tests/
│   ├── conftest.py                   # Fixtures compartidos
│   ├── test_components.py            # Tests unitarios (parser + engine)
│   └── test_api_integration.py       # Tests de integración API (45 tests)
│
├── infrastructure/                   # IaC (no modificar sin autorización)
├── dataset/                          # CSVs de entrada y catálogos
├── output/                           # Resultados de corridas (gitignored)
├── uploads/                          # Archivos subidos por usuario
│
├── Dockerfile                        # API FastAPI
├── Dockerfile.streamlit              # Frontend Streamlit
├── docker-compose.yml                # Orquestación local
├── requirements.txt                  # Dependencias Python fijadas
├── .env.example                      # Plantilla de configuración
├── pytest.ini                        # Configuración de tests
├── start_local.ps1                   # Script de inicio Windows
└── Makefile                          # Comandos de conveniencia
```

## 🔐 Variables de Entorno Clave

| Variable | Default | Descripción |
|----------|---------|-------------|
| `APP_MODE` | `local` | Modo de operación: `local` o `aws` |
| `APP_USERNAME` | `admin` | Usuario del dashboard |
| `APP_PASSWORD` | `coil2026` | Contraseña del dashboard |
| `JWT_SECRET_KEY` | — | Clave para firmar JWT (cambiar en producción) |
| `LOCAL_OUTPUT_DIR` | `output` | Directorio de resultados |
| `AWS_ACCESS_KEY_ID` | — | Credenciales AWS (solo modo aws) |
| `S3_BUCKET_NAME` | — | Bucket S3 (solo modo aws) |

> ⚠️ **Nunca subas `.env` a Git.** Ya está en `.gitignore`.

---

## 🧪 Suite de Tests Completa

El proyecto tiene **4 suites de tests** con cobertura total del pipeline:

```bash
# Todos los tests
python -m pytest tests/ -v

# Por suite:
python -m pytest tests/test_components.py -v           # Parser + Motor (unitarios)
python -m pytest tests/test_api_integration.py -v      # API FastAPI (integración)
python -m pytest tests/test_batch_performance.py -v    # Batch + Parquet + PII
python -m pytest tests/test_aws_mock.py -v             # AWS S3/Glue (con moto)
```

| Suite | Tests | Cubre |
|---|---|---|
| `test_components` | 5 | Parser glosa, motor de reglas |
| `test_api_integration` | 40+ | Todos los endpoints REST |
| `test_batch_performance` | 25+ | Conciliación, rendimiento, PII, Parquet, reglas |
| `test_aws_mock` | 18 | S3 upload/download/list, Glue start/status, deploy |

---

## ☁️ Despliegue Web (Producción)

### Opción A: EC2 con Docker Compose

```bash
# En la instancia EC2 (Ubuntu 22.04):
chmod +x infrastructure/deploy_ec2.sh
./infrastructure/deploy_ec2.sh

# URL: http://<IP-del-servidor>
```

### Opción B: Docker local con Nginx

```bash
# Construir y arrancar con Nginx en puerto 80
docker-compose -f docker-compose.prod.yml up --build -d

# URLs:
#   Dashboard: http://localhost
#   API:       http://localhost/api/v1
#   Swagger:   http://localhost/docs
```

---

## ⚡ Flujo AWS completo

```
1. Configurar credenciales Learner Lab en .env
2. Verificar conexión:    Dashboard → ☁️ Consola AWS → Estado
3. Preparar S3:           Dashboard → ☁️ Consola AWS → S3 → Subir catálogos + script
4. Subir dataset:         Dashboard → ☁️ Consola AWS → S3 → Subir dataset (Bronze)
5. Lanzar Glue Job:       Dashboard → ⚙️ Procesamiento → Lanzar Glue Job
6. Reparar particiones:   Dashboard → ☁️ Consola AWS → Athena → Reparar tabla
7. Consultar resultados:  Dashboard → 📋 Glosas (lee de Athena automáticamente)
8. Ver métricas:          Dashboard → 📊 Dashboard (vistas analíticas de Athena)
```

---

## 📊 Resultados del Sistema (Corrida Verificada)

| Métrica | Valor | Meta |
|---------|-------|------|
| Registros procesados | 1,000 (muestra) | 1.2M prod |
| Conciliación de integridad | ✅ CUADRADA_PERFECTA | Diferencia = 0 |
| % Cobertura | 64.5% | — |
| Rendimiento | 9,948 órd/s | ≥ 139 órd/s ✅ |
| Cumple SLA 24h | ✅ Sí | < 86,400 s |
| Fugas de PII | 0 | 0 ✅ |
| Costo AWS est. (2 DPUs) | $0.000017 USD | < $0.10 USD/corrida |
| Exactitud de decisión | 100% | 100% ✅ |
| Exactitud financiera | 100% | 100% ✅ |



Integrantes: Ismael López Cardozo - Juan David Castañeda Osorno - Tatiana Fda Suarez
