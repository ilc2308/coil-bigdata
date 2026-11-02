"""
routers/process.py
Endpoints de procesamiento por lotes.

POST /api/v1/upload          — sube un CSV al directorio uploads/
POST /api/v1/process         — lanza un job de procesamiento en background
GET  /api/v1/process/{run_id} — consulta el estado del job
GET  /api/v1/process          — lista todos los jobs de la sesión
GET  /api/v1/uploads          — lista archivos disponibles en uploads/
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from api.middleware.auth import get_current_user
from api.schemas.metrics import ProcessJobStatus, ProcessStartRequest
from api.services import batch_service, storage_service
from api.services.config import Settings, get_settings

router = APIRouter(prefix="/api/v1", tags=["Procesamiento"])


# ---------------------------------------------------------------------------
# Upload de archivo CSV
# ---------------------------------------------------------------------------

@router.post(
    "/upload",
    summary="Subir archivo CSV",
    description="Sube un CSV de órdenes médicas al servidor para procesarlo después.",
)
async def upload_csv(
    file: UploadFile = File(...),
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    # Validar extensión
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se aceptan archivos CSV (.csv)",
        )

    content = await file.read()
    size_mb = len(content) / 1_048_576

    # Límite de 500 MB
    if size_mb > 500:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"El archivo excede el límite de 500 MB (tamaño: {size_mb:.1f} MB)",
        )

    saved_path = storage_service.save_uploaded_file(file.filename, content, settings)

    return {
        "filename": file.filename,
        "size_mb": round(size_mb, 2),
        "saved_path": saved_path,
        "message": f"Archivo '{file.filename}' guardado exitosamente. Listo para procesar.",
    }


@router.get(
    "/uploads",
    summary="Listar archivos disponibles",
    description="Lista los archivos CSV disponibles en uploads/ y en dataset/.",
)
async def list_available_files(
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    uploaded = storage_service.list_uploaded_files(settings)

    # Incluir también los archivos pre-existentes en dataset/
    dataset_files = []
    dataset_dir = os.path.join(str(settings.base_dir), "dataset")
    if os.path.exists(dataset_dir):
        for fn in os.listdir(dataset_dir):
            if fn.endswith(".csv"):
                fp = os.path.join(dataset_dir, fn)
                dataset_files.append({
                    "filename": fn,
                    "size_mb": round(os.path.getsize(fp) / 1_048_576, 2),
                    "source": "dataset/",
                })

    return {
        "uploaded": uploaded,
        "dataset": dataset_files,
    }


# ---------------------------------------------------------------------------
# Procesamiento
# ---------------------------------------------------------------------------

@router.post(
    "/process",
    response_model=Dict[str, Any],
    summary="Iniciar procesamiento por lotes",
    description=(
        "Lanza el procesamiento de un CSV en background. "
        "Retorna inmediatamente con el run_id. "
        "Consulta el estado con GET /process/{run_id}."
    ),
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_process(
    request: ProcessStartRequest,
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    try:
        result = await batch_service.start_batch_job(
            filename=request.filename,
            run_id=request.run_id,
            chunk_size=request.chunk_size,
            write_parquet=request.write_parquet,
            settings=settings,
        )
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/process",
    summary="Listar todos los jobs de la sesión",
)
async def list_jobs(
    _user: str = Depends(get_current_user),
):
    return {"jobs": batch_service.list_jobs()}


@router.get(
    "/process/{run_id}",
    summary="Estado de un job de procesamiento",
    description="Consulta el estado actual de un job: pending | running | completed | failed",
)
async def get_job_status(
    run_id: str,
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    # Primero buscar en el registro en memoria (job activo)
    job = batch_service.get_job_status(run_id)
    if job:
        return job

    # Si no está en memoria, buscar en los archivos de métricas (corridas anteriores)
    metrics = storage_service.get_run_metrics(run_id, settings)
    if metrics:
        return {
            "run_id": run_id,
            "status": "completed",
            "progress_pct": 100.0,
            "metrics": metrics,
        }

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Job '{run_id}' no encontrado",
    )


@router.post(
    "/process/aws",
    summary="Lanzar Glue Job en AWS (solo APP_MODE=aws)",
    description=(
        "Lanza el Glue Job de Spark en AWS Academy Learner Lab. "
        "Solo disponible cuando APP_MODE=aws. "
        "Requiere credenciales AWS válidas en las variables de entorno."
    ),
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_aws_glue_job(
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    if settings.is_local:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Este endpoint solo está disponible en APP_MODE=aws. "
                "Cambia APP_MODE=aws en tu .env y reinicia la API."
            ),
        )
    try:
        result = await batch_service.start_glue_job_aws(settings)
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
