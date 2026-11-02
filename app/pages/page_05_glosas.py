"""
pages/page_05_glosas.py
Viewer paginado de órdenes procesadas (capa gold).

NUNCA carga el dataset completo — usa la API paginada.
Permite filtrar por decisión, perfil, fecha, entidad, servicio y alertas.
"""

from __future__ import annotations
from typing import Dict, List, Tuple

import streamlit as st
from app.components.auth import api_get
from app.components.paginator import show_paginated_table, reset_pagination


def _fetch_orders(page: int, page_size: int, filters: Dict) -> Tuple[List[Dict], int]:
    """Adaptador entre el paginador y la API."""
    params = {"page": page, "page_size": page_size}
    params.update({k: v for k, v in filters.items() if v})
    data = api_get("/api/v1/results", params=params) or {}
    return data.get("data", []), data.get("total", 0)


def render():
    st.title("📋 Glosas — Órdenes Procesadas")
    st.caption(
        "Visualización paginada de la capa gold. "
        "Máximo 2,000 filas por página para proteger el rendimiento con 1.2M registros."
    )

    # ---------------------------------------------------------------
    # Panel de filtros
    # ---------------------------------------------------------------
    with st.expander("🔍 Filtros de búsqueda", expanded=True):
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            decision = st.selectbox(
                "Decisión",
                ["", "CUBRE", "NO CUBRE"],
                format_func=lambda x: "Todas" if not x else x,
                key="gls_decision",
            )

        with col2:
            perfil = st.selectbox(
                "Perfil de cobertura",
                ["", "PRIORITARIO", "ESTANDAR", "COPAGO"],
                format_func=lambda x: "Todos" if not x else x,
                key="gls_perfil",
            )

        with col3:
            fecha_desde = st.date_input("Fecha desde", value=None, key="gls_fdesde")
            fecha_hasta = st.date_input("Fecha hasta", value=None, key="gls_fhasta")

        with col4:
            codigo_srv = st.text_input("Código servicio", placeholder="COV-001", key="gls_cod")
            alertas = st.selectbox(
                "Alerta",
                ["", "NINGUNA", "VALOR_SOBRE_RANGO", "VALOR_BAJO_RANGO",
                 "SERVICIO_FUERA_DE_CATALOGO", "MEDICACION_NO_CONCUERDA"],
                format_func=lambda x: "Todas" if not x else x,
                key="gls_alerta",
            )

        col5, col6 = st.columns(2)
        with col5:
            entidad = st.text_input("Entidad emisora", placeholder="Hospital…", key="gls_entidad")
        with col6:
            run_id_filter = st.text_input("ID de corrida", placeholder="RUN-…", key="gls_runid")

        col_apply, col_clear = st.columns([1, 4])
        with col_apply:
            if st.button("🔍 Aplicar filtros", type="primary", use_container_width=True):
                reset_pagination("glosas")
                st.rerun()
        with col_clear:
            if st.button("🗑️ Limpiar filtros"):
                for key in ["gls_decision", "gls_perfil", "gls_fdesde", "gls_fhasta",
                            "gls_cod", "gls_alerta", "gls_entidad", "gls_runid"]:
                    if key in st.session_state:
                        del st.session_state[key]
                reset_pagination("glosas")
                st.rerun()

    # Construir filtros activos
    filters = {}
    if decision:
        filters["decision"] = decision
    if perfil:
        filters["perfil_cobertura"] = perfil
    if fecha_desde:
        filters["fecha_desde"] = str(fecha_desde)
    if fecha_hasta:
        filters["fecha_hasta"] = str(fecha_hasta)
    if codigo_srv:
        filters["codigo_servicio"] = codigo_srv
    if alertas:
        filters["alertas"] = alertas
    if entidad:
        filters["entidad_emisora"] = entidad
    if run_id_filter:
        filters["run_id"] = run_id_filter

    # Mostrar filtros activos
    if filters:
        active_tags = " · ".join(f"`{k}={v}`" for k, v in filters.items())
        st.caption(f"Filtros activos: {active_tags}")

    st.divider()

    # ---------------------------------------------------------------
    # Tabla paginada
    # ---------------------------------------------------------------
    show_paginated_table(
        fetch_fn=_fetch_orders,
        filters=filters,
        session_key="glosas",
        page_sizes=[25, 50, 100, 200, 500],
        columns_order=[
            "id_solicitud", "fecha_solicitud", "perfil_cobertura",
            "servicio_solicitado", "decision", "porcentaje_cobertura",
            "valor_procedimiento", "valor_reconocido", "alertas",
            "entidad_emisora", "medio_emisor", "codigo_servicio",
            "categoria_servicio", "regla_aplicada", "id_corrida",
        ],
        columns_rename={
            "id_solicitud": "ID Solicitud",
            "fecha_solicitud": "Fecha",
            "perfil_cobertura": "Perfil",
            "servicio_solicitado": "Servicio",
            "decision": "Decisión",
            "porcentaje_cobertura": "% Cob.",
            "valor_procedimiento": "V. Solicitado",
            "valor_reconocido": "V. Reconocido",
            "alertas": "Alertas",
            "entidad_emisora": "Entidad",
            "medio_emisor": "Canal",
            "codigo_servicio": "Código",
            "categoria_servicio": "Categoría",
            "regla_aplicada": "Regla",
            "id_corrida": "Corrida",
        },
        highlight_col="decision",
        highlight_map={"CUBRE": "#27AE60", "NO CUBRE": "#E74C3C"},
        show_download=True,
        title="Órdenes Procesadas — Capa Gold",
    )
