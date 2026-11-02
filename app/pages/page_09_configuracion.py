"""
pages/page_09_configuracion.py
Módulo de configuración del sistema COIL.

Muestra:
- Modo de operación activo (LOCAL / AWS)
- Configuración de paths y credenciales (sin mostrar secretos)
- Estado de salud de la API
- Guía de inicio rápido
"""

from __future__ import annotations
import requests
import streamlit as st
from app.components.auth import api_get, get_api_base


def render():
    st.title("⚙️ Configuración del Sistema")
    st.caption("Estado del sistema, configuración activa y guía de uso.")

    tab_status, tab_config, tab_guide = st.tabs([
        "🟢 Estado del Sistema",
        "⚙️ Configuración Activa",
        "📖 Guía de Uso",
    ])

    # ---------------------------------------------------------------
    # TAB 1: Estado del sistema
    # ---------------------------------------------------------------
    with tab_status:
        st.markdown("#### Estado del Sistema")

        col_refresh = st.columns([1, 4])[0]
        if col_refresh.button("🔄 Verificar estado"):
            st.rerun()

        # Health de la API
        api_url = get_api_base()

        try:
            health_resp = requests.get(f"{api_url}/health", timeout=5)
            if health_resp.status_code == 200:
                health = health_resp.json()
                st.success(f"✅ **API activa** en `{api_url}`")
                col1, col2, col3 = st.columns(3)
                col1.metric("Modo", health.get("mode", "N/A").upper())
                col2.metric("Estado", health.get("status", "N/A"))
                col3.metric("Versión Catálogo", health.get("version_catalogo", "N/A"))
            else:
                st.error(f"❌ API respondió con código {health_resp.status_code}")
        except requests.exceptions.ConnectionError:
            st.error(
                f"❌ **API no disponible** en `{api_url}`\n\n"
                "Asegúrate de que el servidor FastAPI está activo:\n"
                "```\nuvicorn api.main:app --host 0.0.0.0 --port 8000\n```"
            )
        except Exception as e:
            st.warning(f"⚠️ No se pudo verificar el estado: {e}")

        st.divider()

        # Estadísticas del sistema
        st.markdown("#### Resumen del Dataset")
        stats = api_get("/api/v1/results/summary") or {}
        metrics_data = api_get("/api/v1/metrics") or {}

        col_a, col_b, col_c, col_d = st.columns(4)
        col_a.metric("Órdenes en Gold", f"{stats.get('total_ordenes', 0):,}")
        col_b.metric("Corridas Ejecutadas", f"{metrics_data.get('total', 0)}")
        col_c.metric("API Base URL", api_url)
        col_d.metric("Versión", "2.0.0")

        # Archivos disponibles
        files_data = api_get("/api/v1/uploads") or {}
        uploaded = files_data.get("uploaded", [])
        dataset = files_data.get("dataset", [])

        if uploaded or dataset:
            st.markdown("**Archivos disponibles:**")
            cols = st.columns(2)
            with cols[0]:
                st.caption("📤 Subidos (uploads/)")
                for f in uploaded:
                    st.markdown(f"- `{f['filename']}` — {f['size_mb']:.1f} MB")
                if not uploaded:
                    st.caption("_(ninguno)_")
            with cols[1]:
                st.caption("🗂️ Dataset (dataset/)")
                for f in dataset:
                    st.markdown(f"- `{f['filename']}` — {f['size_mb']:.1f} MB")
                if not dataset:
                    st.caption("_(ninguno)_")

    # ---------------------------------------------------------------
    # TAB 2: Configuración activa
    # ---------------------------------------------------------------
    with tab_config:
        st.markdown("#### Configuración Activa")
        st.info("Las credenciales y secretos no se muestran aquí por seguridad.")

        config = api_get("/api/v1/config") or {}

        if config:
            app_mode = config.get("app_mode", "local")
            mode_color = "#27AE60" if app_mode == "local" else "#E67E22"
            mode_icon = "💻" if app_mode == "local" else "☁️"

            st.markdown(
                f"<div style='background:{mode_color}15; border:2px solid {mode_color}; "
                f"border-radius:8px; padding:1rem; margin-bottom:1rem'>"
                f"<h3 style='color:{mode_color}; margin:0'>{mode_icon} Modo {app_mode.upper()}</h3>"
                f"</div>",
                unsafe_allow_html=True,
            )

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**General**")
                st.code(f"APP_MODE={config.get('app_mode', 'local')}")
                st.code(f"VERSION_CATALOGO={config.get('version_catalogo', '')}")
                st.markdown("**Rutas**")
                st.code(f"OUTPUT_DIR={config.get('output_dir', '')}")
                st.code(f"UPLOAD_DIR={config.get('upload_dir', '')}")

            with col2:
                if app_mode == "aws":
                    st.markdown("**AWS**")
                    st.code(f"AWS_REGION={config.get('aws_region', '')}")
                    st.code(f"S3_BUCKET={config.get('s3_bucket', '')}")
                    st.code(f"GLUE_JOB={config.get('glue_job', '')}")
                    st.code(f"ATHENA_DB={config.get('athena_database', '')}")
                else:
                    st.markdown("**Variables de entorno (.env)**")
                    st.markdown("""
                    Para cambiar la configuración, edita el archivo `.env`:
                    - `APP_MODE` — `local` o `aws`
                    - `APP_USERNAME` / `APP_PASSWORD` — credenciales de acceso
                    - `LOCAL_OUTPUT_DIR` — directorio de resultados
                    - `LOCAL_UPLOAD_DIR` — directorio de uploads
                    - Credenciales AWS para modo cloud
                    """)

        st.divider()
        st.markdown("#### Ejemplo de `.env`")
        st.code("""
APP_MODE=local
APP_USERNAME=admin
APP_PASSWORD=coil2026
JWT_SECRET_KEY=cambia_esta_clave_secreta
LOCAL_OUTPUT_DIR=output
LOCAL_UPLOAD_DIR=uploads
VERSION_CATALOGO=2026.1
        """, language="bash")

    # ---------------------------------------------------------------
    # TAB 3: Guía de uso
    # ---------------------------------------------------------------
    with tab_guide:
        st.markdown("#### 🚀 Guía de Inicio Rápido")

        st.markdown("""
        ### Flujo de trabajo recomendado

        ```
        1. Carga de Datos → 2. Procesamiento COIL → 3. Dashboard → 4. Reportes
        ```

        ---

        ### 1. Modo Local (sin AWS)

        **Arrancar con Docker:**
        ```bash
        # Copiar el archivo de configuración
        cp .env.example .env
        # Editar .env con tus preferencias

        # Construir y arrancar
        docker-compose up --build

        # Acceder a:
        # API:       http://localhost:8000/docs
        # Dashboard: http://localhost:8501
        ```

        **Arrancar sin Docker:**
        ```bash
        pip install -r requirements.txt
        cp .env.example .env

        # Terminal 1: API
        uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

        # Terminal 2: Streamlit
        streamlit run app/main.py
        ```

        ---

        ### 2. Procesar el dataset de muestra (1,000 órdenes)

        ```bash
        # Desde CLI directamente:
        python -m src.batch_processor
        ```

        ---

        ### 3. Procesar el dataset completo (1.2M órdenes)

        ```bash
        python -m src.batch_processor dataset/COIL_dataset_glosas_salud_1_2M.csv
        ```

        ---

        ### 4. Modo AWS

        1. Edita `.env` con `APP_MODE=aws` y las credenciales del Learner Lab
        2. Sube los archivos a S3: `./infrastructure/deploy_aws_learner_lab.ps1 -BucketName tu-bucket`
        3. Desde esta UI, ve a **Procesamiento COIL** y lanza el Glue Job

        ---

        ### 5. Ejecutar pruebas

        ```bash
        python -m pytest tests/ -v
        ```

        ---

        ### Estructura de archivos de salida

        ```
        output/
        ├── gold_curated/
        │   ├── fecha_solicitud=2026-05-04/
        │   │   └── part_RUN-XXXX.parquet
        │   └── fecha_solicitud=2026-05-05/
        │       └── part_RUN-XXXX.parquet
        ├── quarantine/
        │   └── quarantine_RUN-XXXX.csv
        └── metrics_RUN-XXXX.json
        ```
        """)

        st.divider()
        st.markdown("#### 📞 Soporte")
        st.markdown(
            "**Proyecto COIL Big Data** · Universidad Pontificia Bolivariana & Universidad Panamericana  \n"
            "Versión 2.0.0 · Arquitectura: FastAPI + Streamlit + PyArrow + AWS  \n"
            "Datos: Sistema de Salud de Chernovia (1.2M órdenes médicas)"
        )
