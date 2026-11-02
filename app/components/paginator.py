"""
components/paginator.py
Componente de tabla paginada para Streamlit.

Nunca carga el dataset completo — obtiene datos de la API página por página.
Incluye controles de navegación, filtros y opción de descarga de la página actual.
"""

from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional, Tuple
import math

import pandas as pd
import streamlit as st


def show_paginated_table(
    fetch_fn: Callable[[int, int, Dict], Tuple[List[Dict], int]],
    filters: Dict[str, Any],
    session_key: str,
    page_sizes: List[int] = None,
    columns_rename: Dict[str, str] = None,
    columns_order: List[str] = None,
    highlight_col: Optional[str] = None,
    highlight_map: Optional[Dict[str, str]] = None,
    show_download: bool = True,
    title: str = "",
) -> None:
    """
    Renderiza una tabla paginada con controles de navegación.

    Args:
        fetch_fn:       Función (page, page_size, filters) → (rows, total).
        filters:        Diccionario de filtros activos.
        session_key:    Clave única en st.session_state para el estado de paginación.
        page_sizes:     Opciones de tamaño de página.
        columns_rename: Renombrar columnas para mostrar.
        columns_order:  Orden de columnas a mostrar.
        highlight_col:  Columna para colorear filas.
        highlight_map:  {valor: color_hex} para el highlight.
        show_download:  Mostrar botón de descarga de la página actual.
        title:          Título de la tabla.
    """
    if page_sizes is None:
        page_sizes = [25, 50, 100, 200]

    # Estado de paginación en session_state
    state_key_page = f"{session_key}_page"
    state_key_size = f"{session_key}_size"

    if state_key_page not in st.session_state:
        st.session_state[state_key_page] = 1
    if state_key_size not in st.session_state:
        st.session_state[state_key_size] = page_sizes[0]

    current_page = st.session_state[state_key_page]
    page_size = st.session_state[state_key_size]

    # Obtener datos
    with st.spinner("Cargando datos…"):
        rows, total = fetch_fn(current_page, page_size, filters)

    if total == 0:
        st.info("ℹ️ No hay registros que coincidan con los filtros seleccionados.")
        return

    total_pages = math.ceil(total / page_size)

    # Encabezado con conteo
    col_title, col_size = st.columns([3, 1])
    with col_title:
        if title:
            st.markdown(f"**{title}**")
        st.caption(
            f"📊 Mostrando {len(rows):,} de {total:,} registros "
            f"· Página {current_page}/{total_pages}"
        )
    with col_size:
        new_size = st.selectbox(
            "Filas/página",
            page_sizes,
            index=page_sizes.index(page_size) if page_size in page_sizes else 0,
            key=f"{session_key}_size_select",
            label_visibility="collapsed",
        )
        if new_size != page_size:
            st.session_state[state_key_size] = new_size
            st.session_state[state_key_page] = 1
            st.rerun()

    # Construir DataFrame
    df = pd.DataFrame(rows)

    if columns_order:
        existing = [c for c in columns_order if c in df.columns]
        rest = [c for c in df.columns if c not in columns_order]
        df = df[existing + rest]

    if columns_rename:
        df = df.rename(columns=columns_rename)

    # Aplicar highlight por columna
    # Determinar el nombre de la columna en el DataFrame (puede haber sido renombrada)
    _hl_col_display = columns_rename.get(highlight_col, highlight_col) if columns_rename else highlight_col
    if highlight_col and highlight_map and _hl_col_display in df.columns:
        def _make_styler(col_name, h_map):
            def _style_row(row):
                try:
                    val = str(row[col_name])
                except (KeyError, TypeError):
                    val = ""
                color = h_map.get(val, "")
                if color:
                    return [f"background-color: {color}20; color: {color}" for _ in row]
                return ["" for _ in row]
            return _style_row

        styled = df.style.apply(_make_styler(_hl_col_display, highlight_map), axis=1)
        st.dataframe(styled, use_container_width=True, hide_index=True)
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

    # Controles de navegación
    col_prev, col_info, col_next, col_jump = st.columns([1, 2, 1, 2])

    with col_prev:
        if st.button("⬅ Anterior", key=f"{session_key}_prev", disabled=current_page <= 1):
            st.session_state[state_key_page] = current_page - 1
            st.rerun()

    with col_info:
        st.markdown(
            f"<p style='text-align:center; margin-top:0.5rem'>Página {current_page} de {total_pages}</p>",
            unsafe_allow_html=True,
        )

    with col_next:
        if st.button("Siguiente ➡", key=f"{session_key}_next", disabled=current_page >= total_pages):
            st.session_state[state_key_page] = current_page + 1
            st.rerun()

    with col_jump:
        jump_to = st.number_input(
            "Ir a página",
            min_value=1,
            max_value=total_pages,
            value=current_page,
            step=1,
            key=f"{session_key}_jump",
            label_visibility="collapsed",
        )
        if jump_to != current_page:
            st.session_state[state_key_page] = int(jump_to)
            st.rerun()

    # Descarga de la página actual
    if show_download and rows:
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Descargar esta página (CSV)",
            data=csv_bytes,
            file_name=f"{session_key}_pag{current_page}.csv",
            mime="text/csv",
            key=f"{session_key}_dl",
        )


def reset_pagination(session_key: str):
    """Resetea la paginación al cambiar filtros."""
    st.session_state[f"{session_key}_page"] = 1
