"""
pages/page_02_carga_datos.py
Módulo de carga y validación de archivos CSV.

Permite:
- Subir un nuevo CSV al servidor
- Ver archivos ya disponibles (dataset/ y uploads/)
- Previsualizar las primeras filas sin cargar el archivo completo
"""

from __future__ import annotations
import io
import pandas as pd
import streamlit as st
from app.components.auth import api_get, api_upload_file


def render():
    st.title("📂 Carga de Datos")
    st.caption("Sube o selecciona un archivo CSV de órdenes médicas para procesarlo.")

    tab_upload, tab_available = st.tabs(["⬆️ Subir nuevo archivo", "📁 Archivos disponibles"])

    # ----------------------------------------------------------------
    # TAB 1: Subir archivo
    # ----------------------------------------------------------------
    with tab_upload:
        st.markdown("#### Cargar archivo CSV de órdenes médicas")
        st.info(
            "📌 **Formato esperado:** CSV UTF-8 con columnas: "
            "`id_solicitud`, `fecha_solicitud`, `glosa`, `medio_emisor`, "
            "`valor_procedimiento`, `entidad_emisora`"
        )

        uploaded = st.file_uploader(
            "Arrastra o selecciona el archivo CSV",
            type=["csv"],
            accept_multiple_files=False,
            help="Tamaño máximo: 500 MB. El dataset de 1.2M ocupa ~344 MB.",
        )

        if uploaded:
            size_mb = uploaded.size / 1_048_576
            st.markdown(f"**Archivo seleccionado:** `{uploaded.name}` · {size_mb:.1f} MB")

            # Previsualización (solo primeras 5 filas, no carga todo en memoria)
            with st.expander("👁️ Previsualizar primeras filas", expanded=True):
                try:
                    # Leer solo el principio del buffer
                    preview_bytes = uploaded.read(65536)  # 64 KB
                    uploaded.seek(0)
                    preview_df = pd.read_csv(io.BytesIO(preview_bytes), nrows=5, encoding="utf-8")
                    st.dataframe(preview_df, use_container_width=True)
                    st.caption(f"Columnas detectadas: {list(preview_df.columns)}")

                    # Validar columnas requeridas
                    required_cols = {"id_solicitud", "fecha_solicitud", "glosa",
                                     "medio_emisor", "valor_procedimiento", "entidad_emisora"}
                    found_cols = set(preview_df.columns)
                    missing = required_cols - found_cols
                    if missing:
                        st.error(f"❌ Columnas faltantes: {missing}")
                    else:
                        st.success("✅ Esquema correcto — todas las columnas requeridas presentes")
                except Exception as e:
                    st.error(f"Error al previsualizar: {e}")

            col_btn, col_info = st.columns([1, 3])
            with col_btn:
                if st.button("⬆️ Subir al servidor", type="primary", use_container_width=True):
                    with st.spinner(f"Subiendo {uploaded.name} ({size_mb:.1f} MB)…"):
                        uploaded.seek(0)
                        content = uploaded.read()
                        result = api_upload_file(uploaded.name, content)
                        if result:
                            st.success(f"✅ {result.get('message', 'Archivo subido exitosamente')}")
                            st.balloons()
                        else:
                            st.error("❌ Error al subir el archivo. Verifica la conexión con la API.")

            with col_info:
                st.markdown(
                    f"ℹ️ El archivo se guardará en `uploads/` del servidor. "
                    f"Luego podrás procesarlo desde **Procesamiento COIL**."
                )

    # ----------------------------------------------------------------
    # TAB 2: Archivos disponibles
    # ----------------------------------------------------------------
    with tab_available:
        st.markdown("#### Archivos disponibles para procesar")

        if st.button("🔄 Actualizar lista"):
            st.rerun()

        files_data = api_get("/api/v1/uploads")

        if not files_data:
            st.warning("No se pudo obtener la lista de archivos. ¿Está la API activa?")
            return

        # Archivos en uploads/
        uploaded_files = files_data.get("uploaded", [])
        dataset_files  = files_data.get("dataset", [])

        col_up, col_ds = st.columns(2)

        with col_up:
            st.markdown("**📤 Subidos recientemente** (`uploads/`)")
            if uploaded_files:
                for f in uploaded_files:
                    with st.container():
                        c1, c2 = st.columns([3, 1])
                        c1.markdown(f"📄 `{f['filename']}` — {f['size_mb']:.1f} MB")
                        if c2.button("Usar", key=f"use_upload_{f['filename']}", use_container_width=True):
                            st.session_state["selected_file"] = f["filename"]
                            st.success(f"Archivo `{f['filename']}` seleccionado. Ve a **Procesamiento COIL**.")
            else:
                st.info("Sin archivos subidos todavía.")

        with col_ds:
            st.markdown("**🗂️ Dataset del proyecto** (`dataset/`)")
            if dataset_files:
                for f in dataset_files:
                    with st.container():
                        c1, c2 = st.columns([3, 1])
                        c1.markdown(f"📄 `{f['filename']}` — {f['size_mb']:.1f} MB")
                        if c2.button("Usar", key=f"use_ds_{f['filename']}", use_container_width=True):
                            st.session_state["selected_file"] = f["filename"]
                            st.success(f"Archivo `{f['filename']}` seleccionado. Ve a **Procesamiento COIL**.")
            else:
                st.info("Sin archivos en dataset/.")

        # Mostrar selección actual
        if st.session_state.get("selected_file"):
            st.info(f"📌 Archivo seleccionado actualmente: **{st.session_state['selected_file']}**")
