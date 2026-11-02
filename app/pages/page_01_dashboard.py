"""
pages/page_01_dashboard.py
Dashboard ejecutivo con KPIs, distribución de cobertura y métricas de la última corrida.
Todos los datos se obtienen del endpoint /api/v1/results/summary y /api/v1/metrics.
"""

from __future__ import annotations
import streamlit as st
from app.components.auth import api_get
from app.components.charts import (
    decision_donut, perfiles_bar, top_servicios_bar,
    valor_cobertura_bar, runs_timeline, alertas_bar, conciliacion_gauge,
)


def render():
    st.title("📊 Dashboard Ejecutivo")
    st.caption("Sistema de Salud de Chernovia — Vista consolidada de cobertura médica")

    # --- Cargar datos ---
    with st.spinner("Cargando estadísticas…"):
        stats = api_get("/api/v1/results/summary") or {}
        metrics_data = api_get("/api/v1/metrics") or {}

    runs = metrics_data.get("runs", [])
    latest = runs[0] if runs else {}
    ci = latest.get("conciliacion_integridad", {})

    if not stats and not latest:
        st.warning("⚠️ No hay datos procesados todavía. Ve a **Procesamiento COIL** para ejecutar una corrida.")
        _show_empty_state()
        return

    # ---------------------------------------------------------------
    # Fila 1: KPIs principales
    # ---------------------------------------------------------------
    st.subheader("Indicadores Clave")
    c1, c2, c3, c4, c5 = st.columns(5)

    def _metric(col, label, value, help_text="", delta=None):
        with col:
            kw = {"delta": delta} if delta is not None else {}
            st.metric(label=label, value=value, help=help_text, **kw)

    total_ord = stats.get("total_ordenes", 0)
    total_cub = stats.get("total_cubiertas", 0)
    total_no  = stats.get("total_no_cubiertas", 0)
    pct_cub   = stats.get("porcentaje_cubiertas", 0.0)
    val_sol   = stats.get("valor_solicitado_total_cop", 0)
    val_rec   = stats.get("valor_reconocido_total_cop", 0)
    cuarentena_total = latest.get("total_cuarentena", 0)

    _metric(c1, "Total Órdenes", f"{total_ord:,}", "Registros en la capa gold")
    _metric(c2, "Cubiertas", f"{total_cub:,}", "Órdenes con decisión CUBRE")
    _metric(c3, "No Cubiertas", f"{total_no:,}", "Órdenes con decisión NO CUBRE")
    _metric(c4, "% Cobertura", f"{pct_cub:.1f}%", "Porcentaje de órdenes cubiertas")
    _metric(c5, "Cuarentena", f"{cuarentena_total:,}", "Registros rechazados por validación")

    st.divider()

    # ---------------------------------------------------------------
    # Fila 2: Gráficos de distribución
    # ---------------------------------------------------------------
    col_a, col_b, col_c = st.columns([1.2, 1.2, 1.6])

    with col_a:
        dist_dec = stats.get("distribucion_decisiones", {"CUBRE": total_cub, "NO CUBRE": total_no})
        st.plotly_chart(decision_donut(dist_dec), use_container_width=True)

    with col_b:
        dist_perf = stats.get("distribucion_perfiles", {})
        if dist_perf:
            st.plotly_chart(perfiles_bar(dist_perf), use_container_width=True)
        else:
            st.info("Sin datos de perfiles")

    with col_c:
        top_srv = stats.get("top_servicios", [])
        st.plotly_chart(top_servicios_bar(top_srv[:10], "Top 10 Servicios"), use_container_width=True)

    # ---------------------------------------------------------------
    # Fila 3: Valores financieros y alertas
    # ---------------------------------------------------------------
    col_d, col_e = st.columns([1.5, 1.5])

    with col_d:
        if val_sol or val_rec:
            st.plotly_chart(valor_cobertura_bar(stats), use_container_width=True)
        else:
            st.info("Sin datos financieros")

    with col_e:
        top_alertas = stats.get("top_alertas", [])
        if top_alertas:
            st.plotly_chart(alertas_bar(top_alertas, "Alertas del Sistema"), use_container_width=True)
        else:
            st.info("Sin alertas registradas")

    st.divider()

    # ---------------------------------------------------------------
    # Fila 4: Métricas de corridas y conciliación
    # ---------------------------------------------------------------
    col_f, col_g = st.columns([2, 1])

    with col_f:
        if runs:
            st.plotly_chart(runs_timeline(runs[-10:], "Rendimiento Reciente (últimas 10 corridas)"),
                           use_container_width=True)

    with col_g:
        st.markdown("**Última Corrida**")
        if latest:
            st.plotly_chart(
                conciliacion_gauge(ci.get("estado", ""), ci.get("diferencia", 0)),
                use_container_width=True,
            )
            cols = st.columns(2)
            cols[0].metric("Duración", f"{latest.get('duracion_segundos', 0):.1f} s")
            cols[1].metric("Rendimiento", f"{latest.get('rendimiento_ordenes_por_segundo', 0):,.0f} órd/s")
            cols[0].metric("SLA 24h", "✅ Sí" if latest.get("cumple_sla_24h") else "❌ No")
            cols[1].metric("Costo AWS est.", f"${latest.get('estimacion_costo_aws_usd', 0):.6f}")
        else:
            st.info("Sin corridas registradas")

    # ---------------------------------------------------------------
    # Resumen de corridas recientes
    # ---------------------------------------------------------------
    if runs:
        st.subheader("Corridas Recientes")
        import pandas as pd
        df_runs = pd.DataFrame(runs[:5])[[
            "id_corrida", "timestamp_fin", "total_recibidas",
            "total_cubiertas", "total_cuarentena", "duracion_segundos",
            "rendimiento_ordenes_por_segundo", "porcentaje_cubiertas",
        ]].rename(columns={
            "id_corrida": "ID Corrida",
            "timestamp_fin": "Fin",
            "total_recibidas": "Recibidas",
            "total_cubiertas": "Cubiertas",
            "total_cuarentena": "Cuarentena",
            "duracion_segundos": "Duración (s)",
            "rendimiento_ordenes_por_segundo": "Órd/s",
            "porcentaje_cubiertas": "% Cobertura",
        })
        st.dataframe(df_runs, use_container_width=True, hide_index=True)


def _show_empty_state():
    """Estado vacío cuando no hay datos."""
    st.markdown(
        """
        <div style='text-align:center; padding: 3rem; color: #777'>
            <h1 style='font-size:4rem'>📭</h1>
            <h3>Sin datos procesados</h3>
            <p>Sigue estos pasos para comenzar:</p>
            <ol style='text-align:left; max-width:400px; margin:auto'>
                <li>Ve a <b>Carga de Datos</b> y sube un CSV de órdenes</li>
                <li>Ve a <b>Procesamiento COIL</b> y ejecuta una corrida</li>
                <li>Regresa aquí para ver las métricas</li>
            </ol>
        </div>
        """,
        unsafe_allow_html=True,
    )
