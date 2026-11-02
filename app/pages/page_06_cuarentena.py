"""
pages/page_06_cuarentena.py
Módulo de visualización y análisis de registros en cuarentena.

Muestra órdenes que fallaron validación de esquema o valor,
con sus motivos de rechazo para análisis y corrección.
"""

from __future__ import annotations
from typing import Dict, List, Tuple

import pandas as pd
import plotly.express as px
import streamlit as st
from app.components.auth import api_get
from app.components.paginator import show_paginated_table, reset_pagination


def _fetch_quarantine(page: int, page_size: int, filters: Dict) -> Tuple[List[Dict], int]:
    params = {"page": page, "page_size": page_size}
    if filters.get("run_id"):
        params["run_id"] = filters["run_id"]
    data = api_get("/api/v1/quarantine", params=params) or {}
    return data.get("data", []), data.get("total", 0)


def render():
    st.title("🚧 Cuarentena")
    st.caption(
        "Registros rechazados por validación de esquema, valor inválido o glosa malformada. "
        "La ecuación de integridad garantiza: Recibidas = Procesadas + Cuarentena."
    )

    # ---------------------------------------------------------------
    # Resumen de cuarentena
    # ---------------------------------------------------------------
    summary = api_get("/api/v1/quarantine/summary") or {}

    total_q = summary.get("total", 0)
    por_motivo = summary.get("por_motivo", [])
    por_run = summary.get("por_run", {})

    col1, col2, col3 = st.columns(3)
    col1.metric("Total en Cuarentena", f"{total_q:,}")
    col2.metric("Runs con Cuarentena", f"{len(por_run)}")
    col3.metric("Motivos Únicos", f"{len(por_motivo)}")

    if total_q == 0:
        st.success("✅ No hay registros en cuarentena. Todos los datos pasaron la validación.")
        return

    st.divider()

    # ---------------------------------------------------------------
    # Gráfico de motivos
    # ---------------------------------------------------------------
    if por_motivo:
        df_motivos = pd.DataFrame(por_motivo)
        fig = px.bar(
            df_motivos.sort_values("total", ascending=True),
            x="total",
            y="motivo",
            orientation="h",
            title="Registros por Motivo de Rechazo",
            color="total",
            color_continuous_scale="Reds",
            labels={"total": "Registros", "motivo": "Motivo"},
        )
        fig.update_layout(
            height=max(250, len(df_motivos) * 35 + 80),
            showlegend=False,
            coloraxis_showscale=False,
            margin=dict(l=10, r=10, t=40, b=10),
            paper_bgcolor="white",
        )
        st.plotly_chart(fig, use_container_width=True)

    # ---------------------------------------------------------------
    # Filtros
    # ---------------------------------------------------------------
    with st.expander("🔍 Filtrar por corrida", expanded=False):
        run_ids = list(por_run.keys())
        run_filter = st.selectbox(
            "Corrida",
            [""] + run_ids,
            format_func=lambda x: "Todas las corridas" if not x else x,
            key="q_run_filter",
        )
        if st.button("Aplicar", key="q_apply"):
            reset_pagination("quarantine")
            st.rerun()

    filters = {}
    if run_filter:
        filters["run_id"] = run_filter

    st.divider()

    # ---------------------------------------------------------------
    # Tabla paginada
    # ---------------------------------------------------------------
    show_paginated_table(
        fetch_fn=_fetch_quarantine,
        filters=filters,
        session_key="quarantine",
        page_sizes=[25, 50, 100],
        columns_order=[
            "id_solicitud", "fecha_solicitud", "motivo_rechazo",
            "valor_procedimiento", "entidad_emisora", "medio_emisor",
            "id_corrida", "timestamp_rechazo",
        ],
        columns_rename={
            "id_solicitud": "ID Solicitud",
            "fecha_solicitud": "Fecha",
            "motivo_rechazo": "Motivo de Rechazo",
            "valor_procedimiento": "Valor",
            "entidad_emisora": "Entidad",
            "medio_emisor": "Canal",
            "id_corrida": "Corrida",
            "timestamp_rechazo": "Timestamp",
        },
        show_download=True,
        title="Registros en Cuarentena",
    )

    # ---------------------------------------------------------------
    # Ayuda para resolver la cuarentena
    # ---------------------------------------------------------------
    with st.expander("💡 ¿Cómo resolver registros en cuarentena?"):
        st.markdown("""
        Los registros en cuarentena no se procesan ni se incluyen en la capa gold.
        Para corregirlos:

        | Motivo | Causa probable | Solución |
        |--------|---------------|----------|
        | `Valor de procedimiento inválido` | Campo vacío, negativo o no numérico | Corregir en el CSV fuente |
        | `Glosa malformada o incompleta` | Falta algún campo obligatorio de la glosa | Revisar el formato de la glosa |
        | `Falta clave obligatoria *` | Falta Paciente, DNO o ServicioSolicitado | Completar los campos faltantes |
        | `Formato de glosa no cumple estructura` | Separadores o claves incorrectos | Verificar el formato `Clave: Valor;` |

        **Formato esperado de glosa:**
        ```
        Paciente: Nombre; DNO: DNO-12345678; SeguroSocial: SS-111-22-3333; 
        Edad: 45; PerfilCobertura: PRIORITARIO; 
        ServicioSolicitado: Consulta de medicina general; Medicacion: acetaminofén
        ```
        """)
