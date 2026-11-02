# Guía Paso a Paso — COIL en AWS Academy Learner Lab

> **Contexto:** AWS Academy Learner Lab otorga $50 USD de crédito con sesiones de ~4 horas.  
> El costo total de una corrida completa (1.2M órdenes) es **≈ $0.10 USD**.  
> Esta guía cubre dos rutas: **Ruta A** (infraestructura via CloudFormation) y **Ruta B** (manual desde consola).

---

## ⚠️ Reglas importantes antes de empezar

- **No desplegar** sin haber completado los pasos de configuración local primero
- **No compartir** el `.env` ni credenciales en Git o chat
- Las sesiones del Learner Lab duran ~4 horas — el `AWS_SESSION_TOKEN` expira
- Si el token expira a mitad de una corrida, el Glue Job falla — renovar antes de empezar

---

## FASE 0 — Prerequisitos locales

Antes de tocar AWS, verifica que el sistema funciona en modo local:

```powershell
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Ejecutar tests unitarios (deben pasar todos)
python -m pytest tests/test_components.py -v

# 3. Probar el procesador local con la muestra
python -m src.batch_processor

# ✅ Si ves "CUADRADA_PERFECTA" en la consola, el sistema está listo
```

---

## FASE 1 — Iniciar el Learner Lab y obtener credenciales

### Paso 1.1 — Iniciar la sesión

1. Abre **AWS Academy** → tu curso → **Learner Lab**
2. Haz clic en **Start Lab** (botón verde)
3. Espera a que el indicador cambie de 🔴 a 🟢 (puede tardar 1–2 minutos)

### Paso 1.2 — Obtener las credenciales temporales

1. Haz clic en **AWS Details** (en el panel derecho)
2. Clic en **Show** junto a "AWS CLI"
3. Copia los **3 valores**:

```
aws_access_key_id     = ASIA...
aws_secret_access_key = wJalr...
aws_session_token     = IQoJb3Jp... (cadena muy larga)
```

> 💡 También puedes descargar el archivo `.aws/credentials` que aparece allí.

### Paso 1.3 — Conocer el ARN del LabRole

1. En la consola AWS → busca **IAM**
2. Roles → busca `LabRole`
3. Copia el ARN completo: `arn:aws:iam::XXXXXXXXXXXX:role/LabRole`

Guarda el número de cuenta (los 12 dígitos del ARN) — lo necesitarás después.

---

## FASE 2 — Configurar el proyecto local para modo AWS

### Paso 2.1 — Editar el archivo `.env`

```powershell
# Desde la raíz del proyecto
copy .env.example .env
notepad .env
```

Edita estos valores:

```bash
# ── Cambiar a modo AWS ──────────────────────────────────
APP_MODE=aws

# ── Credenciales del Learner Lab (las del Paso 1.2) ─────
AWS_ACCESS_KEY_ID=ASIA...
AWS_SECRET_ACCESS_KEY=wJalr...
AWS_SESSION_TOKEN=IQoJb3Jp...
AWS_DEFAULT_REGION=us-east-1

# ── Nombre del bucket (debe ser único globalmente) ───────
# Patrón recomendado: coil-bigdata-salud-datalake-<cuenta>-dev
S3_BUCKET_NAME=coil-bigdata-salud-datalake-XXXXXXXXXXXX-dev

# ── Nombres de recursos (NO cambiar) ────────────────────
GLUE_JOB_NAME=coil-bigdata-salud-spark-batch-processor
ATHENA_WORKGROUP=coil-bigdata-salud-analytics-wg
ATHENA_DATABASE=coil_bigdata_salud_db

# ── Credenciales de la app ───────────────────────────────
APP_USERNAME=admin
APP_PASSWORD=coil2026
JWT_SECRET_KEY=coloca-una-clave-aleatoria-larga-aqui
```

### Paso 2.2 — Verificar que el .env no se sube a Git

```powershell
Select-String -Path .gitignore -Pattern "^\.env$"
# Debe mostrar ".env" — si no aparece, agrégalo manualmente
```

---

## FASE 3 — Crear la infraestructura en AWS

### Ruta A — Script automático (recomendado)

