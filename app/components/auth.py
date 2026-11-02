"""
components/auth.py
Gestión de autenticación en Streamlit usando st.session_state + JWT.

El token se obtiene de la API FastAPI en /api/v1/auth/token.
Todos los módulos deben llamar a require_auth() al inicio.
"""

from __future__ import annotations

import os
import time
from typing import Optional

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Configuración del cliente API
# ---------------------------------------------------------------------------

def get_api_base() -> str:
    """URL base de la API. Lee API_BASE_URL del entorno o usa localhost."""
    return os.environ.get("API_BASE_URL", "http://localhost:8000")


def api_headers() -> dict:
    """Retorna los headers con el token JWT de la sesión actual."""
    token = st.session_state.get("access_token", "")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def api_get(path: str, params: dict = None, timeout: int = 30) -> Optional[dict]:
    """GET autenticado a la API. Retorna None si falla."""
    try:
        resp = requests.get(
            f"{get_api_base()}{path}",
            headers=api_headers(),
            params=params or {},
            timeout=timeout,
        )
        if resp.status_code == 401:
            st.session_state["authenticated"] = False
            st.session_state["access_token"] = ""
            st.rerun()
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ No se puede conectar con la API. Verifica que el servidor esté activo.")
        return None
    except requests.exceptions.Timeout:
        st.error("⏱️ La API tardó demasiado en responder.")
        return None
    except Exception as e:
        st.error(f"Error en API: {e}")
        return None


def api_post(path: str, payload: dict = None, timeout: int = 30) -> Optional[dict]:
    """POST autenticado a la API."""
    try:
        resp = requests.post(
            f"{get_api_base()}{path}",
            headers=api_headers(),
            json=payload or {},
            timeout=timeout,
        )
        if resp.status_code == 401:
            st.session_state["authenticated"] = False
            st.rerun()
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ No se puede conectar con la API.")
        return None
    except Exception as e:
        st.error(f"Error en API: {e}")
        return None


def api_download(path: str, params: dict = None, timeout: int = 60) -> Optional[bytes]:
    """GET que retorna bytes (para descargas CSV/Excel)."""
    try:
        resp = requests.get(
            f"{get_api_base()}{path}",
            headers={k: v for k, v in api_headers().items() if k != "Content-Type"},
            params=params or {},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        st.error(f"Error al descargar: {e}")
        return None


def api_upload_file(filename: str, content: bytes, timeout: int = 120) -> Optional[dict]:
    """POST multipart para subir un archivo CSV."""
    try:
        resp = requests.post(
            f"{get_api_base()}/api/v1/upload",
            headers={"Authorization": f"Bearer {st.session_state.get('access_token', '')}"},
            files={"file": (filename, content, "text/csv")},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"Error al subir archivo: {e}")
        return None


# ---------------------------------------------------------------------------
# Login / Logout
# ---------------------------------------------------------------------------

def _init_session():
    """Inicializa claves de sesión si no existen."""
    defaults = {
        "authenticated": False,
        "access_token": "",
        "username": "",
        "login_error": "",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def show_login_form():
    """Muestra el formulario de login centrado."""
    _init_session()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            """
            <div style='text-align:center; padding: 2rem 0 1rem 0'>
                <h1 style='color:#1F4E79; font-size:2.2rem'>🏥 COIL</h1>
                <p style='color:#555; font-size:1rem'>Sistema de Gestión de Órdenes Médicas<br>
                <small>Sistema de Salud de Chernovia</small></p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("login_form", clear_on_submit=False):
            st.subheader("Iniciar sesión")
            username = st.text_input("Usuario", placeholder="admin")
            password = st.text_input("Contraseña", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Ingresar", use_container_width=True, type="primary")

        if submitted:
            _do_login(username, password)

        if st.session_state.get("login_error"):
            st.error(st.session_state["login_error"])

        st.markdown(
            "<p style='text-align:center; color:#999; font-size:0.75rem; margin-top:2rem'>"
            "v2.0.0 · Universidad Pontificia Bolivariana (UPB) · COIL Big Data</p>",
            unsafe_allow_html=True,
        )


def _do_login(username: str, password: str):
    """Llama a la API y guarda el token en session_state."""
    st.session_state["login_error"] = ""
    try:
        resp = requests.post(
            f"{get_api_base()}/api/v1/auth/token",
            data={"username": username, "password": password},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            st.session_state["authenticated"] = True
            st.session_state["access_token"] = data["access_token"]
            st.session_state["username"] = username
            st.rerun()
        else:
            st.session_state["login_error"] = "Usuario o contraseña incorrectos."
    except requests.exceptions.ConnectionError:
        st.session_state["login_error"] = (
            "No se puede conectar con la API. "
            "Asegúrate de que el servidor FastAPI está activo en el puerto 8000."
        )


def logout():
    """Cierra la sesión y regresa al login."""
    for key in ["authenticated", "access_token", "username"]:
        st.session_state[key] = "" if key != "authenticated" else False
    st.rerun()


def require_auth():
    """
    Función de guardia. Llamar al inicio de cada página.
    Si el usuario no está autenticado, muestra el login y detiene la ejecución.
    """
    _init_session()
    if not st.session_state.get("authenticated"):
        show_login_form()
        st.stop()


# ---------------------------------------------------------------------------
# Barra lateral común
# ---------------------------------------------------------------------------

def sidebar_nav():
    """Renderiza la barra lateral con info del usuario y botón de logout."""
    with st.sidebar:
        st.markdown(
            f"""
            <div style='background:#1F4E79; padding:1rem; border-radius:8px; margin-bottom:1rem'>
                <h3 style='color:white; margin:0'>🏥 COIL</h3>
                <p style='color:#BDC3C7; margin:0.3rem 0 0 0; font-size:0.85rem'>
                    Sistema de Salud de Chernovia
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"👤 **{st.session_state.get('username', 'Usuario')}**",
        )

        # Modo de operación — consultar la API sin importar módulos de backend
        try:
            import requests as _req
            r = _req.get(f"{get_api_base()}/health", timeout=3)
            if r.status_code == 200:
                mode = r.json().get("mode", "local")
                mode_color = "#27AE60" if mode == "local" else "#E67E22"
                mode_label = mode.upper()
                st.markdown(
                    f"<span style='background:{mode_color}; color:white; padding:2px 8px; "
                    f"border-radius:4px; font-size:0.8rem'>⚡ Modo {mode_label}</span>",
                    unsafe_allow_html=True,
                )
        except Exception:
            pass

        st.divider()

        if st.button("🚪 Cerrar sesión", use_container_width=True):
            logout()
