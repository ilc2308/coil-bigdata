"""
pages/page_03_procesamiento.py
Módulo de procesamiento COIL por lotes.

Permite:
- Configurar y lanzar una corrida de procesamiento
- Monitorear el progreso en tiempo real
- Ver métricas de la corrida completada
- Lanzar el Glue Job en AWS (modo aws)
"""

from __future__ import annotations
import time
import streamlit as st
from app.components.auth import api_get, api_post
from app.components.charts import conciliacion_gauge


def render():
    st.title("⚙️ Procesamiento COIL")
    st.caption("Ejecutar el procesador por lotes de órdenes médicas.")

    # Detectar modo
    config_data = api_get("/api/v1/config") or {}
    app_mode = config_data.get("app_mode", "local")

    if app_mode == "aws":
        _render_aws_mode(config_data)
    else:
        _render_local_mode()


def _render_local_mode():
    """Procesamiento local con batch_processor.py."""
    st.subheader("Modo LOCAL — Procesamiento por lotes")

    tab_new, tab_monitor, tab_history = st.tabs(
        ["🚀 Nueva corrida", "📡 Monitoreo", "📋 Historial"]
    )

    # ---------------------------------------------------------------
    # TAB 1: Nueva corrida
    # ---------------------------------------------------------------
    with tab_new:
        selected_file = st.session_state.get("selected_file", "")

        st.markdown("#### Configuración de la corrida")

        col_file, col_opts = st.columns([2, 1])

        with col_file:
            # Obtener lista de archivos disponibles
            files_data = api_get("/api/v1/uploads") or {}
            all_files = (
                [f["filename"] for f in files_data.get("uploaded", [])] +
                [f["filename"] for f in files_data.get("dataset", [])]
            )

            if not all_files:
                st.warning("No hay archivos disponibles. Ve a **Carga de Datos** primero.")
                return

            default_idx = all_files.index(selected_file) if selected_file in all_files else 0
            filename = st.selectbox(
                "Archivo CSV a procesar",
                options=all_files,
                index=default_idx,
                help="Selecciona el archivo de órdenes a procesar",
            )

        with col_opts:
            write_parquet = st.checkbox(
                "Escribir Parquet (recomendado)",
                value=True,
                help="Genera archivos Parquet comprimidos en Snappy. Más rápido para consultas.",
            )
            chunk_size = st.select_slider(
                "Chunk de progreso",
                options=[10000, 50000, 100000, 200000, 500000],
                value=100000,
                format_func=lambda x: f"{x:,}",
                help="Cada cuántas filas se reporta progreso",
            )
            custom_run_id = st.text_input(
                "ID de corrida (opcional)",
                placeholder="RUN-YYYYMMDDHHMMSS-xxxxxx",
                help="Deja vacío para generar automáticamente",
            )

        st.markdown("---")

        col_btn, col_info = st.columns([1, 3])
        with col_btn:
            launch = st.button("🚀 Iniciar Procesamiento", type="primary", use_container_width=True)
        with col_info:
            if filename:
                size_info = ""
                for flist in [files_data.get("uploaded", []), files_data.get("dataset", [])]:
                    for f in flist:
                        if f["filename"] == filename:
                            size_info = f"({f['size_mb']:.1f} MB)"
                st.markdown(
                    f"⚡ Archivo seleccionado: **`{filename}`** {size_info}  \n"
                    f"📦 Formato salida: **{'Parquet (Snappy)' if write_parquet else 'CSV'}**"
                )

        if launch:
            payload = {
                "filename": filename,
                "chunk_size": chunk_size,
                "write_parquet": write_parquet,
            }
            if custom_run_id.strip():
                payload["run_id"] = custom_run_id.strip()

            with st.spinner("Enviando solicitud a la API…"):
                result = api_post("/api/v1/process", payload)

            if result:
                run_id = result.get("run_id", "")
                st.success(f"✅ Corrida iniciada: **{run_id}**")
                st.session_state["current_run_id"] = run_id
                st.info("Ve a la pestaña **Monitoreo** para seguir el progreso.")
            else:
                st.error("❌ Error al iniciar el procesamiento.")

    # ---------------------------------------------------------------
    # TAB 2: Monitoreo en tiempo real
    # ---------------------------------------------------------------
    with tab_monitor:
        current_run_id = st.session_state.get("current_run_id", "")

        if not current_run_id:
            st.info("Lanza una corrida desde la pestaña **Nueva corrida** para monitorizarla aquí.")
            return

        st.markdown(f"#### Monitoreando: `{current_run_id}`")

        status_placeholder = st.empty()
        metrics_placeholder = st.empty()

        auto_refresh = st.checkbox("🔄 Auto-actualizar cada 3 segundos", value=True)

        def _show_status():
            data = api_get(f"/api/v1/process/{current_run_id}")
            if not data:
                status_placeholder.warning("No se pudo obtener el estado.")
                return False

            status = data.get("status", "unknown")
            progress = data.get("progress_pct", 0.0)

            with status_placeholder.container():
                color_map = {
                    "pending":   "🟡",
                    "running":   "🔵",
                    "completed": "🟢",
                    "failed":    "🔴",
                }
                icon = color_map.get(status, "⚪")
                st.markdown(f"**Estado:** {icon} `{status.upper()}`")

                if status == "running":
                    st.progress(min(progress / 100, 1.0), text=f"{progress:.0f}% completado")
                elif status == "completed":
                    st.progress(1.0, text="✅ Completado")
                elif status == "failed":
                    st.error(f"Error: {data.get('error', 'desconocido')}")

            # Mostrar métricas si está completo
            if status == "completed" and data.get("metrics"):
                _show_run_metrics(metrics_placeholder, data["metrics"])

            return status in ("completed", "failed")

        done = _show_status()

        if not done and auto_refresh:
            time.sleep(3)
            st.rerun()

        col_r1, col_r2 = st.columns(2)
        if col_r1.button("🔄 Actualizar ahora"):
            st.rerun()
        if col_r2.button("🗑️ Limpiar selección"):
            st.session_state.pop("current_run_id", None)
            st.rerun()

    # ---------------------------------------------------------------
    # TAB 3: Historial de corridas
    # ---------------------------------------------------------------
    with tab_history:
        st.markdown("#### Corridas anteriores")
        jobs_data = api_get("/api/v1/process") or {}
        jobs = jobs_data.get("jobs", [])

        metrics_data = api_get("/api/v1/metrics") or {}
        runs = metrics_data.get("runs", [])

        if not jobs and not runs:
            st.info("No hay corridas registradas en esta sesión.")
            return

        import pandas as pd

        if runs:
            cols_map = {
                "id_corrida": "ID",
                "timestamp_fin": "Completado",
                "total_recibidas": "Recibidas",
                "total_procesadas": "Procesadas",
                "total_cuarentena": "Cuarentena",
                "duracion_segundos": "Duración (s)",
                "rendimiento_ordenes_por_segundo": "Órd/s",
                "porcentaje_cubiertas": "% Cob.",
                "formato_salida": "Formato",
            }
            df = pd.DataFrame(runs)
            available_cols = [c for c in cols_map.keys() if c in df.columns]
            df_display = df[available_cols].rename(columns=cols_map)
            st.dataframe(df_display, use_container_width=True, hide_index=True)

            # Selector para ver detalles
            run_ids = [r["id_corrida"] for r in runs]
            sel_run = st.selectbox("Ver detalles de corrida:", run_ids, key="hist_run_sel")
            if sel_run:
                detail = api_get(f"/api/v1/metrics/{sel_run}")
                if detail:
                    st.json(detail)


