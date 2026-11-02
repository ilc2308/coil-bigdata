"""
app/main.py
Punto de entrada de la aplicación Streamlit COIL.

Arrancar con:
    streamlit run app/main.py

Gestiona:
- Autenticación y sesión
- Navegación multipágina
- Importación de módulos de página
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Asegurar que el directorio raíz del proyecto esté en sys.path
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import streamlit as st

# ---------------------------------------------------------------------------
# Configuración global de la página (debe ser la PRIMERA llamada Streamlit)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="COIL — Sistema de Órdenes Médicas",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "COIL Big Data v2.0 · UPB & Universidad Panamericana",
    },
)

# CSS global
st.markdown(
    """
    <style>
    /* Ocultar elementos de Streamlit que no queremos mostrar */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Mejoras visuales generales */
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
    .stMetric { background: #F8F9FA; border-radius: 8px; padding: 0.5rem; }
    .stTabs [data-baseweb="tab"] { font-size: 0.9rem; }
    div[data-testid="stSidebarNav"] { display: none; }

    /* Cards de KPI */
    div.metric-card {
        background: white;
        border: 1px solid #E0E0E0;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------

from app.components.auth import require_auth, sidebar_nav

require_auth()

# ---------------------------------------------------------------------------
# Navegación multipágina
# ---------------------------------------------------------------------------

PAGES = {
    "📊 Dashboard":          "app.pages.page_01_dashboard",
    "📂 Carga de Datos":     "app.pages.page_02_carga_datos",
    "⚙️ Procesamiento COIL": "app.pages.page_03_procesamiento",
    "🛡️ Cobertura":          "app.pages.page_04_cobertura",
    "📋 Glosas":             "app.pages.page_05_glosas",
    "☁️ Consola AWS":        "app.pages.page_05b_aws_console",
    "🚧 Cuarentena":         "app.pages.page_06_cuarentena",
    "🔍 Auditoría":          "app.pages.page_07_auditoria",
    "📥 Reportes":           "app.pages.page_08_reportes",
    "⚙️ Configuración":      "app.pages.page_09_configuracion",
}

# Barra lateral
sidebar_nav()

with st.sidebar:
    st.markdown("### Navegación")
    selection = st.radio(
        label="",
        options=list(PAGES.keys()),
        key="nav_selection",
        label_visibility="collapsed",
    )

# ---------------------------------------------------------------------------
# Cargar y ejecutar la página seleccionada
# ---------------------------------------------------------------------------

import importlib

module_name = PAGES[selection]
try:
    mod = importlib.import_module(module_name)
    if hasattr(mod, "render"):
        mod.render()
    else:
        st.error(f"El módulo '{module_name}' no tiene función render().")
except ModuleNotFoundError as e:
    st.error(f"Módulo no encontrado: {e}")
    st.info(f"Asegúrate de que el archivo existe en app/pages/")
except Exception as e:
    st.error(f"Error al cargar la página: {e}")
    import traceback
    st.code(traceback.format_exc())
