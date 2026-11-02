"""
tests/conftest.py
Fixtures compartidos para todos los tests del proyecto COIL.

Provee:
- cliente HTTP asíncrono para tests de la API FastAPI (sin levantar servidor real)
- paths de archivos de dataset y catálogos
- overrides de configuración para test (modo local, dirs temporales)
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# ── Asegurar que el directorio raíz esté en sys.path ──────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── Paths del dataset ──────────────────────────────────────────────────────────
DATASET_DIR        = PROJECT_ROOT / "dataset"
SAMPLE_CSV         = DATASET_DIR / "sample_1000.csv"
CATALOGO_SERVICIOS = DATASET_DIR / "COIL_catalogo_servicios_cubiertos.csv"
CATALOGO_PERFILES  = DATASET_DIR / "COIL_catalogo_perfiles_cobertura.csv"


# ── Fixture: directorio temporal de output para tests ─────────────────────────
@pytest.fixture(scope="session")
def tmp_output_dir():
    """Directorio temporal de salida que se limpia al final de la sesión de tests."""
    with tempfile.TemporaryDirectory(prefix="coil_test_output_") as tmpdir:
        # Crear subdirectorios esperados
        Path(tmpdir, "gold_curated").mkdir(parents=True, exist_ok=True)
        Path(tmpdir, "quarantine").mkdir(parents=True, exist_ok=True)
        yield tmpdir


# ── Fixture: override de Settings para apuntar al output temporal ─────────────
@pytest.fixture(scope="session")
def test_settings(tmp_output_dir):
    """Settings de la API configuradas para el entorno de test."""
    from api.services.config import Settings
    return Settings(
        app_mode="local",
        app_username="testuser",
        app_password="testpass",
        jwt_secret_key="test_secret_key_32_chars_minimum_ok",
        local_base_dir=str(PROJECT_ROOT),
        local_catalogo_servicios="dataset/COIL_catalogo_servicios_cubiertos.csv",
        local_catalogo_perfiles="dataset/COIL_catalogo_perfiles_cobertura.csv",
        local_output_dir=str(tmp_output_dir),
        local_upload_dir=str(tmp_output_dir),
        version_catalogo="2026.1",
    )


# ── Fixture: aplicación FastAPI con settings sobreescritas ───────────────────
@pytest.fixture(scope="session")
def app(test_settings):
    """Instancia de la app FastAPI lista para tests (sin levantar servidor)."""
    from api.services.config import get_settings
    from api.main import app as fastapi_app

    # Sobreescribir la dependencia de settings
    fastapi_app.dependency_overrides[get_settings] = lambda: test_settings
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


# ── Fixture: cliente HTTP asíncrono (sin servidor real) ───────────────────────
@pytest_asyncio.fixture(scope="session")
async def client(app):
    """Cliente HTTP asíncrono que habla directamente con la app ASGI."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


# ── Fixture: token de acceso para endpoints autenticados ──────────────────────
@pytest_asyncio.fixture(scope="session")
async def auth_token(client, test_settings):
    """Obtiene un JWT válido para usar en tests autenticados."""
    response = await client.post(
        "/api/v1/auth/token",
        data={
            "username": test_settings.app_username,
            "password": test_settings.app_password,
        },
    )
    assert response.status_code == 200, f"Login falló: {response.text}"
    return response.json()["access_token"]


# ── Fixture: headers con JWT ──────────────────────────────────────────────────
@pytest_asyncio.fixture(scope="session")
async def auth_headers(auth_token):
    """Headers HTTP con Authorization: Bearer para tests autenticados."""
    return {"Authorization": f"Bearer {auth_token}"}


# ── Fixture: resultado de una corrida de prueba sobre sample_1000 ─────────────
@pytest_asyncio.fixture(scope="session")
async def sample_run_metrics(tmp_output_dir):
    """
    Ejecuta el batch_processor sobre sample_1000.csv una sola vez por sesión.
    Retorna el diccionario de métricas para que los tests de resultados lo usen.
    """
    if not SAMPLE_CSV.exists():
        pytest.skip(f"sample_1000.csv no encontrado en {SAMPLE_CSV}")

    from src.batch_processor import process_batch

    metrics = process_batch(
        input_csv_path=str(SAMPLE_CSV),
        catalogo_servicios_path=str(CATALOGO_SERVICIOS),
        catalogo_perfiles_path=str(CATALOGO_PERFILES),
        output_dir=tmp_output_dir,
        run_id="RUN-TEST-INTEGRATION",
        chunk_size=500,
        write_parquet=True,
    )
    return metrics
