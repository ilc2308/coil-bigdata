"""
services/aws_service.py
Servicio centralizado para operaciones AWS.

Cubre:
  - S3: upload, download, list, delete, presigned URLs
  - AWS Glue: start job, get job status, list job runs
  - Amazon Athena: execute query, get results paginados, list tables/views
  - Catálogos: subir catálogos locales a S3 para que Glue los use

SEGURIDAD:
  - Las credenciales NUNCA se hardcodean — vienen de Settings (desde .env)
  - Los valores de credenciales no se loguean ni se retornan al cliente
  - Los session_token del Learner Lab tienen expiración de ~4 horas
  - Permisos mínimos: solo las operaciones que el proyecto necesita
"""

from __future__ import annotations

import io
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from api.services.config import Settings


# ---------------------------------------------------------------------------
# Factory de clientes boto3
# ---------------------------------------------------------------------------

def _boto3_client(service: str, settings: Settings):
    """
    Crea un cliente boto3 con resolución y detección automática:
    1. Si hay credenciales explícitas configuradas (y no son 'auto'):
       Intenta usarlas.
    2. Si están configuradas como 'auto' o vacías:
       Usa la cadena de resolución estándar de AWS:
       - Rol IAM de EC2 (Instance Metadata Service IMDS / LabRole)
       - Archivo ~/.aws/credentials o ~/.aws/config
       - Variables de entorno del sistema
    3. Si las credenciales explícitas fallan o están vencidas, hace fallback automático a IMDS/boto3 default.
    """
    import boto3

    region = settings.aws_default_region or "us-east-1"
    explicit_key = (settings.aws_access_key_id or "").strip()
    is_auto = explicit_key.lower() in ("auto", "none", "null", "")

    if not is_auto:
        kwargs: Dict[str, Any] = {
            "region_name": region,
            "aws_access_key_id": explicit_key,
            "aws_secret_access_key": (settings.aws_secret_access_key or "").strip(),
        }
        if settings.aws_session_token and settings.aws_session_token.strip():
            kwargs["aws_session_token"] = settings.aws_session_token.strip()

        try:
            return boto3.client(service, **kwargs)
        except Exception:
            pass

    # Modo automático: Boto3 busca en IMDS (LabRole), ~/.aws/credentials o variables de entorno
    return boto3.client(service, region_name=region)


def _check_aws_mode(settings: Settings):
    """Lanza RuntimeError si la app no está en modo aws."""
    if settings.is_local:
        raise RuntimeError(
            "Operación solo disponible en APP_MODE=aws. "
            "Edita APP_MODE=aws en tu .env y reinicia la API."
        )
    if not settings.s3_bucket_name:
        raise RuntimeError(
            "S3_BUCKET_NAME no configurado en .env. "
            "Especifica el bucket de tu Learner Lab."
        )


# ===========================================================================
# S3
# ===========================================================================

def s3_upload_file(
    local_path: str,
    s3_key: str,
    settings: Settings,
    content_type: str = "application/octet-stream",
) -> Dict[str, str]:
    """
    Sube un archivo local a S3.

    Returns:
        {"bucket": ..., "key": ..., "url": "s3://..."}
    """
    _check_aws_mode(settings)
    s3 = _boto3_client("s3", settings)
    s3.upload_file(
        local_path,
        settings.s3_bucket_name,
        s3_key,
        ExtraArgs={"ContentType": content_type},
    )
    return {
        "bucket": settings.s3_bucket_name,
        "key": s3_key,
        "url": f"s3://{settings.s3_bucket_name}/{s3_key}",
    }


