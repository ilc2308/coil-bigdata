"""
pages/page_08_reportes.py
Módulo de generación y descarga de reportes.

Formatos disponibles:
- CSV: órdenes gold (filtrado), cuarentena, métricas de corridas
- Excel: reporte ejecutivo completo con 4 hojas
"""

from __future__ import annotations
import streamlit as st
from app.components.auth import api_download


def render():
    st.title("📥 Reportes y Exportación")
    st.caption("Descarga los datos procesados en formato CSV o Excel para análisis externo.")

    tab_csv, tab_excel = st.tabs(["📄 CSV", "📊 Excel (Ejecutivo)"])

    # ---------------------------------------------------------------
    # TAB 1: Reportes CSV
    # ---------------------------------------------------------------
    with tab_csv:
        st.markdown("#### Exportar a CSV")

        report_type = st.radio(
            "Tipo de reporte",
            ["Órdenes Gold", "Cuarentena", "Historial de Corridas"],
            horizontal=True,
            key="csv_report_type",
        )

        # ---- Órdenes Gold ----
        if report_type == "Órdenes Gold":
            st.markdown("**Parámetros del reporte**")

            col1, col2, col3 = st.columns(3)
            with col1:
                r_decision = st.selectbox(
                    "Decisión",
                    ["", "CUBRE", "NO CUBRE"],
                    format_func=lambda x: "Todas" if not x else x,
                    key="r_decision",
                )
                r_perfil = st.selectbox(
                    "Perfil",
                    ["", "PRIORITARIO", "ESTANDAR", "COPAGO"],
                    format_func=lambda x: "Todos" if not x else x,
                    key="r_perfil",
                )
            with col2:
                r_fecha_desde = st.date_input("Fecha desde", value=None, key="r_fdesde")
                r_fecha_hasta = st.date_input("Fecha hasta", value=None, key="r_fhasta")
            with col3:
                r_entidad = st.text_input("Entidad emisora", key="r_entidad")
                r_max = st.select_slider(
                    "Máximo de filas",
                    options=[10_000, 50_000, 100_000, 200_000, 500_000],
                    value=100_000,
                    format_func=lambda x: f"{x:,}",
                    key="r_max",
                )

            params = {k: v for k, v in {
                "decision": r_decision,
                "perfil_cobertura": r_perfil,
                "fecha_desde": str(r_fecha_desde) if r_fecha_desde else "",
                "fecha_hasta": str(r_fecha_hasta) if r_fecha_hasta else "",
                "entidad_emisora": r_entidad,
                "max_rows": r_max,
            }.items() if v}

            col_btn, col_info = st.columns([1, 3])
            with col_btn:
                gen_gold = st.button("📥 Generar CSV", type="primary", use_container_width=True, key="gen_gold")
            with col_info:
                st.info(
                    f"Genera un CSV con hasta **{r_max:,}** registros. "
                    "Para el dataset completo de 1.2M, usa el script CLI o aumenta el límite."
                )

            if gen_gold:
                with st.spinner("Generando reporte… esto puede tardar unos segundos con datasets grandes"):
                    csv_bytes = api_download("/api/v1/reports/gold/csv", params=params, timeout=120)

                if csv_bytes:
                    st.success(f"✅ Reporte generado — {len(csv_bytes)/1024:.1f} KB")
                    st.download_button(
                        label="⬇️ Descargar coil_ordenes_gold.csv",
                        data=csv_bytes,
                        file_name="coil_ordenes_gold.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )

        # ---- Cuarentena ----
        elif report_type == "Cuarentena":
            st.markdown("**Exportar registros de cuarentena**")
            r_runid = st.text_input("Filtrar por ID corrida (opcional)", key="r_q_runid")

            if st.button("📥 Generar CSV Cuarentena", type="primary", key="gen_q"):
                params = {}
                if r_runid:
                    params["run_id"] = r_runid
                with st.spinner("Generando…"):
                    csv_bytes = api_download("/api/v1/reports/quarantine/csv", params=params)
                if csv_bytes:
                    st.download_button(
                        "⬇️ Descargar coil_cuarentena.csv",
                        data=csv_bytes,
                        file_name="coil_cuarentena.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )

        # ---- Métricas ----
        else:
            st.markdown("**Exportar historial de corridas**")
            st.caption("Incluye todos los campos de métricas de cada corrida ejecutada.")

            if st.button("📥 Generar CSV Métricas", type="primary", key="gen_m"):
                with st.spinner("Generando…"):
                    csv_bytes = api_download("/api/v1/reports/metrics/csv")
                if csv_bytes:
                    st.download_button(
                        "⬇️ Descargar coil_metricas_corridas.csv",
                        data=csv_bytes,
                        file_name="coil_metricas_corridas.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )

    # ---------------------------------------------------------------
    # TAB 2: Reporte Excel ejecutivo
    # ---------------------------------------------------------------
    with tab_excel:
        st.markdown("#### Reporte Ejecutivo Excel")
        st.markdown("""
        Genera un archivo `.xlsx` con **4 hojas** listas para presentación:

        | Hoja | Contenido |
        |------|-----------|
        | 📊 **Resumen Ejecutivo** | KPIs, métricas de la última corrida |
        | ✅ **Órdenes Cubiertas** | Hasta 25,000 registros con decisión CUBRE |
        | ❌ **Órdenes No Cubiertas** | Hasta 25,000 registros con decisión NO CUBRE |
        | 🚧 **Cuarentena** | Hasta 5,000 registros rechazados |
        | 📋 **Historial Corridas** | Todas las corridas ejecutadas |
        """)

        st.info(
            "💡 El Excel está limitado a 25,000 filas por hoja para mantener el archivo manejable. "
            "Para el dataset completo usa la exportación CSV."
        )

        if st.button("📊 Generar Reporte Excel", type="primary", use_container_width=True, key="gen_excel"):
            with st.spinner("Generando reporte Excel con múltiples hojas… puede tardar hasta 30 segundos"):
                excel_bytes = api_download("/api/v1/reports/gold/excel", timeout=120)

            if excel_bytes:
                size_kb = len(excel_bytes) / 1024
                st.success(f"✅ Reporte Excel generado — {size_kb:.0f} KB")
                st.download_button(
                    label="⬇️ Descargar coil_reporte_ejecutivo.xlsx",
                    data=excel_bytes,
                    file_name="coil_reporte_ejecutivo.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            else:
                st.error(
                    "No se pudo generar el Excel. "
                    "Verifica que `openpyxl` está instalado y hay datos en la capa gold."
                )