def _show_run_metrics(placeholder, metrics: dict):
    """Muestra métricas de una corrida completada."""
    with placeholder.container():
        st.divider()
        st.markdown("#### 📊 Resultados de la corrida")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Recibidas", f"{metrics.get('total_recibidas', 0):,}")
        c2.metric("Procesadas", f"{metrics.get('total_procesadas', 0):,}")
        c3.metric("Cubiertas", f"{metrics.get('total_cubiertas', 0):,}")
        c4.metric("Cuarentena", f"{metrics.get('total_cuarentena', 0):,}")

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Duración", f"{metrics.get('duracion_segundos', 0):.2f} s")
        c6.metric("Rendimiento", f"{metrics.get('rendimiento_ordenes_por_segundo', 0):,.0f} órd/s")
        c7.metric("% Cobertura", f"{metrics.get('porcentaje_cubiertas', 0):.1f}%")
        c8.metric("Costo AWS est.", f"${metrics.get('estimacion_costo_aws_usd', 0):.6f}")

        ci = metrics.get("conciliacion_integridad", {})
        col_g, col_v = st.columns([1, 2])
        with col_g:
            st.plotly_chart(
                conciliacion_gauge(ci.get("estado", ""), ci.get("diferencia", 0)),
                use_container_width=True,
            )
        with col_v:
            val_sol = metrics.get("valor_solicitado_total_cop", 0)
            val_rec = metrics.get("valor_reconocido_total_cop", 0)
            st.metric("Valor Solicitado", f"${val_sol:,.0f} COP")
            st.metric("Valor Reconocido", f"${val_rec:,.0f} COP")
            brecha = val_sol - val_rec
            st.metric("Brecha", f"${brecha:,.0f} COP")


def _render_aws_mode(config_data: dict):
    """Procesamiento en modo AWS via Glue Job."""
    st.subheader("Modo AWS — AWS Glue Spark Job")
    st.info(
        f"🌩️ Glue Job: `{config_data.get('glue_job', 'N/A')}`  \n"
        f"🗄️ Bucket S3: `{config_data.get('s3_bucket', 'N/A')}`"
    )

    st.warning(
        "⚠️ El modo AWS lanzará el Glue Job en tu cuenta de AWS Academy Learner Lab. "
        "Esto genera costos reales. Confirma antes de continuar."
    )

    if st.button("🚀 Lanzar Glue Job en AWS", type="primary"):
        result = api_post("/api/v1/process/aws")
        if result:
            job_run_id = result.get("job_run_id", "")
            st.success(f"✅ Glue Job lanzado. Job Run ID: `{job_run_id}`")
            st.session_state["glue_run_id"] = job_run_id
        else:
            st.error("Error al lanzar el Glue Job.")

    if st.session_state.get("glue_run_id"):
        run_id = st.session_state["glue_run_id"]
        status_data = api_get(f"/api/v1/process/{run_id}")
        if status_data:
            st.json(status_data)