def s3_upload_bytes(
    content: bytes,
    s3_key: str,
    settings: Settings,
    content_type: str = "application/octet-stream",
) -> Dict[str, str]:
    """Sube bytes en memoria a S3 (sin archivo temporal)."""
    _check_aws_mode(settings)
    s3 = _boto3_client("s3", settings)
    s3.put_object(
        Bucket=settings.s3_bucket_name,
        Key=s3_key,
        Body=content,
        ContentType=content_type,
    )
    return {
        "bucket": settings.s3_bucket_name,
        "key": s3_key,
        "url": f"s3://{settings.s3_bucket_name}/{s3_key}",
    }


def s3_list_objects(
    prefix: str,
    settings: Settings,
    max_keys: int = 1000,
) -> List[Dict[str, Any]]:
    """
    Lista objetos en S3 con un prefijo dado.
    Retorna lista de {key, size_mb, last_modified}.
    """
    _check_aws_mode(settings)
    s3 = _boto3_client("s3", settings)

    response = s3.list_objects_v2(
        Bucket=settings.s3_bucket_name,
        Prefix=prefix,
        MaxKeys=max_keys,
    )

    objects = []
    for obj in response.get("Contents", []):
        objects.append({
            "key":           obj["Key"],
            "size_mb":       round(obj["Size"] / 1_048_576, 3),
            "last_modified": str(obj["LastModified"]),
        })
    return objects


def s3_download_bytes(s3_key: str, settings: Settings) -> bytes:
    """Descarga un objeto de S3 y retorna sus bytes."""
    _check_aws_mode(settings)
    s3 = _boto3_client("s3", settings)
    buf = io.BytesIO()
    s3.download_fileobj(settings.s3_bucket_name, s3_key, buf)
    buf.seek(0)
    return buf.read()


def s3_presigned_url(
    s3_key: str,
    settings: Settings,
    expires_in: int = 3600,
) -> str:
    """Genera una URL pre-firmada para descarga temporal (válida `expires_in` segundos)."""
    _check_aws_mode(settings)
    s3 = _boto3_client("s3", settings)
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket_name, "Key": s3_key},
        ExpiresIn=expires_in,
    )


def s3_get_bucket_summary(settings: Settings) -> Dict[str, Any]:
    """
    Retorna un resumen del bucket: capas bronze, gold, quarantine y scripts.
    """
    _check_aws_mode(settings)

    prefixes = {
        "bronze":     settings.s3_bronze_prefix,
        "gold":       settings.s3_gold_prefix,
        "quarantine": settings.s3_quarantine_prefix,
        "catalogs":   settings.s3_catalogs_prefix,
        "scripts":    "scripts/",
        "athena":     settings.s3_athena_results_prefix,
    }

    summary: Dict[str, Any] = {"bucket": settings.s3_bucket_name, "layers": {}}
    for layer, prefix in prefixes.items():
        objects = s3_list_objects(prefix, settings, max_keys=500)
        summary["layers"][layer] = {
            "prefix":        f"s3://{settings.s3_bucket_name}/{prefix}",
            "total_objects": len(objects),
            "total_size_mb": round(sum(o["size_mb"] for o in objects), 2),
        }
    return summary


def s3_upload_catalogs(settings: Settings) -> Dict[str, str]:
    """
    Sube los catálogos locales a S3 para que el Glue Job pueda usarlos.
    Rutas destino: s3://<bucket>/catalogs/COIL_catalogo_*.csv
    """
    _check_aws_mode(settings)

    results = {}
    for local_path in [settings.catalogo_servicios_path, settings.catalogo_perfiles_path]:
        filename = Path(local_path).name
        s3_key = f"{settings.s3_catalogs_prefix}{filename}"
        r = s3_upload_file(local_path, s3_key, settings, content_type="text/csv")
        results[filename] = r["url"]

    return results


def s3_upload_glue_script(settings: Settings) -> Dict[str, str]:
    """
    Sube el script aws_glue_job.py a S3 para que Glue lo ejecute.
    """
    _check_aws_mode(settings)

    script_path = str(Path(settings.base_dir) / "src" / "aws_glue_job.py")
    if not Path(script_path).exists():
        raise FileNotFoundError(f"Script Glue no encontrado: {script_path}")

    s3_key = "scripts/aws_glue_job.py"
    r = s3_upload_file(script_path, s3_key, settings, content_type="text/x-python")
    return {"script_s3_url": r["url"]}


