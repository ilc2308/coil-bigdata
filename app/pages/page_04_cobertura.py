"""
pages/page_04_cobertura.py
Gestión y exploración de reglas de cobertura.

Permite:
- Ver el catálogo completo de 20 servicios cubiertos
- Ver los 3 perfiles de cobertura (PRIORITARIO / ESTANDAR / COPAGO)
- Evaluar una orden médica de prueba en tiempo real
- Ver estadísticas de cobertura del dataset
"""

from __future__ import annotations
import pandas as pd
import streamlit as st
from app.components.auth import api_get, api_post
from app.components.charts import decision_donut, perfiles_bar, alertas_bar


def render():
    st.title("🛡️ Gestión de Cobertura")
    st.caption("Reglas de cobertura, catálogos y evaluación de órdenes.")

    tab_cat, tab_perfiles, tab_eval, tab_stats = st.tabs([
        "📋 Catálogo Servicios",
        "👤 Perfiles",
        "🧪 Evaluador",
        "📊 Estadísticas",
    ])

    # ---------------------------------------------------------------
    # TAB 1: Catálogo de servicios
    # ---------------------------------------------------------------
    with tab_cat:
        st.markdown("#### Catálogo de Servicios Cubiertos")
        st.caption("20 servicios médicos del sistema de cobertura de Chernovia — Versión 2026.1")

        data = api_get("/api/v1/coverage/servicios") or {}
        servicios = data.get("servicios", [])

        if not servicios:
            st.warning("No se pudo cargar el catálogo. ¿Está la API activa?")
            return

        df = pd.DataFrame(servicios)

        # Filtros
        col_cat, col_search = st.columns(2)
        with col_cat:
            categorias = ["Todas"] + sorted(df["categoria"].unique().tolist())
            cat_filter = st.selectbox("Filtrar por categoría", categorias)
        with col_search:
            search = st.text_input("Buscar servicio", placeholder="ej: consulta, radiografía…")

        df_filtered = df.copy()
        if cat_filter != "Todas":
            df_filtered = df_filtered[df_filtered["categoria"] == cat_filter]
        if search:
            mask = df_filtered["servicio"].str.contains(search, case=False, na=False)
            df_filtered = df_filtered[mask]

        st.dataframe(
            df_filtered[[
                "codigo_servicio", "servicio", "categoria",
                "valor_min_referencia", "valor_max_referencia",
                "medicaciones_referencia", "cubre_sistema_publico"
            ]].rename(columns={
                "codigo_servicio": "Código",
                "servicio": "Servicio",
                "categoria": "Categoría",
                "valor_min_referencia": "Valor Mín (COP)",
                "valor_max_referencia": "Valor Máx (COP)",
                "medicaciones_referencia": "Medicaciones Referencia",
                "cubre_sistema_publico": "Sistema Público",
            }),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(f"Mostrando {len(df_filtered)} de {len(df)} servicios")

        # Distribución por categoría
        if len(df) > 0:
            cat_dist = df.groupby("categoria").size().reset_index(name="total")
            import plotly.express as px
            fig = px.pie(cat_dist, names="categoria", values="total",
                        title="Distribución por Categoría",
                        color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_layout(height=280, margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig, use_container_width=True)

    # ---------------------------------------------------------------
    # TAB 2: Perfiles de cobertura
    # ---------------------------------------------------------------
    with tab_perfiles:
        st.markdown("#### Perfiles de Cobertura")

        perfiles_data = api_get("/api/v1/coverage/perfiles") or {}
        perfiles = perfiles_data.get("perfiles", [])

        if not perfiles:
            st.warning("No se pudo cargar los perfiles.")
            return

        col1, col2, col3 = st.columns(3)
        cols = [col1, col2, col3]
        colors = {"PRIORITARIO": "#8E44AD", "ESTANDAR": "#2980B9", "COPAGO": "#16A085"}

        for i, p in enumerate(perfiles):
            perfil = p.get("perfil_cobertura", "")
            pct = p.get("porcentaje_cobertura_si_el_servicio_esta_cubierto", 0)
            desc = p.get("descripcion", "")
            color = colors.get(perfil, "#555")

            with cols[i % 3]:
                st.markdown(
                    f"""
                    <div style='background:white; border:2px solid {color}; border-radius:12px;
                                padding:1.5rem; text-align:center; margin-bottom:1rem'>
                        <h2 style='color:{color}; margin:0'>{pct}%</h2>
                        <h4 style='color:#333; margin:0.5rem 0'>{perfil}</h4>
                        <p style='color:#666; font-size:0.85rem; margin:0'>{desc}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.divider()
        st.markdown("**Tabla de Reglas de Negocio**")
        df_reglas = pd.DataFrame([
            {"Perfil": "PRIORITARIO", "Cobertura": "100%", "Regla": "RN-COV-CATALOGO-V1",
             "Descripción": "Cobertura total — servicio en catálogo"},
            {"Perfil": "ESTANDAR", "Cobertura": "50%", "Regla": "RN-COV-CATALOGO-V1",
             "Descripción": "Cobertura parcial — servicio en catálogo"},
            {"Perfil": "COPAGO", "Cobertura": "25%", "Regla": "RN-COV-CATALOGO-V1",
             "Descripción": "Cobertura mínima con copago — servicio en catálogo"},
            {"Perfil": "Cualquiera", "Cobertura": "0%", "Regla": "RN-NOCOV-EXCLUSION-V1",
             "Descripción": "Servicio fuera del catálogo — NO CUBRE"},
        ])
        st.dataframe(df_reglas, use_container_width=True, hide_index=True)

    # ---------------------------------------------------------------
    # TAB 3: Evaluador de órdenes
    # ---------------------------------------------------------------
    with tab_eval:
        st.markdown("#### Evaluador de Orden Individual")
        st.caption("Prueba el motor de reglas con valores personalizados sin crear una corrida completa.")

        col_form, col_result = st.columns([1, 1])

        with col_form:
            # Cargar opciones dinámicamente
            srv_data = api_get("/api/v1/coverage/servicios") or {}
            srv_list = [s["servicio"] for s in srv_data.get("servicios", [])]
            srv_list_sorted = sorted(srv_list) if srv_list else ["Consulta de medicina general"]

            servicio = st.selectbox(
                "Servicio solicitado",
                srv_list_sorted,
                help="Selecciona del catálogo oficial",
            )
            # Opción manual
            manual = st.text_input(
                "O escribe un servicio manual",
                placeholder="ej: Cirugía estética no autorizada",
                help="Para probar servicios NO cubiertos",
            )
            servicio_final = manual.strip() if manual.strip() else servicio

            perfil = st.radio(
                "Perfil de cobertura",
                ["PRIORITARIO", "ESTANDAR", "COPAGO"],
                horizontal=True,
            )
            valor = st.number_input(
                "Valor del procedimiento (COP)",
                min_value=1000,
                max_value=10_000_000,
                value=80_000,
                step=5000,
                format="%d",
            )
            meds_input = st.text_input(
                "Medicaciones (separadas por |)",
                placeholder="acetaminofén|ibuprofeno",
            )
            meds = [m.strip() for m in meds_input.split("|") if m.strip()] if meds_input else []

            evaluar = st.button("🧪 Evaluar orden", type="primary", use_container_width=True)

        with col_result:
            if evaluar:
                payload = {
                    "servicio_solicitado": servicio_final,
                    "perfil_cobertura": perfil,
                    "valor_procedimiento": int(valor),
                    "medicaciones": meds,
                }
                result = api_post("/api/v1/coverage/evaluate", payload)

                if result:
                    decision = result.get("decision", "")
                    pct = result.get("porcentaje_cobertura", 0)
                    val_rec = result.get("valor_reconocido", 0)
                    alerta = result.get("alertas", "NINGUNA")

                    color = "#27AE60" if decision == "CUBRE" else "#E74C3C"
                    icon = "✅" if decision == "CUBRE" else "❌"

                    st.markdown(
                        f"""
                        <div style='background:white; border:3px solid {color}; border-radius:12px;
                                    padding:1.5rem; margin-top:1rem'>
                            <h2 style='color:{color}; margin:0'>{icon} {decision}</h2>
                            <hr style='border-color:{color}20'>
                            <table style='width:100%'>
                                <tr><td><b>Cobertura</b></td><td style='color:{color}'><b>{pct}%</b></td></tr>
                                <tr><td><b>Valor solicitado</b></td><td>${valor:,} COP</td></tr>
                                <tr><td><b>Valor reconocido</b></td><td>${val_rec:,} COP</td></tr>
                                <tr><td><b>Código servicio</b></td><td>{result.get('codigo_servicio')}</td></tr>
                                <tr><td><b>Categoría</b></td><td>{result.get('categoria_servicio')}</td></tr>
                                <tr><td><b>Regla aplicada</b></td><td>{result.get('regla_aplicada')}</td></tr>
                                <tr><td><b>Alertas</b></td><td>{alerta}</td></tr>
                            </table>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.error("No se pudo evaluar la orden.")
            else:
                st.markdown(
                    "<div style='padding:2rem; text-align:center; color:#999'>"
                    "<p>Configura los parámetros y haz clic en <b>Evaluar orden</b></p>"
                    "</div>",
                    unsafe_allow_html=True,
                )

    # ---------------------------------------------------------------
    # TAB 4: Estadísticas de cobertura
    # ---------------------------------------------------------------
    with tab_stats:
        st.markdown("#### Estadísticas de Cobertura del Dataset")

        stats = api_get("/api/v1/coverage/stats") or {}

        if not stats or stats.get("total_ordenes", 0) == 0:
            st.info("Sin datos procesados todavía.")
            return

        c1, c2, c3 = st.columns(3)
        c1.metric("Total órdenes", f"{stats.get('total_ordenes', 0):,}")
        c2.metric("Cubiertas", f"{stats.get('total_cubiertas', 0):,}")
        c3.metric("% Cobertura", f"{stats.get('porcentaje_cubiertas', 0):.1f}%")

        col_a, col_b = st.columns(2)
        with col_a:
            dist_dec = stats.get("distribucion_decisiones", {})
            if dist_dec:
                st.plotly_chart(decision_donut(dist_dec, "Decisiones"), use_container_width=True)
        with col_b:
            dist_perf = stats.get("distribucion_perfiles", {})
            if dist_perf:
                st.plotly_chart(perfiles_bar(dist_perf), use_container_width=True)

        top_alertas = stats.get("top_alertas", [])
        if top_alertas:
            st.plotly_chart(alertas_bar(top_alertas, "Alertas del sistema"), use_container_width=True)
