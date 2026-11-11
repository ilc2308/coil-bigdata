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


class RawCredentialsRequest(BaseModel):
    raw_credentials: str


def _persist_env_credentials(env_path: str, ak: str, sk: str, stk: str):
    """Guarda las credenciales en .env para que persistan ante reinicios de contenedor."""
    import os
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        new_lines = []
        keys_set = set()
        for line in lines:
            if line.startswith("AWS_ACCESS_KEY_ID="):
                new_lines.append(f"AWS_ACCESS_KEY_ID={ak}\n")
                keys_set.add("AWS_ACCESS_KEY_ID")
            elif line.startswith("AWS_SECRET_ACCESS_KEY="):
                new_lines.append(f"AWS_SECRET_ACCESS_KEY={sk}\n")
                keys_set.add("AWS_SECRET_ACCESS_KEY")
            elif line.startswith("AWS_SESSION_TOKEN="):
                new_lines.append(f"AWS_SESSION_TOKEN={stk}\n")
                keys_set.add("AWS_SESSION_TOKEN")
            elif line.startswith("APP_MODE="):
                new_lines.append("APP_MODE=aws\n")
                keys_set.add("APP_MODE")
            else:
                new_lines.append(line)

        if "AWS_ACCESS_KEY_ID" not in keys_set:
            new_lines.append(f"AWS_ACCESS_KEY_ID={ak}\n")
        if "AWS_SECRET_ACCESS_KEY" not in keys_set:
            new_lines.append(f"AWS_SECRET_ACCESS_KEY={sk}\n")
        if "AWS_SESSION_TOKEN" not in keys_set:
            new_lines.append(f"AWS_SESSION_TOKEN={stk}\n")

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Estado / conectividad
# ---------------------------------------------------------------------------

@router.get(
    "/status",
    summary="Verificar conexión con AWS",
    description=(
        "Verifica que las credenciales son válidas intentando un STS GetCallerIdentity. "
        "Soporta detección automática mediante Roles IAM (LabRole / EC2 IMDS) y fallback."
    ),
)
async def aws_status(
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    _require_aws(settings)

    import boto3
    from api.services.aws_service import _boto3_client
    from api.services.config import update_settings

    # 1. Intentar primero con el cliente configurado
    try:
        sts = _boto3_client("sts", settings)
        resp = sts.get_caller_identity()
        arn = resp.get("Arn", "")
        source = "Rol IAM (LabRole / EC2 IMDS)" if ("role" in arn.lower() or "instance" in arn.lower()) else "Credenciales explícitas (.env)"
        return {
            "status":      "connected",
            "auth_source": source,
            "account":     resp.get("Account", ""),
            "arn":         arn,
            "region":      settings.aws_default_region,
            "bucket":      settings.s3_bucket_name,
            "glue_job":    settings.glue_job_name,
            "athena_db":   settings.athena_database,
            "workgroup":   settings.athena_workgroup,
        }
    except Exception as exc_first:
        # 2. Si falló (token expirado), intentar auto-detección limpia con Boto3 default chain
        try:
            sts_auto = boto3.client("sts", region_name=settings.aws_default_region)
            resp = sts_auto.get_caller_identity()
            arn = resp.get("Arn", "")
            source = "Rol IAM (LabRole / EC2 IMDS)" if ("role" in arn.lower() or "instance" in arn.lower()) else "AWS Credentials Chain"
            
            # Limpiar credenciales expiradas en memoria
            update_settings(aws_access_key_id="auto", aws_secret_access_key="", aws_session_token="")

            return {
                "status":      "connected",
                "auth_source": source,
                "account":     resp.get("Account", ""),
                "arn":         arn,
                "region":      settings.aws_default_region,
                "bucket":      settings.s3_bucket_name,
                "glue_job":    settings.glue_job_name,
                "athena_db":   settings.athena_database,
                "workgroup":   settings.athena_workgroup,
                "notice":      "Auto-detección activada: las credenciales anteriores expiraron.",
            }
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"No se puede conectar con AWS: {str(exc_first)}",
            )


