"""
pages/page_07_auditoria.py
Módulo de auditoría y trazabilidad.

Permite:
- Ver historial de corridas con métricas de conciliación
- Ejecutar el oráculo de validación independiente
- Parsear una glosa de prueba
- Verificar integridad matemática del sistema
"""

from __future__ import annotations
import streamlit as st
from app.components.auth import api_get, api_post
from app.components.charts import conciliacion_gauge, runs_timeline


def render():
    st.title("🔍 Auditoría y Trazabilidad")
    st.caption(
        "Verificación independiente de exactitud al 100% · "
        "Ley 1581 de 2012 · Seudonimización SHA-256"
    )

    tab_hist, tab_oracle, tab_parser = st.tabs([
        "📋 Historial de Corridas",
        "🔬 Oráculo de Validación",
        "🧬 Parser de Glosa",
    ])

    # ---------------------------------------------------------------
    # TAB 1: Historial de corridas
    # ---------------------------------------------------------------
    with tab_hist:
        st.markdown("#### Historial de Corridas con Métricas de Auditoría")

        audit_data = api_get("/api/v1/audit/runs") or {}
        runs_audit = audit_data.get("runs", [])

        if not runs_audit:
            st.info("No hay corridas registradas todavía.")
        else:
            import pandas as pd

            df_audit = pd.DataFrame(runs_audit).rename(columns={
                "id_corrida": "ID Corrida",
                "timestamp_fin": "Completado",
                "total_recibidas": "Recibidas",
                "total_procesadas": "Procesadas",
                "total_cuarentena": "Cuarentena",
                "conciliacion_estado": "Conciliación",
                "diferencia": "Diferencia",
                "cumple_sla_24h": "SLA 24h",
                "cumple_rendimiento_minimo": "Rend. OK",
                "porcentaje_cubiertas": "% Cobertura",
            })

            # Colorear estado de conciliación
            def _color_ci(val):
                if val == "CUADRADA_PERFECTA":
                    return "background-color: #D5F5E3; color: #1E8449"
                return "background-color: #FADBD8; color: #922B21"

            styled = df_audit.style.applymap(
                _color_ci,
                subset=["Conciliación"] if "Conciliación" in df_audit.columns else [],
            )
            st.dataframe(styled, use_container_width=True, hide_index=True)

            # Timeline
            full_runs = api_get("/api/v1/metrics") or {}
            all_runs = full_runs.get("runs", [])
            if all_runs:
                st.plotly_chart(
                    runs_timeline(all_runs[-10:], "Rendimiento histórico (últimas 10 corridas)"),
                    use_container_width=True,
                )

            # Detalle de una corrida
            st.divider()
            st.markdown("#### Detalle de Corrida")
            run_ids = [r["ID Corrida"] for r in df_audit.to_dict("records")]
            sel_run = st.selectbox("Seleccionar corrida:", run_ids, key="aud_run_sel")
            if sel_run:
                detail = api_get(f"/api/v1/metrics/{sel_run}")
                if detail:
                    col_g, col_m = st.columns([1, 2])
                    ci = detail.get("conciliacion_integridad", {})
                    with col_g:
                        st.plotly_chart(
                            conciliacion_gauge(ci.get("estado", ""), ci.get("diferencia", 0)),
                            use_container_width=True,
                        )
                    with col_m:
                        st.json(detail)

    # ---------------------------------------------------------------
    # TAB 2: Oráculo de validación
    # ---------------------------------------------------------------
    with tab_oracle:
        st.markdown("#### Oráculo de Validación Independiente")
        st.info(
            "El oráculo recalcula cada decisión de forma independiente al procesador principal "
            "y compara los resultados. Detecta discrepancias de decisión, valor financiero y fugas de PII. "
            "**Nota:** solo recomendado para `sample_1000.csv` desde la API para evitar timeouts."
        )

        # Archivos disponibles
        files_data = api_get("/api/v1/uploads") or {}
        all_files = (
            [f["filename"] for f in files_data.get("uploaded", [])] +
            [f["filename"] for f in files_data.get("dataset", [])]
        )

        if not all_files:
            st.warning("No hay archivos disponibles. Ve a Carga de Datos.")
        else:
            col_f, col_r = st.columns(2)
            with col_f:
                oracle_file = st.selectbox(
                    "Archivo CSV a auditar",
                    all_files,
                    key="oracle_file",
                    help="Selecciona el mismo archivo usado en el procesamiento",
                )
            with col_r:
                # Corridas disponibles
                metrics_data = api_get("/api/v1/metrics") or {}
                runs = metrics_data.get("runs", [])
                run_opts = [r["id_corrida"] for r in runs] if runs else ["(ninguna)"]
                oracle_run = st.selectbox("Corrida a auditar", run_opts, key="oracle_run")

            st.warning(
                "⚠️ Para datasets de 1.2M registros, usa el script directo: "
                "`python -m src.oracle_validator`"
            )

            if st.button("🔬 Ejecutar Oráculo", type="primary"):
                with st.spinner("Ejecutando validación independiente… (puede tardar varios segundos)"):
                    result = api_get(
                        f"/api/v1/audit/validate/{oracle_run}",
                        params={"input_filename": oracle_file},
                        timeout=120,
                    )

                if result:
                    estado = result.get("estado_auditoria", "")
                    ok = estado == "APROBADO_100_EXACTITUD"

                    if ok:
                        st.success(f"✅ **{estado}** — Sistema verificado con exactitud al 100%")
                    else:
                        st.error(f"❌ **{estado}** — Se detectaron discrepancias")

                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Registros auditados", f"{result.get('total_registros_evaluados', 0):,}")
                    col2.metric("Exactitud Decisión", f"{result.get('porcentaje_exactitud_decision', 0):.2f}%")
                    col3.metric("Exactitud Financiera", f"{result.get('porcentaje_exactitud_financiera', 0):.2f}%")
                    col4.metric("Fugas PII", f"{result.get('fugas_privacidad_pii', 0)}")

                    with st.expander("Ver resultado completo"):
                        st.json(result)
                else:
                    st.error("No se pudo ejecutar el oráculo. Verifica la conexión con la API.")

    # ---------------------------------------------------------------
    # TAB 3: Parser de glosa
    # ---------------------------------------------------------------
    with tab_parser:
        st.markdown("#### Parser y Validador de Glosa")
        st.caption(
            "Verifica si una glosa cumple el formato de 7 campos requeridos. "
            "Los datos PII se muestran solo como hashes SHA-256."
        )

        example_glosa = (
            "Paciente: Carlos Slim; DNO: DNO-99999999; SeguroSocial: SS-111-22-3333; "
            "Edad: 45; PerfilCobertura: PRIORITARIO; "
            "ServicioSolicitado: Consulta de medicina general; "
            "Medicacion: acetaminofén|ibuprofeno"
        )

        glosa_input = st.text_area(
            "Ingresa la glosa a parsear",
            value=example_glosa,
            height=120,
            key="parser_glosa_input",
        )

        if st.button("🧬 Parsear glosa", type="primary"):
            result = api_post("/api/v1/audit/parse", {"glosa": glosa_input})
            if result:
                if result.get("es_valido"):
                    st.success("✅ Glosa válida — todos los campos extraídos correctamente")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown("**Datos extraídos:**")
                        st.metric("Perfil de Cobertura", result.get("perfil_cobertura", ""))
                        st.metric("Servicio Solicitado", result.get("servicio_solicitado", ""))
                        st.metric("Edad", result.get("edad", ""))
                        meds = result.get("medicaciones", [])
                        st.metric("Medicaciones", f"{len(meds)} encontradas")
                        if meds:
                            st.caption(f"Lista: {', '.join(meds)}")
                    with col_b:
                        st.markdown("**Hashes SHA-256 (PII protegida):**")
                        st.code(f"DNO Hash: {result.get('dno_hash', '')[:16]}…")
                        st.code(f"SS Hash: {result.get('seguro_social_hash', '')[:16]}…")
                        st.code(f"Paciente Hash: {result.get('paciente_hash', '')[:16]}…")
                        st.caption("Los hashes tienen 64 caracteres — aquí se muestran truncados por seguridad")
                else:
                    st.error(f"❌ Glosa inválida: {result.get('error', 'Error desconocido')}")
                    st.markdown("""
                    **Formato esperado:**
                    ```
                    Paciente: Nombre Apellido; DNO: DNO-12345678; SeguroSocial: SS-111-22-3333; 
                    Edad: 45; PerfilCobertura: PRIORITARIO; 
                    ServicioSolicitado: Consulta de medicina general; Medicacion: acetaminofén
                    ```
                    """)
