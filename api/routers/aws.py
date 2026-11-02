"""
routers/aws.py
Endpoints de integración con AWS (S3, Glue, Athena).
Solo disponibles cuando APP_MODE=aws.

GET  /api/v1/aws/status              — verificar conexión AWS y listar recursos
GET  /api/v1/aws/s3/summary          — resumen del bucket S3 por capas
GET  /api/v1/aws/s3/list             — listar objetos en un prefijo S3
POST /api/v1/aws/s3/upload-catalogs  — subir catálogos locales a S3
POST /api/v1/aws/s3/upload-dataset   — subir CSV de órdenes a Bronze
POST /api/v1/aws/s3/upload-script    — subir aws_glue_job.py a S3/scripts/
POST /api/v1/aws/deploy              — pipeline completo de deploy a S3
GET  /api/v1/aws/glue/runs           — historial de ejecuciones del Glue Job
GET  /api/v1/aws/glue/{run_id}       — estado de un Glue Job Run
POST /api/v1/aws/athena/query        — ejecutar SQL en Athena (máx 1000 filas)
GET  /api/v1/aws/athena/views        — consultar una vista analítica
POST /api/v1/aws/athena/repair       — MSCK REPAIR TABLE para cargar particiones
GET  /api/v1/aws/athena/tables       — listar tablas del Glue Data Catalog
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel

from api.middleware.auth import get_current_user
from api.services.config import Settings, get_settings

router = APIRouter(prefix="/api/v1/aws", tags=["AWS"])


# ---------------------------------------------------------------------------
# Guard helper
# ---------------------------------------------------------------------------

def _require_aws(settings: Settings):
    """Lanza 400 si la app no está en modo aws."""
    if settings.is_local:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Este endpoint requiere APP_MODE=aws. "
                "Edita .env con APP_MODE=aws y S3_BUCKET_NAME, "
                "luego reinicia la API."
            ),
        )
    if not settings.s3_bucket_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="S3_BUCKET_NAME no configurado en .env",
        )


# ---------------------------------------------------------------------------
# Schemas de entrada
# ---------------------------------------------------------------------------

class AthenaQueryRequest(BaseModel):
    sql: str
    max_rows: int = 500
    timeout_seconds: int = 120


class DeployRequest(BaseModel):
    local_csv_path: Optional[str] = None
    upload_glue_script: bool = True


# ---------------------------------------------------------------------------
# Estado / conectividad
# ---------------------------------------------------------------------------

@router.get(
    "/status",
    summary="Verificar conexión con AWS",
    description=(
        "Verifica que las credenciales son válidas intentando un STS GetCallerIdentity. "
        "No genera costos."
    ),
)
async def aws_status(
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    _require_aws(settings)

    try:
        import boto3
        kwargs: Dict[str, Any] = {"region_name": settings.aws_default_region}
        if settings.aws_access_key_id:
            kwargs["aws_access_key_id"]     = settings.aws_access_key_id
            kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        if settings.aws_session_token:
            kwargs["aws_session_token"] = settings.aws_session_token

        sts  = boto3.client("sts", **kwargs)
        resp = sts.get_caller_identity()

        return {
            "status":    "connected",
            "account":   resp.get("Account", ""),
            "arn":       resp.get("Arn", ""),
            "region":    settings.aws_default_region,
            "bucket":    settings.s3_bucket_name,
            "glue_job":  settings.glue_job_name,
            "athena_db": settings.athena_database,
            "workgroup": settings.athena_workgroup,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No se puede conectar con AWS: {str(exc)}",
        )


# ---------------------------------------------------------------------------
# S3
# ---------------------------------------------------------------------------

@router.get(
    "/s3/summary",
    summary="Resumen del bucket S3 por capas",
)
async def s3_summary(
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    _require_aws(settings)
    try:
        from api.services.aws_service import s3_get_bucket_summary
        return s3_get_bucket_summary(settings)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/s3/list",
    summary="Listar objetos en un prefijo S3",
)
async def s3_list(
    prefix: str = Query(default="", description="Prefijo S3, ej: bronze/solicitudes/"),
    max_keys: int = Query(default=100, ge=1, le=1000),
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    _require_aws(settings)
    try:
        from api.services.aws_service import s3_list_objects
        objects = s3_list_objects(prefix, settings, max_keys)
        return {"prefix": prefix, "total": len(objects), "objects": objects}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/s3/upload-catalogs",
    summary="Subir catálogos locales a S3",
    description=(
        "Sube COIL_catalogo_servicios_cubiertos.csv y COIL_catalogo_perfiles_cobertura.csv "
        "al prefijo catalogs/ del bucket S3. Necesario antes del primer Glue Job."
    ),
)
async def upload_catalogs(
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    _require_aws(settings)
    try:
        from api.services.aws_service import s3_upload_catalogs
        result = s3_upload_catalogs(settings)
        return {"uploaded": result, "message": "Catálogos subidos a S3 exitosamente."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/s3/upload-script",
    summary="Subir aws_glue_job.py a S3",
    description="Sube el script Spark al prefijo scripts/ del bucket. Necesario antes del primer Glue Job.",
)
async def upload_glue_script(
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    _require_aws(settings)
    try:
        from api.services.aws_service import s3_upload_glue_script
        result = s3_upload_glue_script(settings)
        return {"uploaded": result, "message": "Script Glue subido a S3 exitosamente."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/s3/upload-dataset",
    summary="Subir CSV de órdenes a la capa Bronze",
    description=(
        "Sube un CSV del servidor (dataset/ o uploads/) a s3://<bucket>/bronze/solicitudes/. "
        "Este archivo es el que el Glue Job procesará."
    ),
)
async def upload_dataset(
    filename: str = Body(..., embed=True, description="Nombre del CSV en dataset/ o uploads/"),
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    _require_aws(settings)
    from pathlib import Path

    # Resolver ruta local
    local_path = None
    for base in [Path(settings.base_dir) / "dataset", Path(settings.upload_dir)]:
        candidate = base / filename
        if candidate.exists():
            local_path = str(candidate)
            break

    if not local_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Archivo '{filename}' no encontrado en dataset/ ni uploads/",
        )

    try:
        from api.services.aws_service import s3_upload_dataset
        result = s3_upload_dataset(local_path, settings)
        return {
            "filename": filename,
            "s3_url":   result["s3_url"],
            "message":  f"'{filename}' subido a la capa Bronze de S3.",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/deploy",
    summary="Pipeline completo de deploy a S3",
    description=(
        "Ejecuta en secuencia: subir catálogos + script Glue + CSV (opcional). "
        "Deja el bucket listo para lanzar el Glue Job."
    ),
)
async def deploy_pipeline(
    request: DeployRequest,
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    _require_aws(settings)
    try:
        from api.services.aws_service import deploy_to_s3
        result = deploy_to_s3(
            local_csv_path=request.local_csv_path or "",
            settings=settings,
            upload_glue_script=request.upload_glue_script,
        )
        return {"deployed": result, "message": "Deploy a S3 completado. Listo para lanzar el Glue Job."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Glue
# ---------------------------------------------------------------------------

@router.get(
    "/glue/runs",
    summary="Historial de ejecuciones del Glue Job",
)
async def glue_list_runs(
    max_results: int = Query(default=20, ge=1, le=100),
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    _require_aws(settings)
    try:
        from api.services.aws_service import glue_list_job_runs
        runs = glue_list_job_runs(settings, max_results)
        return {"job_name": settings.glue_job_name, "total": len(runs), "runs": runs}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/glue/{job_run_id}",
    summary="Estado de un Glue Job Run",
)
async def glue_run_status(
    job_run_id: str,
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    _require_aws(settings)
    try:
        from api.services.aws_service import glue_get_job_run
        return glue_get_job_run(job_run_id, settings)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Athena
# ---------------------------------------------------------------------------

@router.post(
    "/athena/query",
    summary="Ejecutar SQL en Athena",
    description=(
        "Ejecuta una consulta SQL en Athena y retorna hasta `max_rows` filas. "
        "⚠️ Athena cobra $5 por TB escaneado. Usa filtros de partición para reducir costos."
    ),
)
async def athena_query(
    request: AthenaQueryRequest,
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    _require_aws(settings)

    # Bloquear operaciones de escritura/DDL desde este endpoint
    sql_upper = request.sql.strip().upper()
    forbidden = ("DROP", "DELETE", "TRUNCATE", "INSERT", "UPDATE", "ALTER", "CREATE")
    if any(sql_upper.startswith(kw) for kw in forbidden):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten consultas SELECT desde este endpoint.",
        )

    try:
        from api.services.aws_service import athena_execute_and_fetch
        headers, rows = athena_execute_and_fetch(
            request.sql, settings, request.max_rows, request.timeout_seconds
        )
        return {
            "query":   request.sql[:200],
            "total":   len(rows),
            "headers": headers,
            "rows":    rows,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/athena/views",
    summary="Consultar una vista analítica de Athena",
    description=(
        "Consulta una de las 3 vistas ejecutivas definidas en athena_ddl.sql. "
        "Vistas: v_resumen_cobertura_ejecutivo | v_analisis_canal_entidad | v_auditoria_servicios_alertas"
    ),
)
async def athena_get_view(
    view: str = Query(
        description="Nombre de la vista analítica",
        examples=["v_resumen_cobertura_ejecutivo"],
    ),
    max_rows: int = Query(default=500, ge=1, le=1000),
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    _require_aws(settings)
    try:
        from api.services.aws_service import athena_get_view_data
        headers, rows = athena_get_view_data(view, settings, max_rows)
        return {"view": view, "total": len(rows), "headers": headers, "rows": rows}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/athena/repair",
    summary="MSCK REPAIR TABLE — cargar particiones",
    description=(
        "Ejecuta MSCK REPAIR TABLE para que Athena detecte las nuevas particiones "
        "creadas por el Glue Job. Ejecutar después de cada corrida de Glue."
    ),
)
async def athena_repair(
    table: str = Body(
        default="gold_solicitudes_cobertura",
        embed=True,
        description="Tabla a reparar (gold_solicitudes_cobertura o quarentena_solicitudes)",
    ),
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    _require_aws(settings)
    allowed = {"gold_solicitudes_cobertura", "quarentena_solicitudes"}
    if table not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tabla no permitida. Opciones: {allowed}",
        )
    try:
        from api.services.aws_service import athena_repair_table
        result = athena_repair_table(table, settings)
        return {"table": table, "result": result, "message": "Particiones cargadas exitosamente."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/athena/tables",
    summary="Listar tablas del Glue Data Catalog",
)
async def athena_list(
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    _require_aws(settings)
    try:
        from api.services.aws_service import athena_list_tables
        tables = athena_list_tables(settings)
        return {"database": settings.athena_database, "tables": tables}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