def s3_upload_dataset(local_csv_path: str, settings: Settings) -> Dict[str, str]:
    """
    Sube un CSV de órdenes a la capa Bronze de S3.
    """
    _check_aws_mode(settings)

    filename = Path(local_csv_path).name
    s3_key = f"{settings.s3_bronze_prefix}{filename}"
    r = s3_upload_file(local_csv_path, s3_key, settings, content_type="text/csv")
    return {"s3_url": r["url"], "key": s3_key}


# ===========================================================================
# AWS GLUE
# ===========================================================================

def glue_start_job(
    settings: Settings,
    source_prefix: Optional[str] = None,
    target_prefix: Optional[str] = None,
    quarantine_prefix: Optional[str] = None,
) -> Dict[str, str]:
    """
    Lanza una ejecución del Glue Job de Spark.

    Returns:
        {"job_run_id": ..., "job_name": ..., "status": "STARTING"}
    """
    _check_aws_mode(settings)

    glue = _boto3_client("glue", settings)

    # Argumentos opcionales que sobreescriben los defaults del Job
    extra_args: Dict[str, str] = {}
    if source_prefix:
        extra_args["--SOURCE_PREFIX"] = source_prefix
    if target_prefix:
        extra_args["--TARGET_PREFIX"] = target_prefix
    if quarantine_prefix:
        extra_args["--QUARANTINE_PREFIX"] = quarantine_prefix

    response = glue.start_job_run(
        JobName=settings.glue_job_name,
        Arguments=extra_args if extra_args else {},
    )

    return {
        "job_run_id": response["JobRunId"],
        "job_name":   settings.glue_job_name,
        "status":     "STARTING",
    }


def glue_get_job_run(job_run_id: str, settings: Settings) -> Dict[str, Any]:
    """
    Consulta el estado de un Glue Job Run.

    Returns:
        {job_run_id, job_name, status, started_on, completed_on,
         execution_time_seconds, dpu_seconds, error_message}
    """
    _check_aws_mode(settings)

    glue = _boto3_client("glue", settings)
    resp = glue.get_job_run(JobName=settings.glue_job_name, RunId=job_run_id)
    run  = resp["JobRun"]

    started   = run.get("StartedOn")
    completed = run.get("CompletedOn")
    exec_time = run.get("ExecutionTime", 0)  # segundos

    # Estimación de costo: G.1X = 1 DPU, 2 workers × $0.308/DPU-hora
    cost_usd = (2 * exec_time / 3600.0) * 0.308 if exec_time else 0.0

    return {
        "job_run_id":              job_run_id,
        "job_name":                settings.glue_job_name,
        "status":                  run.get("JobRunState", "UNKNOWN"),
        "started_on":              str(started) if started else "",
        "completed_on":            str(completed) if completed else "",
        "execution_time_seconds":  exec_time,
        "estimated_cost_usd":      round(cost_usd, 6),
        "error_message":           run.get("ErrorMessage", ""),
    }


def glue_list_job_runs(
    settings: Settings,
    max_results: int = 20,
) -> List[Dict[str, Any]]:
    """Lista las últimas ejecuciones del Glue Job."""
    _check_aws_mode(settings)

    glue  = _boto3_client("glue", settings)
    resp  = glue.get_job_runs(JobName=settings.glue_job_name, MaxResults=max_results)
    runs  = resp.get("JobRuns", [])

    result = []
    for r in runs:
        exec_time = r.get("ExecutionTime", 0)
        cost_usd  = (2 * exec_time / 3600.0) * 0.308 if exec_time else 0.0
        result.append({
            "job_run_id":             r["Id"],
            "status":                 r.get("JobRunState", "UNKNOWN"),
            "started_on":             str(r.get("StartedOn", "")),
            "completed_on":           str(r.get("CompletedOn", "")),
            "execution_time_seconds": exec_time,
            "estimated_cost_usd":     round(cost_usd, 6),
        })
    return result