```powershell
# Cargar variables del .env en la sesión de PowerShell
Get-Content .env | ForEach-Object {
    if ($_ -match "^([^#=]+)=(.*)$") {
        [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim())
    }
}

# Ejecutar el script de deploy
.\infrastructure\deploy_aws_learner_lab.ps1 `
    -BucketName $env:S3_BUCKET_NAME `
    -AwsRegion "us-east-1" `
    -LabRoleArn "arn:aws:iam::XXXXXXXXXXXX:role/LabRole"
```

El script hace automáticamente:
- ✅ Crea prefijos S3 (bronze/, gold/, quarantine/, scripts/, catalogs/)
- ✅ Sube catálogos CSV a `s3://<bucket>/catalogs/`
- ✅ Sube `aws_glue_job.py` a `s3://<bucket>/scripts/`
- ✅ Sube `sample_1000.csv` a `s3://<bucket>/bronze/solicitudes/`
- ✅ Despliega CloudFormation (S3, Glue Job, Athena WorkGroup)

---

### Ruta B — Consola AWS manual

#### B.1 — Crear el bucket S3

1. AWS Console → **S3** → **Create bucket**
2. Bucket name: `coil-bigdata-salud-datalake-XXXXXXXXXXXX-dev`
3. Region: `us-east-1` — Block all public access: ✅ — Encryption: SSE-S3
4. **Create bucket**

#### B.2 — Crear carpetas en el bucket

Crea estos prefijos (botón **Create folder** o subiendo un objeto vacío):

```
bronze/solicitudes/
gold/curated_solicitudes/
quarantine/solicitudes/
catalogs/
scripts/
athena-results/
spark-logs/
temp/
```

#### B.3 — Subir archivos a S3

```powershell
$bucket = $env:S3_BUCKET_NAME

aws s3 cp dataset/COIL_catalogo_servicios_cubiertos.csv s3://$bucket/catalogs/
aws s3 cp dataset/COIL_catalogo_perfiles_cobertura.csv  s3://$bucket/catalogs/
aws s3 cp src/aws_glue_job.py                           s3://$bucket/scripts/

# El dataset grande tarda 2-5 minutos según tu conexión:
aws s3 cp dataset/COIL_dataset_glosas_salud_1_2M.csv    s3://$bucket/bronze/solicitudes/
```

#### B.4 — Crear el Glue Job

AWS Console → **AWS Glue** → **ETL Jobs** → **Create job** → **Script editor**

| Campo | Valor |
|---|---|
| Job name | `coil-bigdata-salud-spark-batch-processor` |
| IAM Role | `LabRole` |
| Glue version | Glue 4.0 |
| Script path | `s3://<bucket>/scripts/aws_glue_job.py` |
| Worker type | G.1X |
| Number of workers | 2 |
| Timeout | 120 min |

**Job parameters** (Advanced properties):

| Key | Value |
|---|---|
| `--S3_BUCKET_NAME` | `coil-bigdata-salud-datalake-XXXXXXXXXXXX-dev` |
| `--SOURCE_PREFIX` | `bronze/solicitudes/` |
| `--TARGET_PREFIX` | `gold/curated_solicitudes/` |
| `--QUARANTINE_PREFIX` | `quarantine/solicitudes/` |
| `--VERSION_CATALOGO` | `2026.1` |
| `--TempDir` | `s3://<bucket>/temp/` |
| `--enable-metrics` | `true` |

#### B.5 — Crear el Athena WorkGroup

AWS Console → **Athena** → **WorkGroups** → **Create**  
Name: `coil-bigdata-salud-analytics-wg`  
Query result location: `s3://<bucket>/athena-results/`  
Encryption: SSE-S3

#### B.6 — Ejecutar el DDL en Athena

1. Athena → **Query editor** → selecciona workgroup
2. Abre `infrastructure/athena_ddl.sql`
3. Reemplaza todas las ocurrencias de `${S3_BUCKET_NAME}` con tu bucket real
4. Ejecuta las secciones en orden: CREATE DATABASE → CREATE TABLE gold → CREATE TABLE quarantine → CREATE VIEWs

---

## FASE 4 — Arrancar la aplicación

```powershell
# Sin Docker (más rápido para pruebas):
# Terminal 1
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2
streamlit run app/main.py --server.port 8501

# ── O con el script automático ──
.\start_local.ps1

# ── O con Docker ──
docker-compose up --build
```

Accede: `http://localhost:8501` → login: `admin / coil2026`

---

## FASE 5 — Verificar conexión desde el Dashboard

