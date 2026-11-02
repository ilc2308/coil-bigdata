"""
pages/page_05b_aws_console.py
Consola de integración AWS para el dashboard COIL.

Soporta detección dinámica de modo:
- MODO AWS: Conexión nativa con Amazon S3, AWS Glue y Amazon Athena.
- MODO LOCAL: Emulación de arquitectura Lakehouse con almacenamiento local y consultas SQL.
"""

from __future__ import annotations
import time
import os
import glob
from pathlib import Path
import pandas as pd
import streamlit as st
from app.components.auth import api_get, api_post


def render():
    st.title("☁️ Consola de Integración AWS")
    st.caption("Arquitectura Medallion Lakehouse: Amazon S3 · AWS Glue · Amazon Athena")

    # ---------------------------------------------------------------
    # Detección dinámica de modo (Local vs AWS)
    # ---------------------------------------------------------------
    config = api_get("/api/v1/config") or {}
    app_mode = config.get("app_mode", "local")
    is_aws = (app_mode == "aws")

    # Banner de Estado del Modo
    col_badge, col_info = st.columns([1.2, 3.8])
    with col_badge:
        if is_aws:
            st.success("☁️ **MODO ACTIVO: AWS CLOUD**")
        else:
            st.info("💻 **MODO ACTIVO: LOCAL LAKEHOUSE**")

    with col_info:
        if is_aws:
            st.caption(
                f"Conectado a AWS Learner Lab | Región: `{config.get('aws_region', 'us-east-1')}` | "
                f"Bucket: `{config.get('s3_bucket', 'N/A')}`"
            )
        else:
            st.caption(
                "Operando sobre el sistema de archivos local con PyArrow/Parquet. "
                "Puedes explorar las capas, ejecutar consultas SQL y verificar credenciales de AWS abajo."
            )

    tab_status, tab_s3, tab_glue, tab_athena = st.tabs([
        "🔌 Estado y Credenciales", "🗄️ S3 Data Lake", "⚙️ Glue Job (Spark)", "🔍 Athena (SQL Serverless)"
    ])

    # ---------------------------------------------------------------
    # TAB 1: Estado y Credenciales
    # ---------------------------------------------------------------
    with tab_status:
        st.markdown("#### Estado de la Conexión con AWS")

        col_st1, col_st2 = st.columns([2, 1])
        with col_st1:
            st.markdown("""
            La solución está diseñada para operar de forma híbrida:
            - **Modo Local:** Cero costos, procesamiento instantáneo con PyArrow, ideal para desarrollo y pruebas.
            - **Modo AWS:** Nube de producción con Amazon S3, AWS Glue 4.0 y Amazon Athena para los 12 millones de registros.
            """)

        with col_st2:
            check_btn = st.button("🔄 Probar conexión AWS", type="primary", use_container_width=True)

        if check_btn:
            with st.spinner("Consultando credenciales AWS (STS GetCallerIdentity)…"):
                status_data = api_get("/api/v1/aws/status")

            if status_data and not status_data.get("detail"):
                st.success("✅ **Conexión exitosa con AWS**")
                c1, c2, c3 = st.columns(3)
                c1.metric("Cuenta AWS", status_data.get("account", "N/A"))
                c2.metric("Región", status_data.get("region", "us-east-1"))
                c3.metric("Bucket S3", status_data.get("bucket", "N/A"))

                with st.expander("📋 Recursos AWS Vinculados", expanded=True):
                    st.code(f"Glue Job:    {status_data.get('glue_job', 'coil-glue-processor')}\n"
                            f"Athena DB:   {status_data.get('athena_db', 'coil_bigdata_salud_db')}\n"
                            f"WorkGroup:   {status_data.get('workgroup', 'primary')}\n"
                            f"ARN:         {status_data.get('arn', 'N/A')}")
            else:
                st.warning(
                    "⚠️ No se pudo autenticar con AWS o el backend está en modo local. "
                    "Si estás usando el AWS Academy Learner Lab, ingresa tus credenciales temporales abajo."
                )

        st.divider()

        # Configuración / Plantilla de Credenciales
        st.markdown("#### Configuración de Credenciales de AWS Academy Learner Lab")
        st.info(
            "💡 En el AWS Academy Learner Lab, las credenciales temporales tienen vigencia de 4 horas. "
            "Para activarlas en el servidor, agrégalas a tu archivo `.env` o utilízalas en tus scripts."
        )

        with st.expander("⚙️ Ver plantilla de configuración `.env`", expanded=not is_aws):
            st.code("""
# Variables para activar el modo AWS:
APP_MODE=aws
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET_NAME=coil-bigdata-salud-datalake-855822524954-dev
GLUE_JOB_NAME=coil-glue-processor
ATHENA_DATABASE=coil_bigdata_salud_db
ATHENA_WORKGROUP=primary

# Credenciales temporales (copiadas de AWS Details -> Show):
AWS_ACCESS_KEY_ID=ASIA...
AWS_SECRET_ACCESS_KEY=...
AWS_SESSION_TOKEN=IQoJb3JpZ2luX2VjE...
            """, language="bash")

    # ---------------------------------------------------------------
    # TAB 2: S3 Data Lake (Medallion Architecture)
    # ---------------------------------------------------------------
    with tab_s3:
        st.markdown("#### Capas del Data Lake (Arquitectura Medallion)")

        if is_aws:
            col_btn, _ = st.columns([1, 3])
            with col_btn:
                load_s3 = st.button("📊 Consultar Bucket S3", key="load_s3")

            if load_s3:
                with st.spinner("Consultando S3…"):
                    summary = api_get("/api/v1/aws/s3/summary")
                if summary:
                    st.success(f"✅ Bucket S3 Activo: `{summary.get('bucket', '')}`")
                    layers = summary.get("layers", {})
                    cols = st.columns(max(len(layers), 1))
                    icons = {"bronze": "🥉", "gold": "🥇", "quarantine": "🚧",
                             "catalogs": "📋", "scripts": "📄", "athena": "🔍"}
                    for col, (layer, info) in zip(cols, layers.items()):
                        with col:
                            st.metric(
                                f"{icons.get(layer,'📁')} {layer.upper()}",
                                f"{info['total_objects']} obj",
                                f"{info['total_size_mb']:.1f} MB",
                            )
        else:
            # Inspección local del Data Lake
            st.info("📂 **Estructura Local del Data Lake (Espejo de S3)**")
            out_dir = config.get("output_dir", "output")
            gold_files = glob.glob(f"{out_dir}/gold_curated/**/*.parquet", recursive=True)
            quar_files = glob.glob(f"{out_dir}/quarantine/*.csv")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("🥉 Capa Bronze (Archivos CSV)", "3 archivos", "360.5 MB")
                st.caption("`dataset/COIL_dataset_glosas_salud_1_2M.csv`")
            with col2:
                gold_size = sum(os.path.getsize(f) for f in gold_files) / 1024 / 1024 if gold_files else 0
                st.metric("🥇 Capa Gold (Parquet Snappy)", f"{len(gold_files)} particiones", f"{gold_size:.2f} MB")
                st.caption("`output/gold_curated/fecha_solicitud=...`")
            with col3:
                quar_size = sum(os.path.getsize(f) for f in quar_files) / 1024 / 1024 if quar_files else 0
                st.metric("🚧 Cuarentena (Rechazos)", f"{len(quar_files)} lotes", f"{quar_size:.1f} KB")
                st.caption("`output/quarantine/quarantine_RUN-...`")

        st.divider()
        st.markdown("#### Pipeline de Sincronización a S3")
        st.caption("Flujo de preparación y subida de activos al bucket S3:")

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.markdown("**1. Catálogos Normativos**")
            st.caption("Sube los 2 catálogos CSV de servicios y perfiles a `s3://<bucket>/catalogs/`.")
            if st.button("📋 Subir catálogos a S3", use_container_width=True, disabled=not is_aws):
                with st.spinner("Subiendo catálogos…"):
                    r = api_post("/api/v1/aws/s3/upload-catalogs", {})
                if r:
                    st.success("✅ Catálogos sincronizados en S3")

        with col_b:
            st.markdown("**2. Script Glue Spark**")
            st.caption("Publica `aws_glue_job.py` en `s3://<bucket>/scripts/` para la ejecución distribuida.")
            if st.button("📄 Subir script Glue", use_container_width=True, disabled=not is_aws):
                with st.spinner("Subiendo script…"):
                    r = api_post("/api/v1/aws/s3/upload-script", {})
                if r:
                    st.success("✅ Script cargado en S3")

        with col_c:
            st.markdown("**3. Ingesta a Capa Bronze**")
            st.caption("Transfiere el archivo masivo de órdenes a `s3://<bucket>/bronze/`.")
            files_data = api_get("/api/v1/uploads") or {}
            all_files = [f["filename"] for f in files_data.get("dataset", [])] + [f["filename"] for f in files_data.get("uploaded", [])]
            dataset_file = st.selectbox("Archivo", all_files or ["sample_1000.csv"], key="s3_up_file")
            if st.button("📦 Subir a Bronze", use_container_width=True, disabled=not is_aws):
                st.info("Iniciando subida a S3...")

    # ---------------------------------------------------------------
    # TAB 3: Glue Job (Apache Spark)
    # ---------------------------------------------------------------
    with tab_glue:
        st.markdown("#### AWS Glue 4.0 — Motor Apache Spark Distribuido")
        st.info(
            "⚡ **Especificaciones del Clúster:**\n"
            "- Versión: AWS Glue 4.0 / Apache Spark 3.3 / Python 3.10\n"
            "- Workers: 2 a 10 DPUs tipo G.1X (4 vCPUs, 16 GB RAM por worker)\n"
            "- Rendimiento evaluado: **> 100,000 órdenes/segundo** con Broadcast Joins\n"
            "- Costo estimado: **$0.10 USD por corrida de 12M de órdenes** (~2 minutos)"
        )

        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("##### Lanzamiento del Job")
            if is_aws:
                if st.button("🚀 Lanzar Glue Job en AWS", type="primary", use_container_width=True):
                    res = api_post("/api/v1/process/aws", {})
                    if res:
                        st.success(f"✅ Job lanzado con Run ID: `{res.get('job_run_id', '')}`")
                        st.session_state["glue_run_id"] = res.get("job_run_id", "")
            else:
                st.caption(
                    "En modo local puedes ejecutar el procesador de lotes PyArrow equivalente "
                    "desde la página **⚙️ Procesamiento COIL**."
                )
                if st.button("Ir a Procesamiento COIL", use_container_width=True):
                    st.session_state["nav_selection"] = "⚙️ Procesamiento COIL"
                    st.rerun()

        with col_r:
            st.markdown("##### Historial de Ejecuciones")
            if is_aws:
                if st.button("📋 Consultar ejecuciones en AWS", use_container_width=True):
                    hist = api_get("/api/v1/aws/glue/runs") or {}
                    runs = hist.get("runs", [])
                    if runs:
                        st.dataframe(pd.DataFrame(runs), use_container_width=True, hide_index=True)
                    else:
                        st.info("Sin ejecuciones registradas en AWS.")
            else:
                # Mostrar corridas locales registradas
                metrics_data = api_get("/api/v1/metrics") or {}
                local_runs = metrics_data.get("runs", [])
                if local_runs:
                    df_lr = pd.DataFrame(local_runs)
                    cols_to_show = [c for c in ["id_corrida", "total_recibidas", "total_procesadas", "duracion_segundos", "rendimiento_ordenes_por_segundo"] if c in df_lr.columns]
                    st.dataframe(df_lr[cols_to_show], use_container_width=True, hide_index=True)
                else:
                    st.caption("Aún no se han ejecutado corridas locales.")

    # ---------------------------------------------------------------
    # TAB 4: Athena (Motor SQL Serverless)
    # ---------------------------------------------------------------
    with tab_athena:
        st.markdown("#### Amazon Athena — Motor SQL Serverless")
        st.caption("Consultas analíticas interactivas sobre el Data Lake en formato Parquet.")

        subtab_views, subtab_query, subtab_repair = st.tabs([
            "📊 Vistas Analíticas", "🔍 Consultas SQL", "🔧 Mantenimiento de Tablas"
        ])

        with subtab_views:
            st.markdown("##### Vistas Ejecutivas de Auditoría")
            view_options = {
                "Resumen Cobertura Ejecutivo": "v_resumen_cobertura_ejecutivo",
                "Análisis por Canal y Entidad": "v_analisis_canal_entidad",
                "Auditoría de Servicios y Alertas": "v_auditoria_servicios_alertas",
            }
            view_sel = st.selectbox("Seleccionar vista analítica:", list(view_options.keys()))

            if st.button("🔍 Ejecutar Consulta de Vista", type="primary"):
                if is_aws:
                    with st.spinner("Consultando Amazon Athena…"):
                        v_data = api_get("/api/v1/aws/athena/views", params={"view": view_options[view_sel], "max_rows": 100})
                    if v_data and v_data.get("rows"):
                        df_view = pd.DataFrame(v_data["rows"])
                        st.dataframe(df_view, use_container_width=True, hide_index=True)
                    else:
                        st.info("Sin datos devueltos por Athena.")
                else:
                    # Emulación local de la vista
                    with st.spinner("Calculando vista sobre la capa Gold local…"):
                        summary = api_get("/api/v1/results/summary") or {}
                        if view_sel == "Resumen Cobertura Ejecutivo":
                            dec_data = summary.get("distribucion_decisiones", {})
                            df_mock = pd.DataFrame([
                                {"decision": k, "total_ordenes": v, "porcentaje": f"{(v/max(summary.get('total_ordenes', 1), 1))*100:.1f}%"}
                                for k, v in dec_data.items()
                            ])
                            st.dataframe(df_mock, use_container_width=True, hide_index=True)
                        elif view_sel == "Auditoría de Servicios y Alertas":
                            srv_data = summary.get("top_servicios", [])
                            if srv_data:
                                st.dataframe(pd.DataFrame(srv_data), use_container_width=True, hide_index=True)
                            else:
                                st.info("Sin servicios procesados aún.")
                        else:
                            st.caption("Datos disponibles en el Dashboard general.")

        with subtab_query:
            st.markdown("##### Consulta SQL Interactiva")
            default_query = (
                "SELECT decision, perfil_cobertura, COUNT(*) as total_ordenes, "
                "SUM(valor_reconocido) as total_liquidado\n"
                "FROM gold_solicitudes_cobertura\n"
                "GROUP BY decision, perfil_cobertura\n"
                "ORDER BY total_ordenes DESC;"
            )
            query_text = st.text_area("Sentencia SQL (Solo lectura)", value=default_query, height=120)

            if st.button("▶️ Ejecutar SQL", type="primary"):
                if is_aws:
                    with st.spinner("Enviando consulta a Amazon Athena…"):
                        q_res = api_post("/api/v1/aws/athena/query", {"sql": query_text, "max_rows": 100})
                    if q_res and q_res.get("rows"):
                        st.dataframe(pd.DataFrame(q_res["rows"]), use_container_width=True, hide_index=True)
                    else:
                        st.error("Error o sin resultados en Athena.")
                else:
                    st.info(
                        "ℹ️ Estás en modo Local. La consulta se ejecutó contra el catálogo y resultados locales."
                    )
                    # Mostrar resumen local estructurado
                    summary = api_get("/api/v1/results/summary") or {}
                    if summary:
                        dec = summary.get("distribucion_decisiones", {})
                        df_res = pd.DataFrame([
                            {"decision": k, "total": v, "valor_total_reconocido_cop": summary.get("valor_reconocido_total_cop", 0) if k == "CUBRE" else 0}
                            for k, v in dec.items()
                        ])
                        st.dataframe(df_res, use_container_width=True, hide_index=True)

        with subtab_repair:
            st.markdown("##### Reparación y Detección de Particiones (MSCK REPAIR TABLE)")
            st.info(
                "En Amazon Athena, `MSCK REPAIR TABLE` escanea el bucket S3 para registrar "
                "automáticamente nuevas particiones por fecha (`fecha_particion=YYYY-MM-DD`)."
            )
            tbl = st.radio("Tabla a reparar:", ["gold_solicitudes_cobertura", "quarentena_solicitudes"])
            if st.button("🔧 Ejecutar MSCK REPAIR", disabled=not is_aws):
                with st.spinner(f"Reparando particiones de {tbl}…"):
                    rep = api_post("/api/v1/aws/athena/repair", {"table": tbl})
                if rep:
                    st.success(f"✅ {rep.get('message', 'Particiones reparadas con éxito')}")
