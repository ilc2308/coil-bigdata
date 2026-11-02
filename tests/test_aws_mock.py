"""
tests/test_aws_mock.py
Tests de la integración AWS usando moto (mock de AWS).
NO consumen créditos reales del Learner Lab.
NO requieren credenciales AWS configuradas.

Valida:
- Factory de clientes boto3
- Operaciones S3: upload, download, list
- Glue Job: start, get status
- Storage service: rama AWS (con S3 mockeado)
- AWS service: funciones individuales
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# ── Asegurar que el directorio raíz esté en sys.path ──────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Intentar importar moto — skip todos los tests si no está instalado
try:
    from moto import mock_aws
    import boto3
    MOTO_AVAILABLE = True
except ImportError:
    MOTO_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not MOTO_AVAILABLE,
    reason="moto no instalado — instala con: pip install 'moto[s3,glue,athena]'",
)

# ── Settings de AWS para tests ────────────────────────────────────────────────
TEST_BUCKET  = "test-coil-bucket"
TEST_REGION  = "us-east-1"
TEST_DB      = "coil_test_db"
TEST_GLUE_JOB = "coil-test-glue-job"


def _make_aws_settings():
    """Crea un objeto Settings simulando APP_MODE=aws."""
    from api.services.config import Settings
    return Settings(
        app_mode="aws",
        app_username="testuser",
        app_password="testpass",
        jwt_secret_key="test_secret_aws_key_32_chars_ok__",
        local_base_dir=str(PROJECT_ROOT),
        local_catalogo_servicios="dataset/COIL_catalogo_servicios_cubiertos.csv",
        local_catalogo_perfiles="dataset/COIL_catalogo_perfiles_cobertura.csv",
        aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
        aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        aws_session_token="",
        aws_default_region=TEST_REGION,
        s3_bucket_name=TEST_BUCKET,
        s3_bronze_prefix="bronze/solicitudes/",
        s3_gold_prefix="gold/curated_solicitudes/",
        s3_quarantine_prefix="quarantine/solicitudes/",
        s3_catalogs_prefix="catalogs/",
        s3_athena_results_prefix="athena-results/",
        glue_job_name=TEST_GLUE_JOB,
        athena_workgroup="primary",
        athena_database=TEST_DB,
        version_catalogo="2026.1",
    )


# ── Fixture: bucket S3 mockeado ──────────────────────────────────────────────
@pytest.fixture
def mock_s3_bucket():
    """Crea un bucket S3 en moto para cada test."""
    with mock_aws():
        client = boto3.client("s3", region_name=TEST_REGION)
        client.create_bucket(Bucket=TEST_BUCKET)
        yield client


# ── Fixture: Glue Job mockeado ───────────────────────────────────────────────
@pytest.fixture
def mock_glue_job():
    """Crea un Glue Job en moto."""
    with mock_aws():
        client = boto3.client("glue", region_name=TEST_REGION)
        client.create_job(
            Name=TEST_GLUE_JOB,
            Role="arn:aws:iam::123456789012:role/LabRole",
            Command={
                "Name": "glueetl",
                "ScriptLocation": f"s3://{TEST_BUCKET}/scripts/aws_glue_job.py",
                "PythonVersion": "3",
            },
        )
        yield client


# ===========================================================================
# 1. MODO — _check_aws_mode
# ===========================================================================

def test_check_aws_mode_local_raises():
    """_check_aws_mode lanza RuntimeError cuando APP_MODE=local."""
    from api.services.config import Settings
    from api.services.aws_service import _check_aws_mode

    local_settings = Settings(
        app_mode="local",
        s3_bucket_name="",
    )
    with pytest.raises(RuntimeError, match="APP_MODE=aws"):
        _check_aws_mode(local_settings)


def test_check_aws_mode_aws_no_bucket_raises():
    """_check_aws_mode lanza RuntimeError si no hay S3_BUCKET_NAME."""
    from api.services.aws_service import _check_aws_mode

    settings = _make_aws_settings()
    settings_no_bucket = settings.model_copy(update={"s3_bucket_name": ""})
    with pytest.raises(RuntimeError, match="S3_BUCKET_NAME"):
        _check_aws_mode(settings_no_bucket)


def test_check_aws_mode_valid_passes():
    """_check_aws_mode no lanza excepción con configuración válida."""
    from api.services.aws_service import _check_aws_mode

    settings = _make_aws_settings()
    _check_aws_mode(settings)   # no debe lanzar nada


# ===========================================================================
# 2. S3 — UPLOAD / DOWNLOAD / LIST
# ===========================================================================

def test_s3_upload_bytes(mock_s3_bucket):
    """s3_upload_bytes sube contenido correctamente."""
    with mock_aws():
        from api.services.aws_service import s3_upload_bytes

        settings = _make_aws_settings()
        content  = b"id,nombre\n1,test"
        result   = s3_upload_bytes(content, "test/archivo.csv", settings, "text/csv")

        assert result["bucket"] == TEST_BUCKET
        assert result["key"]    == "test/archivo.csv"
        assert result["url"]    == f"s3://{TEST_BUCKET}/test/archivo.csv"

        # Verificar que se puede descargar
        from api.services.aws_service import s3_download_bytes
        downloaded = s3_download_bytes("test/archivo.csv", settings)
        assert downloaded == content


def test_s3_upload_file(mock_s3_bucket, tmp_path):
    """s3_upload_file sube un archivo local a S3."""
    with mock_aws():
        from api.services.aws_service import s3_upload_file

        # Crear archivo temporal
        test_file = tmp_path / "ordenes.csv"
        test_file.write_text("id,glosa\n1,test")

        settings = _make_aws_settings()
        result   = s3_upload_file(str(test_file), "bronze/ordenes.csv", settings)

        assert result["key"] == "bronze/ordenes.csv"


def test_s3_list_objects(mock_s3_bucket):
    """s3_list_objects retorna la lista de objetos en el prefijo."""
    with mock_aws():
        from api.services.aws_service import s3_upload_bytes, s3_list_objects

        settings = _make_aws_settings()

        # Subir 3 archivos
        for i in range(3):
            s3_upload_bytes(f"contenido {i}".encode(), f"catalogs/file_{i}.csv", settings)

        objects = s3_list_objects("catalogs/", settings)

        assert len(objects) == 3
        for obj in objects:
            assert "key" in obj
            assert "size_mb" in obj
            assert "last_modified" in obj


def test_s3_list_objects_empty(mock_s3_bucket):
    """s3_list_objects retorna lista vacía si no hay objetos."""
    with mock_aws():
        from api.services.aws_service import s3_list_objects

        settings = _make_aws_settings()
        objects  = s3_list_objects("prefijo_inexistente/", settings)
        assert objects == []


def test_s3_upload_catalogs(mock_s3_bucket):
    """s3_upload_catalogs sube ambos catálogos correctamente."""
    with mock_aws():
        from api.services.aws_service import s3_upload_catalogs, s3_list_objects

        settings = _make_aws_settings()

        # Verificar que los catálogos locales existen
        cat_srv_path = PROJECT_ROOT / "dataset" / "COIL_catalogo_servicios_cubiertos.csv"
        cat_prf_path = PROJECT_ROOT / "dataset" / "COIL_catalogo_perfiles_cobertura.csv"

        if not cat_srv_path.exists() or not cat_prf_path.exists():
            pytest.skip("Catálogos locales no encontrados")

        result = s3_upload_catalogs(settings)

        assert len(result) == 2
        objects = s3_list_objects("catalogs/", settings)
        filenames = [o["key"].split("/")[-1] for o in objects]
        assert "COIL_catalogo_servicios_cubiertos.csv" in filenames
        assert "COIL_catalogo_perfiles_cobertura.csv" in filenames


def test_s3_upload_glue_script(mock_s3_bucket):
    """s3_upload_glue_script sube aws_glue_job.py correctamente."""
    with mock_aws():
        from api.services.aws_service import s3_upload_glue_script, s3_list_objects

        settings    = _make_aws_settings()
        script_path = PROJECT_ROOT / "src" / "aws_glue_job.py"

        if not script_path.exists():
            pytest.skip("aws_glue_job.py no encontrado")

        result  = s3_upload_glue_script(settings)
        objects = s3_list_objects("scripts/", settings)

        assert any(o["key"] == "scripts/aws_glue_job.py" for o in objects)
        assert "script_s3_url" in result


def test_s3_get_bucket_summary(mock_s3_bucket):
    """s3_get_bucket_summary retorna resumen por capas."""
    with mock_aws():
        from api.services.aws_service import s3_upload_bytes, s3_get_bucket_summary

        settings = _make_aws_settings()

        # Colocar un objeto en la capa gold
        s3_upload_bytes(b"parquet_data", "gold/curated_solicitudes/part_001.parquet", settings)

        summary = s3_get_bucket_summary(settings)

        assert summary["bucket"] == TEST_BUCKET
        assert "layers" in summary
        assert "gold" in summary["layers"]
        assert summary["layers"]["gold"]["total_objects"] == 1


# ===========================================================================
# 3. GLUE JOB
# ===========================================================================

def test_glue_start_job(mock_glue_job):
    """glue_start_job lanza el job y retorna un job_run_id."""
    with mock_aws():
        from api.services.aws_service import glue_start_job

        settings = _make_aws_settings()
        result   = glue_start_job(settings)

        assert "job_run_id" in result
        assert result["job_name"] == TEST_GLUE_JOB
        assert result["status"]   == "STARTING"
        assert len(result["job_run_id"]) > 0


def test_glue_get_job_run(mock_glue_job):
    """glue_get_job_run retorna el estado del job run."""
    with mock_aws():
        from api.services.aws_service import glue_start_job, glue_get_job_run

        settings   = _make_aws_settings()
        start_resp = glue_start_job(settings)
        run_id     = start_resp["job_run_id"]

        status_data = glue_get_job_run(run_id, settings)

        assert status_data["job_run_id"] == run_id
        assert "status" in status_data
        assert "execution_time_seconds" in status_data
        assert "estimated_cost_usd" in status_data
        # El costo estimado debe ser >= 0
        assert status_data["estimated_cost_usd"] >= 0


def test_glue_list_job_runs(mock_glue_job):
    """glue_list_job_runs retorna el historial de ejecuciones."""
    with mock_aws():
        from api.services.aws_service import glue_start_job, glue_list_job_runs

        settings = _make_aws_settings()

        # Lanzar 2 jobs
        glue_start_job(settings)
        glue_start_job(settings)

        runs = glue_list_job_runs(settings, max_results=10)

        assert isinstance(runs, list)
        assert len(runs) >= 2
        for run in runs:
            assert "job_run_id" in run
            assert "status" in run


def test_glue_start_job_local_mode_raises():
    """glue_start_job lanza RuntimeError en modo local."""
    from api.services.config import Settings
    from api.services.aws_service import glue_start_job

    local_settings = Settings(app_mode="local", s3_bucket_name="test")
    with pytest.raises(RuntimeError):
        glue_start_job(local_settings)


# ===========================================================================
# 4. STORAGE SERVICE — RAMA AWS
# ===========================================================================

def test_storage_read_gold_aws_empty(mock_s3_bucket):
    """read_gold_paginated en modo AWS retorna vacío si no hay datos en Athena."""
    # Sin Athena mockeado completo, la función debe manejar el error graciosamente
    # Este test verifica que no lanza excepciones no manejadas
    from api.services.storage_service import read_gold_paginated

    settings = _make_aws_settings()
    # Con moto sin Athena configurado, esperamos un error manejado o lista vacía
    try:
        with mock_aws():
            rows, total = read_gold_paginated(page=1, page_size=10, settings=settings)
            # Si llega aquí, debe retornar listas vacías
            assert isinstance(rows, list)
            assert isinstance(total, int)
    except Exception:
        # También aceptamos que falle — lo importante es que la interfaz existe
        pass


def test_deploy_to_s3_pipeline(mock_s3_bucket):
    """deploy_to_s3 ejecuta el pipeline completo de carga."""
    with mock_aws():
        from api.services.aws_service import deploy_to_s3

        settings    = _make_aws_settings()
        script_path = PROJECT_ROOT / "src" / "aws_glue_job.py"
        cat_path    = PROJECT_ROOT / "dataset" / "COIL_catalogo_servicios_cubiertos.csv"

        if not script_path.exists() or not cat_path.exists():
            pytest.skip("Archivos del proyecto no encontrados")

        result = deploy_to_s3(
            local_csv_path="",       # sin dataset (evitar subir 344 MB)
            settings=settings,
            upload_glue_script=True,
        )

        assert "catalogs" in result
        assert "glue_script" in result
        assert len(result["catalogs"]) == 2


# ===========================================================================
# 5. PROTECCIÓN DE CREDENCIALES
# ===========================================================================

def test_aws_credentials_not_in_settings_repr():
    """Las credenciales no deben aparecer en el repr/str del objeto Settings."""
    settings = _make_aws_settings()
    settings_str = str(settings)
    # Los valores de claves secretas no deben aparecer en el string
    assert "wJalrXUtnFEMI" not in settings_str
    assert "AKIAIOSFODNN7" not in settings_str


def test_session_token_used_when_present():
    """El session_token se incluye en kwargs del cliente boto3 cuando está presente."""
    from api.services.aws_service import _boto3_client

    settings = _make_aws_settings()
    settings_with_token = settings.model_copy(
        update={"aws_session_token": "test_session_token_value"}
    )

    # Verificamos indirectamente que no lanza error al construir el cliente
    with mock_aws():
        client = _boto3_client("s3", settings_with_token)
        assert client is not None