def glue_wait_for_completion(
    job_run_id: str,
    settings: Settings,
    timeout_seconds: int = 300,
    poll_interval: int = 10,
) -> Dict[str, Any]:
    """
    Bloquea hasta que el Glue Job finalice (o timeout).
    Solo para uso desde scripts de CLI, no desde endpoints API.
    """
    _check_aws_mode(settings)

    terminal_states = {"SUCCEEDED", "FAILED", "ERROR", "TIMEOUT", "STOPPED"}
    elapsed = 0

    while elapsed < timeout_seconds:
        status_data = glue_get_job_run(job_run_id, settings)
        if status_data["status"] in terminal_states:
            return status_data
        time.sleep(poll_interval)
        elapsed += poll_interval

    raise TimeoutError(
        f"Glue Job {job_run_id} no terminó en {timeout_seconds} segundos."
    )


# ===========================================================================
# AMAZON ATHENA
# ===========================================================================

_ATHENA_TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED"}
_ATHENA_POLL_INTERVAL = 2  # segundos entre polls


def athena_run_query(
    sql: str,
    settings: Settings,
    timeout_seconds: int = 120,
) -> str:
    """
    Ejecuta una consulta Athena y retorna el QueryExecutionId.
    No espera la finalización — usar athena_wait_for_query() para eso.
    """
    _check_aws_mode(settings)

    athena = _boto3_client("athena", settings)
    output_loc = f"s3://{settings.s3_bucket_name}/{settings.s3_athena_results_prefix.strip('/')}/"
    resp   = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": settings.athena_database},
        WorkGroup=settings.athena_workgroup,
        ResultConfiguration={"OutputLocation": output_loc},
    )
    return resp["QueryExecutionId"]


def athena_wait_for_query(
    query_execution_id: str,
    settings: Settings,
    timeout_seconds: int = 120,
) -> Dict[str, Any]:
    """
    Espera a que una consulta Athena termine.
    Retorna {query_id, status, state_change_reason, data_scanned_mb}.
    """
    _check_aws_mode(settings)

    athena  = _boto3_client("athena", settings)
    elapsed = 0

    while elapsed < timeout_seconds:
        resp   = athena.get_query_execution(QueryExecutionId=query_execution_id)
        status = resp["QueryExecution"]["Status"]
        state  = status["State"]

        if state in _ATHENA_TERMINAL:
            stats    = resp["QueryExecution"].get("Statistics", {})
            data_mb  = stats.get("DataScannedInBytes", 0) / 1_048_576

            if state == "FAILED":
                reason = status.get("StateChangeReason", "desconocido")
                raise RuntimeError(f"Athena query falló: {reason}")
            if state == "CANCELLED":
                raise RuntimeError("Athena query fue cancelada")

            return {
                "query_id":          query_execution_id,
                "status":            state,
                "data_scanned_mb":   round(data_mb, 4),
                "execution_time_ms": stats.get("TotalExecutionTimeInMillis", 0),
            }

        time.sleep(_ATHENA_POLL_INTERVAL)
        elapsed += _ATHENA_POLL_INTERVAL

    raise TimeoutError(
        f"Athena query {query_execution_id} no terminó en {timeout_seconds}s"
    )