@router.post(
    "/credentials/parse",
    summary="Parsear y activar credenciales pegadas de AWS Learner Lab",
    description=(
        "Permite pegar el bloque completo de 'AWS Details' (ej: [default] aws_access_key_id=...). "
        "Extrae las variables, valida la conexión con STS y actualiza la configuración en memoria y en .env."
    ),
)
async def parse_and_apply_credentials(
    request: RawCredentialsRequest,
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    import re
    import os
    import boto3
    from api.services.config import update_settings

    text = request.raw_credentials.strip()
    if not text:
        raise HTTPException(status_code=400, detail="El bloque de texto de credenciales está vacío.")

    # Extraer con expresiones regulares tolerantes a [default], export KEY=val, o KEY=val
    ak_match = re.search(r'(?:aws_access_key_id|AWS_ACCESS_KEY_ID)\s*=\s*["\']?([A-Za-z0-9_\-]+)["\']?', text)
    sk_match = re.search(r'(?:aws_secret_access_key|AWS_SECRET_ACCESS_KEY)\s*=\s*["\']?([A-Za-z0-9/+=_\-]+)["\']?', text)
    st_match = re.search(r'(?:aws_session_token|AWS_SESSION_TOKEN)\s*=\s*["\']?([A-Za-z0-9/+=_\-]+)["\']?', text)

    if not ak_match or not sk_match:
        raise HTTPException(
            status_code=400,
            detail="No se encontraron aws_access_key_id o aws_secret_access_key en el texto pegado."
        )

    ak = ak_match.group(1).strip()
    sk = sk_match.group(1).strip()
    stk = st_match.group(1).strip() if st_match else ""

    # Validar inmediatamente contra AWS STS
    try:
        kwargs = {
            "region_name": settings.aws_default_region,
            "aws_access_key_id": ak,
            "aws_secret_access_key": sk,
        }
        if stk:
            kwargs["aws_session_token"] = stk
        sts = boto3.client("sts", **kwargs)
        resp = sts.get_caller_identity()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Credenciales inválidas o rechazadas por AWS STS: {str(exc)}"
        )

    # Actualizar configuración en caliente
    update_settings(
        app_mode="aws",
        aws_access_key_id=ak,
        aws_secret_access_key=sk,
        aws_session_token=stk,
    )

    # Persistir en .env
    env_file = os.path.join(str(settings.base_dir), ".env")
    _persist_env_credentials(env_file, ak, sk, stk)

    return {
        "status": "success",
        "message": "Credenciales detectadas, validadas y activadas exitosamente",
        "account": resp.get("Account"),
        "arn": resp.get("Arn"),
    }


@router.post(
    "/auto-detect",
    summary="Detectar automáticamente credenciales de AWS (IAM Role / IMDS / ~/.aws)",
    description=(
        "Intenta autenticarse sin credenciales fijas, usando la cadena estándar de AWS "
        "(Rol IAM LabRole de EC2 o archivo ~/.aws/credentials del host)."
    ),
)
async def auto_detect_credentials(
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    import os
    import boto3
    from api.services.config import update_settings

    try:
        sts = boto3.client("sts", region_name=settings.aws_default_region)
        resp = sts.get_caller_identity()
        arn = resp.get("Arn", "")
        source = "Rol IAM (LabRole / EC2 IMDS)" if ("role" in arn.lower() or "instance" in arn.lower()) else "AWS Credentials Chain"

        update_settings(
            app_mode="aws",
            aws_access_key_id="auto",
            aws_secret_access_key="",
            aws_session_token="",
        )

        env_file = os.path.join(str(settings.base_dir), ".env")
        _persist_env_credentials(env_file, "auto", "", "")

        return {
            "status": "success",
            "message": f"Conexión automática exitosa mediante {source}",
            "auth_source": source,
            "account": resp.get("Account"),
            "arn": arn,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"No se detectaron credenciales automáticas en el entorno (IMDS/LabRole o ~/.aws): {str(exc)}"
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
