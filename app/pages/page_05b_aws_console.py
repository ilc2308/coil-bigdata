"""
pages/page_05b_aws_console.py
Consola de integración AWS para el dashboard COIL.

Disponible solo cuando APP_MODE=aws.
Permite:
  - Verificar conexión con AWS
  - Ver resumen del bucket S3 por capas
  - Subir datos y catálogos a S3
  - Lanzar y monitorear el Glue Job
  - Consultar vistas analíticas de Athena
  - Ejecutar MSCK REPAIR TABLE
"""

from __future__ import annotations
import time
import streamlit as st
from app.components.auth import api_get, api_post


def render():
    st.title("☁️ Consola AWS")
    st.caption("Integración con Amazon S3, AWS Glue y Amazon Athena")

    # Verificar modo
    config = api_get("/api/v1/config") or {}
    if config.get("app_mode", "local") != "aws":
        st.warning(
            "⚠️ Esta página requiere **APP_MODE=aws** en el archivo `.env`. "
            "Actualmente estás en modo **LOCAL**."
        )
        st.info(
            "Para activar el modo AWS:\n"
            "1. Edita `.env` con `APP_MODE=aws`\n"
            "2. Agrega `S3_BUCKET_NAME`, credenciales y región\n"
            "3. Reinicia la API"
        )
        _show_env_template()
        return

    tab_status, tab_s3, tab_glue, tab_athena = st.tabs([
        "🔌 Estado", "🗄️ S3", "⚙️ Glue Job", "🔍 Athena"
    ])

    # ---------------------------------------------------------------
    # TAB 1: Estado de la conexión
    # ---------------------------------------------------------------
    with tab_status:
        st.markdown("#### Estado de la Conexión AWS")
        if st.button("🔄 Verificar conexión", type="primary"):
            with st.spinner("Verificando credenciales AWS…"):
                status_data = api_get("/api/v1/aws/status")

            if status_data:
                st.success("✅ Conexión exitosa con AWS")
                col1, col2, col3 = st.columns(3)
                col1.metric("Cuenta AWS", status_data.get("account", "N/A"))
                col2.metric("Región", status_data.get("region", "N/A"))
                col3.metric("Bucket", status_data.get("bucket", "N/A"))

                st.markdown("**Recursos configurados:**")
                st.code(f"Glue Job:    {status_data.get('glue_job', '')}")
                st.code(f"Athena DB:   {status_data.get('athena_db', '')}")
                st.code(f"WorkGroup:   {status_data.get('workgroup', '')}")
                st.code(f"ARN:         {status_data.get('arn', '')}")
            else:
                st.error(
                    "❌ No se puede conectar con AWS. Verifica:\n"
                    "- `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY` en .env\n"
                    "- `AWS_SESSION_TOKEN` (requerido en Learner Lab)\n"
                    "- El token de sesión del Learner Lab dura ~4 horas"
                )

        st.divider()
        st.markdown("**Credenciales del AWS Academy Learner Lab**")
        st.info(
            "Los tokens del Learner Lab expiran cada ~4 horas. "
            "Para renovarlos:\n"
            "1. Abre el Learner Lab en AWS Academy\n"
            "2. Clic en **AWS Details** → **Show**\n"
            "3. Copia las 3 variables y actualiza tu `.env`\n"
            "4. Reinicia la API"
        )
        st.code(
            "AWS_ACCESS_KEY_ID=ASIA...\n"
            "AWS_SECRET_ACCESS_KEY=...\n"
            "AWS_SESSION_TOKEN=...",
            language="bash",
        )

    # ---------------------------------------------------------------
    # TAB 2: S3
    # ---------------------------------------------------------------
    with tab_s3:
        st.markdown("#### Estado del Bucket S3")

        col_btn, _ = st.columns([1, 3])
        with col_btn:
            load_s3 = st.button("📊 Cargar resumen S3", key="load_s3")

        if load_s3:
            with st.spinner("Consultando S3…"):
                summary = api_get("/api/v1/aws/s3/summary")
            if summary:
                st.success(f"✅ Bucket: `{summary.get('bucket', '')}`")
                layers = summary.get("layers", {})
                cols = st.columns(len(layers))
                icons = {"bronze": "🥉", "gold": "🥇", "quarantine": "🚧",
                         "catalogs": "📋", "scripts": "📄", "athena": "🔍"}
                for col, (layer, info) in zip(cols, layers.items()):
                    with col:
                        st.metric(
                            f"{icons.get(layer,'📁')} {layer.upper()}",
                            f"{info['total_objects']} obj",
                            f"{info['total_size_mb']:.1f} MB",
                        )

        st.divider()
        st.markdown("#### Preparar S3 para el Glue Job")
        st.caption("Ejecuta estos pasos en orden antes de lanzar el Glue Job por primera vez.")

        col_a, col_b, col_c = st.columns(3)

        with col_a:
            if st.button("📋 1. Subir catálogos", use_container_width=True):
                with st.spinner("Subiendo catálogos…"):
                    r = api_post("/api/v1/aws/s3/upload-catalogs", {})
                if r:
                    st.success("✅ Catálogos en S3")
                    st.json(r.get("uploaded", {}))

        with col_b:
            if st.button("📄 2. Subir script Glue", use_container_width=True):
                with st.spinner("Subiendo aws_glue_job.py…"):
                    r = api_post("/api/v1/aws/s3/upload-script", {})
                if r:
                    st.success("✅ Script en S3/scripts/")
                    st.code(r.get("uploaded", {}).get("script_s3_url", ""))

        with col_c:
            files_data = api_get("/api/v1/uploads") or {}
            all_files = (
                [f["filename"] for f in files_data.get("dataset", [])] +
                [f["filename"] for f in files_data.get("uploaded", [])]
            )
            dataset_file = st.selectbox("Archivo a subir", all_files or ["(ninguno)"], key="s3_file")
            if st.button("📦 3. Subir dataset", use_container_width=True):
                if dataset_file and dataset_file != "(ninguno)":
                    with st.spinner(f"Subiendo {dataset_file} a Bronze…"):
                        import requests as req_lib
                        from app.components.auth import api_headers, get_api_base
                        r2 = req_lib.post(
                            f"{get_api_base()}/api/v1/aws/s3/upload-dataset",
                            headers=api_headers(),
                            json={"filename": dataset_file},
                            timeout=300,
                        )
                    if r2.status_code == 200:
                        st.success(f"✅ {dataset_file} en S3/bronze/")
                        st.code(r2.json().get("s3_url", ""))
                    else:
                        st.error(r2.text)

        st.divider()
        st.markdown("#### Explorador S3")
        prefix = st.text_input("Prefijo S3", value="bronze/", key="s3_prefix")
        if st.button("🔍 Listar objetos", key="s3_list_btn"):
            objs = api_get("/api/v1/aws/s3/list", params={"prefix": prefix, "max_keys": 50}) or {}
            if objs.get("objects"):
                import pandas as pd
                st.dataframe(pd.DataFrame(objs["objects"]), use_container_width=True, hide_index=True)
            else:
                st.info("Sin objetos en este prefijo.")

    # ---------------------------------------------------------------
    # TAB 3: Glue Job
    # ---------------------------------------------------------------
    with tab_glue:
        st.markdown("#### AWS Glue Spark Job")
        st.info(
            f"Job: `{config.get('glue_job', 'N/A')}`  \n"
            "Procesa los datos de la capa Bronze → Gold en Apache Spark 3.x  \n"
            "Costo estimado: ~**$0.10 USD** por corrida (2 workers G.1X, ~2 min)"
        )

        st.warning(
            "⚠️ Lanzar el Job genera costos reales en tu Learner Lab. "
            "Presupuesto disponible: $50 USD."
        )

        col_launch, col_hist = st.columns(2)

        with col_launch:
            if st.button("🚀 Lanzar Glue Job", type="primary", use_container_width=True):
                result = api_post("/api/v1/process/aws", {})
                if result:
                    run_id = result.get("job_run_id", "")
                    st.success(f"✅ Job lanzado: `{run_id}`")
                    st.session_state["glue_run_id"] = run_id
                    st.info("Consulta el historial para ver el estado.")

        with col_hist:
            if st.button("📋 Ver historial", use_container_width=True):
                hist = api_get("/api/v1/aws/glue/runs") or {}
                runs = hist.get("runs", [])
                if runs:
                    import pandas as pd
                    df_runs = pd.DataFrame(runs)
                    st.dataframe(df_runs, use_container_width=True, hide_index=True)
                else:
                    st.info("Sin ejecuciones registradas.")

        # Monitoreo de un Job Run específico
        if st.session_state.get("glue_run_id"):
            run_id = st.session_state["glue_run_id"]
            st.divider()
            st.markdown(f"**Monitoreando:** `{run_id}`")

            status_data = api_get(f"/api/v1/aws/glue/{run_id}")
            if status_data:
                s = status_data.get("status", "UNKNOWN")
                color_map = {"RUNNING": "🔵", "SUCCEEDED": "🟢",
                             "FAILED": "🔴", "STARTING": "🟡"}
                st.markdown(f"Estado: {color_map.get(s,'⚪')} **{s}**")

                c1, c2, c3 = st.columns(3)
                c1.metric("Inicio", status_data.get("started_on", "")[:19])
                c2.metric("Duración", f"{status_data.get('execution_time_seconds', 0)} s")
                c3.metric("Costo est.", f"${status_data.get('estimated_cost_usd', 0):.4f} USD")

                if status_data.get("error_message"):
                    st.error(f"Error: {status_data['error_message']}")

                if s not in ("SUCCEEDED", "FAILED", "ERROR", "TIMEOUT", "STOPPED"):
                    if st.button("🔄 Actualizar estado"):
                        st.rerun()

    # ---------------------------------------------------------------
    # TAB 4: Athena
    # ---------------------------------------------------------------
    with tab_athena:
        st.markdown("#### Amazon Athena — Motor SQL Serverless")
        st.caption(
            "⚠️ Athena cobra **$5 por TB** de datos escaneados. "
            "Usa filtros de partición para reducir costos."
        )

        subtab_views, subtab_query, subtab_repair = st.tabs([
            "📊 Vistas Analíticas", "🔍 SQL Libre", "🔧 Reparar Tabla"
        ])

        with subtab_views:
            st.markdown("**Consultar vistas ejecutivas predefinidas**")
            view_options = {
                "Resumen Cobertura Ejecutivo": "v_resumen_cobertura_ejecutivo",
                "Análisis Canal y Entidad": "v_analisis_canal_entidad",
                "Auditoría Servicios y Alertas": "v_auditoria_servicios_alertas",
            }
            view_label = st.selectbox("Vista", list(view_options.keys()), key="view_sel")
            max_rows_view = st.slider("Máximo de filas", 10, 500, 100, key="view_maxrows")

            if st.button("🔍 Consultar vista", type="primary", key="btn_view"):
                with st.spinner("Ejecutando en Athena…"):
                    data = api_get(
                        "/api/v1/aws/athena/views",
                        params={"view": view_options[view_label], "max_rows": max_rows_view},
                    )
                if data and data.get("rows"):
                    import pandas as pd
                    df = pd.DataFrame(data["rows"])
                    st.metric("Filas retornadas", len(df))
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    csv = df.to_csv(index=False).encode("utf-8")
                    st.download_button("⬇️ Exportar CSV", csv,
                                       f"{view_options[view_label]}.csv", "text/csv")
                else:
                    st.info("Sin resultados o error en la consulta.")

        with subtab_query:
            st.markdown("**SQL libre (solo SELECT)**")
            st.caption("Las consultas DDL/DML están bloqueadas por seguridad.")

            default_sql = (
                f"SELECT decision, perfil_cobertura, COUNT(*) as total\n"
                f"FROM {config.get('athena_database', 'coil_bigdata_salud_db')}"
                f".gold_solicitudes_cobertura\n"
                f"GROUP BY decision, perfil_cobertura\n"
                f"ORDER BY total DESC\nLIMIT 20;"
            )
            sql = st.text_area("SQL", value=default_sql, height=120, key="athena_sql")
            max_rows_sql = st.number_input("Máx filas", 1, 1000, 100, key="sql_maxrows")

            if st.button("▶️ Ejecutar", type="primary", key="btn_sql"):
                with st.spinner("Ejecutando en Athena…"):
                    result = api_post(
                        "/api/v1/aws/athena/query",
                        {"sql": sql, "max_rows": int(max_rows_sql), "timeout_seconds": 120},
                    )
                if result:
                    rows = result.get("rows", [])
                    st.metric("Filas", len(rows))
                    if rows:
                        import pandas as pd
                        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                else:
                    st.error("Error ejecutando la consulta.")

        with subtab_repair:
            st.markdown("**MSCK REPAIR TABLE**")
            st.info(
                "Ejecuta después de cada Glue Job para que Athena detecte "
                "las nuevas particiones (`fecha_particion`) creadas en S3."
            )
            table_to_repair = st.radio(
                "Tabla",
                ["gold_solicitudes_cobertura", "quarentena_solicitudes"],
                key="repair_table",
            )
            if st.button("🔧 Reparar tabla", key="btn_repair"):
                with st.spinner(f"Ejecutando MSCK REPAIR TABLE {table_to_repair}…"):
                    result = api_post(
                        "/api/v1/aws/athena/repair",
                        {"table": table_to_repair},
                    )
                if result:
                    st.success(f"✅ {result.get('message', 'OK')}")
                    st.json(result.get("result", {}))


def _show_env_template():
    """Muestra el template .env para modo AWS."""
    st.markdown("#### Template .env para AWS Academy Learner Lab")
    st.code("""
# Edita tu .env con estos valores:
APP_MODE=aws

# Del AWS Academy Learner Lab → AWS Details → Show:
AWS_ACCESS_KEY_ID=ASIA...
AWS_SECRET_ACCESS_KEY=...
AWS_SESSION_TOKEN=...
AWS_DEFAULT_REGION=us-east-1

# Nombre del bucket creado por CloudFormation:
S3_BUCKET_NAME=coil-bigdata-salud-datalake-<ACCOUNT_ID>-dev
    """, language="bash")