def athena_get_results(
    query_execution_id: str,
    settings: Settings,
    max_rows: int = 1000,
) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    Obtiene los resultados de una consulta Athena finalizada.

    Returns:
        (headers: List[str], rows: List[Dict[str, str]])
    """
    _check_aws_mode(settings)

    athena = _boto3_client("athena", settings)
    # Athena incluye la fila de encabezados en el conteo de MaxResults,
    # por lo que pedimos max_rows + 1, con un tope estricto de 1000 (límite de la API de AWS).
    fetch_limit = min(max(max_rows + 1, 2), 1000)
    resp   = athena.get_query_results(
        QueryExecutionId=query_execution_id,
        MaxResults=fetch_limit,
    )

    result_rows = resp.get("ResultSet", {}).get("Rows", [])
    if not result_rows:
        return [], []

    # Primera fila = headers
    headers = [col.get("VarCharValue", "") for col in result_rows[0]["Data"]]
    rows    = []
    for row in result_rows[1:]:
        values = [cell.get("VarCharValue", "") for cell in row["Data"]]
        rows.append(dict(zip(headers, values)))

    return headers, rows


def athena_execute_and_fetch(
    sql: str,
    settings: Settings,
    max_rows: int = 1000,
    timeout_seconds: int = 120,
) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    Atajo: lanza query + espera + retorna resultados en una sola llamada.
    Para queries rápidas desde endpoints API.
    """
    qid = athena_run_query(sql, settings, timeout_seconds)
    athena_wait_for_query(qid, settings, timeout_seconds)
    return athena_get_results(qid, settings, max_rows)


def athena_repair_table(table: str, settings: Settings) -> Dict[str, Any]:
    """
    Ejecuta MSCK REPAIR TABLE para cargar nuevas particiones.
    Necesario después de un Glue Job que crea nuevas particiones Parquet.
    """
    sql = f"MSCK REPAIR TABLE {settings.athena_database}.{table};"
    qid = athena_run_query(sql, settings)
    return athena_wait_for_query(qid, settings)


def athena_list_tables(settings: Settings) -> List[str]:
    """Lista las tablas de la base de datos Athena/Glue Data Catalog."""
    _check_aws_mode(settings)

    glue = _boto3_client("glue", settings)
    resp = glue.get_tables(DatabaseName=settings.athena_database)
    return [t["Name"] for t in resp.get("TableList", [])]


def athena_get_view_data(
    view_name: str,
    settings: Settings,
    max_rows: int = 500,
) -> Tuple[List[str], List[Dict]]:
    """
    Consulta una de las 3 vistas analíticas definidas en athena_ddl.sql.

    Views disponibles:
        v_resumen_cobertura_ejecutivo
        v_analisis_canal_entidad
        v_auditoria_servicios_alertas
    """
    allowed_views = {
        "v_resumen_cobertura_ejecutivo",
        "v_analisis_canal_entidad",
        "v_auditoria_servicios_alertas",
    }
    if view_name not in allowed_views:
        raise ValueError(
            f"Vista '{view_name}' no permitida. Opciones: {allowed_views}"
        )

    sql = (
        f"SELECT * FROM {settings.athena_database}.{view_name} "
        f"LIMIT {max_rows};"
    )
    return athena_execute_and_fetch(sql, settings, max_rows)


# ===========================================================================
# Pipeline de deploy completo (para CLI / admin)
# ===========================================================================

def deploy_to_s3(
    local_csv_path: str,
    settings: Settings,
    upload_glue_script: bool = True,
) -> Dict[str, Any]:
    """
    Pipeline completo de carga a AWS:
      1. Subir catálogos a S3/catalogs/
      2. Subir script Glue a S3/scripts/
      3. Subir CSV de órdenes a S3/bronze/

    Returns:
        Diccionario con todas las URLs de S3 generadas.
    """
    _check_aws_mode(settings)

    results: Dict[str, Any] = {}

    # 1. Catálogos
    results["catalogs"] = s3_upload_catalogs(settings)

    # 2. Script Glue
    if upload_glue_script:
        results["glue_script"] = s3_upload_glue_script(settings)

    # 3. Dataset
    if local_csv_path and Path(local_csv_path).exists():
        results["dataset"] = s3_upload_dataset(local_csv_path, settings)

    return results
