"""
api/main.py
Aplicación FastAPI principal para el Sistema COIL de Órdenes Médicas.

Arrancar con:
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

Documentación interactiva disponible en:
    http://localhost:8000/docs   (Swagger UI)
    http://localhost:8000/redoc  (ReDoc)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Asegurar que el directorio raíz del proyecto esté en sys.path
# (necesario cuando se lanza desde Docker o desde un directorio distinto)
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.middleware.auth import get_current_user
from api.routers import audit, auth, coverage, process, quarantine, reports, results
from api.routers import aws as aws_router
from api.services.config import get_settings, update_settings
from pydantic import BaseModel
from typing import Optional

# ---------------------------------------------------------------------------
# Lifespan — configuración de inicio/cierre
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    # Crear directorio de uploads si no existe
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    print(f"✅ COIL API iniciada en modo: {settings.app_mode.upper()}")
    print(f"   Catálogo servicios: {settings.catalogo_servicios_path}")
    print(f"   Output dir: {settings.output_dir}")
    yield
    print("COIL API detenida.")


# ---------------------------------------------------------------------------
# Instancia de la aplicación
# ---------------------------------------------------------------------------

app = FastAPI(
    title="COIL — Sistema de Gestión de Órdenes Médicas",
    description="""
## API REST para el procesamiento, auditoría y gestión de órdenes médicas

**Sistema de Salud de Chernovia — Proyecto COIL Big Data**

### Características
- Procesamiento por lotes de hasta 1.2M órdenes médicas
- Motor de reglas de cobertura (20 servicios, 3 perfiles)
- Auditoría independiente con oráculo de verificación
- Exportación CSV / Excel
- Modo LOCAL (archivos) y modo AWS (S3 + Glue + Athena)

### Autenticación
Todos los endpoints (excepto `/api/v1/auth/token`) requieren un JWT.
Obtén el token en: **POST /api/v1/auth/token**
    """,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — permite conexiones desde Streamlit y navegadores locales
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",   # Streamlit local
        "http://127.0.0.1:8501",
        "http://localhost:3000",   # Dev tools
        "*",                       # En producción restringir a dominios específicos
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Manejadores de errores globales
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"Error interno del servidor: {str(exc)}"},
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth.router)
app.include_router(process.router)
app.include_router(results.router)
app.include_router(quarantine.router)
app.include_router(coverage.router)
app.include_router(audit.router)
app.include_router(reports.router)
app.include_router(aws_router.router)


# ---------------------------------------------------------------------------
# Endpoints de sistema (sin autenticación)
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def root():
    return {
        "app": "COIL API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Sistema"])
async def health():
    """Endpoint de salud para Docker healthcheck y load balancer."""
    settings = get_settings()
    return {
        "status": "healthy",
        "mode": settings.app_mode,
        "version_catalogo": settings.version_catalogo,
    }


@app.get("/api/v1/config", tags=["Sistema"])
async def get_config(
    _user: str = Depends(get_current_user),
):
    """Retorna la configuración activa (sin credenciales sensibles)."""
    settings = get_settings()
    return {
        "app_mode": settings.app_mode,
        "version_catalogo": settings.version_catalogo,
        "output_dir": settings.output_dir,
        "upload_dir": settings.upload_dir,
        "aws_region": settings.aws_default_region if settings.is_aws else None,
        "s3_bucket": settings.s3_bucket_name if settings.is_aws else None,
        "glue_job": settings.glue_job_name if settings.is_aws else None,
        "athena_database": settings.athena_database if settings.is_aws else None,
    }


class ModeUpdateRequest(BaseModel):
    app_mode: str
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None
    aws_default_region: Optional[str] = None
    s3_bucket_name: Optional[str] = None
    glue_job_name: Optional[str] = None
    athena_database: Optional[str] = None


@app.post("/api/v1/config/mode", tags=["Sistema"])
async def switch_mode(
    request: ModeUpdateRequest,
    _user: str = Depends(get_current_user),
):
    """Permite cambiar dinámicamente entre modo 'local' y 'aws' y configurar credenciales."""
    mode = request.app_mode.lower()
    if mode not in ("local", "aws"):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Modo no válido. Debe ser 'local' o 'aws'."},
        )

    updates = {"app_mode": mode}
    if request.aws_access_key_id is not None:
        updates["aws_access_key_id"] = request.aws_access_key_id
    if request.aws_secret_access_key is not None:
        updates["aws_secret_access_key"] = request.aws_secret_access_key
    if request.aws_session_token is not None:
        updates["aws_session_token"] = request.aws_session_token
    if request.aws_default_region is not None:
        updates["aws_default_region"] = request.aws_default_region
    if request.s3_bucket_name is not None:
        updates["s3_bucket_name"] = request.s3_bucket_name
    if request.glue_job_name is not None:
        updates["glue_job_name"] = request.glue_job_name
    if request.athena_database is not None:
        updates["athena_database"] = request.athena_database

    settings = update_settings(**updates)
    return {
        "status": "success",
        "message": f"Modo actualizado a {mode.upper()}",
        "app_mode": settings.app_mode,
        "s3_bucket": settings.s3_bucket_name,
        "aws_region": settings.aws_default_region,
    }
