# AI-DLC Operations: Guía de Despliegue en AWS Academy Learner Lab
**Proyecto:** Solución Distribuida en la Nube para el Procesamiento Masivo de Órdenes Médicas en un Sistema Público de Salud  
**Marco Metodológico:** AWS Labs AI-DLC (`awslabs/aidlc-workflows`) - Fase de Operaciones

---

## 🌐 Enlaces de Acceso al Despliegue Activo en AWS

* 🖥️ **Dashboard Web:** [http://coilupbsalud.duckdns.org](http://coilupbsalud.duckdns.org)
* 📑 **Documentación Interactiva (Swagger):** [http://coilupbsalud.duckdns.org/docs](http://coilupbsalud.duckdns.org/docs)
* 💓 **Health Check:** [http://coilupbsalud.duckdns.org/health](http://coilupbsalud.duckdns.org/health)
* 🔐 **Credenciales:** `admin` / `coil2026`

---

## 1. Consideraciones del Entorno AWS Academy Learner Lab

El entorno del Learner Lab cuenta con restricciones particulares que fueron contempladas en el diseño:
* **Presupuesto límite:** \$50 USD de créditos por estudiante/equipo.
* **Sesiones temporizadas:** Las sesiones duran 4 horas continuas (se recomienda detener o apagar recursos al finalizar).
* **Rol IAM preconfigurado:** No se permite crear roles IAM arbitrarios; se debe utilizar obligatoriamente el rol existente `LabRole` (ARN: `arn:aws:iam::<AccountId>:role/LabRole`).
* **Servicios Habilitados:** Amazon S3, AWS Glue, Amazon Athena, CloudWatch, VPC, EC2.

---

## 2. Paso a Paso para el Despliegue en la Consola de AWS

### Paso 1: Iniciar el Laboratorio y Obtener el Nombre del Bucket
1. En el portal de AWS Academy, haz clic en **"Start Lab"** y espera a que el círculo se ponga verde.
2. Abre la **AWS Management Console**.
3. Selecciona la región preferida (por defecto **us-east-1** N. Virginia).

### Paso 2: Crear el Bucket de Amazon S3
1. Navega a **Amazon S3** > **Create bucket**.
2. Nombre sugerido: `coil-salud-chernovia-<tu-nombre-o-id>` (los nombres deben ser únicos globalmente).
3. Mantén marcada la opción **"Block all public access"** (Seguridad RNF-08).
4. Habilita el cifrado por defecto con **Amazon S3-managed keys (SSE-S3)**.
5. Haz clic en **Create bucket**.

### Paso 3: Crear Carpetas y Subir Archivos a S3
Dentro de tu bucket creado, crea las siguientes carpetas y sube los archivos correspondientes:

```
s3://<tu-bucket>/
├── catalogs/
│   ├── COIL_catalogo_servicios_cubiertos.csv
│   └── COIL_catalogo_perfiles_cobertura.csv
├── scripts/
│   └── aws_glue_job.py
└── bronze/
    └── solicitudes/
        ├── sample_1000.csv                    (Para prueba rápida de 1 minuto)
        └── COIL_dataset_glosas_salud_1_2M.csv (Para prueba de carga completa)
```

*(Si utilizas AWS CLI con credenciales activas del laboratorio, puedes ejecutar directamente el script provisto en el repositorio: `powershell -File infrastructure/deploy_aws_learner_lab.ps1 -BucketName <tu-bucket>`)*.

### Paso 4: Crear y Configurar el Job en AWS Glue
1. Navega a **AWS Glue** > **ETL jobs** (en el menú lateral).
2. Selecciona **Script editor** > **Spark** > **Python** > Haz clic en **Create**.
3. En la pestaña **Script**, copia y pega el contenido de `src/aws_glue_job.py` (o selecciona la opción para cargar desde S3 `s3://<tu-bucket>/scripts/aws_glue_job.py`).
4. Ve a la pestaña **Job details** y configura:
   * **Name:** `coil-bigdata-salud-spark-processor`
   * **IAM Role:** Selecciona **`LabRole`** del menú desplegable.
   * **Type:** Spark
   * **Glue version:** **Glue 4.0** (o Glue 5.0)
   * **Worker type:** **G.1X** (1 DPU = 4 vCPU, 16 GB)
   * **Requested number of workers:** **2** (suficiente para procesar 1.2M en < 3 minutos).
   * **Job timeout:** 30 minutos (evita consumo si olvidas apagar).
5. Despliega la sección **Advanced properties** > **Job parameters** y agrega los siguientes pares clave-valor:
   * `--S3_BUCKET_NAME` $\rightarrow$ `<tu-bucket>`
   * `--SOURCE_PREFIX` $\rightarrow$ `bronze/solicitudes/`
   * `--TARGET_PREFIX` $\rightarrow$ `gold/curated_solicitudes/`
   * `--QUARANTINE_PREFIX` $\rightarrow$ `quarantine/solicitudes/`
   * `--VERSION_CATALOGO` $\rightarrow$ `2026.1`
6. Haz clic en **Save** en la esquina superior derecha.

### Paso 5: Ejecutar el Glue Job
1. Haz clic en el botón **Run** (esquina superior derecha).
2. Pasa a la pestaña **Runs** para monitorear el progreso en tiempo real.
3. Observarás cómo el clúster Spark se inicializa, procesa el lote y finaliza con estado **Succeeded**.
4. Puedes revisar las métricas de CloudWatch y el tiempo exacto de cómputo.

### Paso 6: Configurar y Consultar con Amazon Athena
1. Navega a **Amazon Athena** > **Query editor**.
2. Si es la primera vez que usas Athena, haz clic en **Settings** > **Manage** y define la ubicación de resultados de consulta:  
   `s3://<tu-bucket>/athena-results/` > Haz clic en **Save**.
3. Vuelve a **Editor** y copia el contenido del archivo `infrastructure/athena_ddl.sql`, reemplazando `${S3_BUCKET_NAME}` por el nombre de tu bucket.
4. Ejecuta las consultas en orden:
   * Crear la base de datos `coil_bigdata_salud_db`.
   * Crear la tabla externa `gold_solicitudes_cobertura`.
   * Ejecutar: `MSCK REPAIR TABLE coil_bigdata_salud_db.gold_solicitudes_cobertura;` para que Athena reconozca las particiones por fecha.
   * Crear las vistas ejecutivas (`v_resumen_cobertura_ejecutivo`, `v_analisis_canal_entidad`).
5. Ejecuta:
   ```sql
   SELECT * FROM coil_bigdata_salud_db.v_resumen_cobertura_ejecutivo;
   ```
   Visualizarás el resumen consolidado de las órdenes cubiertas, no cubiertas y el valor exacto liquidado por perfil.

---

## 3. Lista de Verificación al Finalizar la Sesión (Cuidado de Presupuesto)
* [ ] Verificar que no existan Jobs de Glue en ejecución activa.
* [ ] Al finalizar las pruebas del proyecto, puedes vaciar el bucket de S3 o descargar los archivos Parquet para conservar la evidencia localmente.
* [ ] Cerrar la sesión de AWS Academy haciendo clic en **"End Lab"**.