1. **☁️ Consola AWS** → pestaña **Estado** → **Verificar conexión**
2. Debes ver `✅ Conexión exitosa con AWS`

---

## FASE 6 — Preparar S3 desde el Dashboard

En **☁️ Consola AWS → S3**:

1. **1. Subir catálogos** → ✅
2. **2. Subir script Glue** → ✅
3. Elige `COIL_dataset_glosas_salud_1_2M.csv` → **3. Subir dataset** (2–5 min)

---

## FASE 7 — Lanzar el Glue Job

En **⚙️ Procesamiento COIL** o **☁️ Consola AWS → Glue Job**:

1. Clic **🚀 Lanzar Glue Job en AWS**
2. Anota el Job Run ID
3. Monitorea: `STARTING → RUNNING → SUCCEEDED` (~1–3 minutos para 1.2M)

---

## FASE 8 — Reparar particiones en Athena

Después de `SUCCEEDED`:

En **☁️ Consola AWS → Athena → Reparar tabla**:
- Selecciona `gold_solicitudes_cobertura` → **🔧 Reparar tabla**

O desde la consola AWS → Athena → Query Editor:
```sql
MSCK REPAIR TABLE coil_bigdata_salud_db.gold_solicitudes_cobertura;
```

---

## FASE 9 — Ver resultados

| Módulo | Fuente de datos |
|---|---|
| 📊 Dashboard | `v_resumen_cobertura_ejecutivo` (Athena) |
| 📋 Glosas | `gold_solicitudes_cobertura` (Athena, paginado) |
| 🚧 Cuarentena | `quarentena_solicitudes` (Athena) |
| ☁️ Consola AWS → Athena → Vistas | 3 vistas analíticas predefinidas |

---

## FASE 10 — Renovar credenciales (cada ~4 horas)

Cuando veas `ExpiredTokenException`:

1. Learner Lab → **AWS Details** → **Show** → copia los 3 nuevos valores
2. Edita `.env` con los nuevos `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`
3. Reinicia la API:
   ```powershell
   # Sin Docker: Ctrl+C → uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
   # Con Docker:
   docker-compose restart api
   ```
4. **☁️ Consola AWS → Verificar conexión** → debe estar verde

---

## Troubleshooting

| Error | Causa | Solución |
|---|---|---|
| `No module named 'awsglue'` | Ejecutar `aws_glue_job.py` localmente | Solo corre en AWS Glue — usa `batch_processor` en local |
| `ExpiredTokenException` | Session token expirado | Seguir Fase 10 |
| Athena retorna 0 filas | Particiones no registradas | Ejecutar MSCK REPAIR TABLE (Fase 8) |
| `Access Denied` en Glue | LabRole sin permisos | Verificar que el Job usa el rol `LabRole` |
| `BucketAlreadyExists` | Nombre de bucket ya tomado | Agregar número de cuenta al nombre |
| Dashboard muestra "Sin datos" | Job no terminó o falta REPAIR | Verificar estado Job → ejecutar REPAIR |
| "Invalid token" en dashboard | JWT expirado (8h) | Cerrar sesión → volver a iniciar sesión |

---

## Costos estimados

| Operación | Costo |
|---|---|
| Glue Job 2 DPUs × 2 min | ~$0.002 USD |
| S3 almacenamiento 1 GB/mes | ~$0.023 USD |
| Athena sin filtros (1 TB) | $5.00 USD |
| **Athena con filtros de partición** | **< $0.001 USD** |
| **Corrida diaria completa** | **~$0.10 USD** |
| **Presupuesto $50 → corridas posibles** | **~500** |

---

## Referencia rápida de comandos CLI

```powershell
# Verificar credenciales
aws sts get-caller-identity

# Listar bucket
aws s3 ls s3://$env:S3_BUCKET_NAME --recursive

# Estado del Glue Job
aws glue get-job-runs --job-name coil-bigdata-salud-spark-batch-processor --max-results 5

# Lanzar Glue Job
aws glue start-job-run --job-name coil-bigdata-salud-spark-batch-processor

# Consulta Athena
aws athena start-query-execution `
    --query-string "SELECT COUNT(*) FROM coil_bigdata_salud_db.gold_solicitudes_cobertura" `
    --work-group coil-bigdata-salud-analytics-wg `
    --query-execution-context Database=coil_bigdata_salud_db
```
