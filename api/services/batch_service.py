"""
services/batch_service.py
Wrapper asíncrono del batch_processor para uso desde la API FastAPI.

El procesamiento de 1.2M de filas es CPU-bound y puede durar 2+ min.
Lo ejecutamos en un ThreadPoolExecutor para no bloquear el event loop de uvicorn.
El estado de cada job se guarda en memoria (job_registry) mientras la app esté activa.
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, Optional

from api.services.config import Settings, get_settings
from api.services.storage_service import get_upload_path

# ---------------------------------------------------------------------------
# Registro en memoria de jobs activos
# ---------------------------------------------------------------------------

_job_registry: Dict[str, Dict[str, Any]] = {}
_registry_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="coil-batch")


def _set_job(run_id: str, **kwargs):
    with _registry_lock:
        if run_id not in _job_registry:
            _job_registry[run_id] = {}
        _job_registry[run_id].update(kwargs)


def get_job_status(run_id: str) -> Optional[Dict[str, Any]]:
    """Retorna el estado actual del job, o None si no existe en el registro."""
    with _registry_lock:
        return dict(_job_registry[run_id]) if run_id in _job_registry else None


def list_jobs() -> list:
    """Lista todos los jobs del registro (activos + históricos de la sesión)."""
    with _registry_lock:
        return [dict(v) for v in _job_registry.values()]


# ---------------------------------------------------------------------------
# Ejecución del batch en hilo separado
# ---------------------------------------------------------------------------

def _run_batch_thread(
    run_id: str,
    input_csv_path: str,
    catalogo_servicios_path: str,
    catalogo_perfiles_path: str,
    output_dir: str,
    chunk_size: int,
    write_parquet: bool,
):
    """Función que corre en el hilo del executor."""
    # Importación aquí para evitar dependencia circular
    import sys
    import os
    # Asegurarnos de que src/ está en el path
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from src.batch_processor import process_batch

    _set_job(run_id, status="running", progress_pct=0.0, started_at=datetime.now().isoformat())

    # Callback de progreso para actualizar el registro en tiempo real
    # Estimamos el porcentaje según el tamaño del archivo (heurística: ~290 bytes/fila en el 1.2M)
    import os as _os
    try:
        file_size = _os.path.getsize(input_csv_path)
        estimated_total = max(file_size // 290, 1)
    except Exception:
        estimated_total = 1_200_000  # fallback para dataset estándar

    def progress_callback(processed: int, total_so_far: int, elapsed: float):
        pct = min(99.0, round(total_so_far / estimated_total * 100, 1))
        _set_job(run_id, progress_pct=pct)

    try:
        metrics = process_batch(
            input_csv_path=input_csv_path,
            catalogo_servicios_path=catalogo_servicios_path,
            catalogo_perfiles_path=catalogo_perfiles_path,
            output_dir=output_dir,
            run_id=run_id,
            chunk_size=chunk_size,
            write_parquet=write_parquet,
            progress_callback=progress_callback,
        )
        _set_job(
            run_id,
            status="completed",
            progress_pct=100.0,
            completed_at=datetime.now().isoformat(),
            metrics=metrics,
        )
    except Exception as exc:
        _set_job(
            run_id,
            status="failed",
            progress_pct=0.0,
            error=str(exc),
            completed_at=datetime.now().isoformat(),
        )


# ---------------------------------------------------------------------------
# API pública del servicio
# ---------------------------------------------------------------------------

async def start_batch_job(
    filename: str,
    run_id: Optional[str] = None,
    chunk_size: int = 100000,
    write_parquet: bool = True,
    settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    """
    Lanza el batch en un hilo del executor.
    Retorna inmediatamente con el run_id y status=pending.

    Args:
        filename:      Nombre del archivo CSV ya guardado en uploads/.
        run_id:        ID de corrida personalizado (se genera si es None).
        chunk_size:    Tamaño del chunk para progreso.
        write_parquet: Escribir Parquet nativo (True) o CSV (False).
        settings:      Configuración de la app.

    Returns:
        Diccionario con run_id y status inicial.
    """
    if settings is None:
        settings = get_settings()

    if not run_id:
        run_id = f"RUN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

    # Verificar que el archivo existe en uploads
    input_path = get_upload_path(filename, settings)
    if input_path is None:
        # Intentar en dataset/ (archivos pre-existentes)
        from pathlib import Path
        alt_path = Path(settings.base_dir) / "dataset" / filename
        if alt_path.exists():
            input_path = str(alt_path)
        else:
            raise FileNotFoundError(f"Archivo no encontrado: {filename}")

    _set_job(run_id, run_id=run_id, status="pending", filename=filename, started_at=datetime.now().isoformat())

    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        _executor,
        _run_batch_thread,
        run_id,
        input_path,
        settings.catalogo_servicios_path,
        settings.catalogo_perfiles_path,
        settings.output_dir,
        chunk_size,
        write_parquet,
    )

    return {"run_id": run_id, "status": "pending", "filename": filename}


async def start_glue_job_aws(settings: Optional[Settings] = None) -> Dict[str, Any]:
    """Lanza el Glue Job en AWS (solo APP_MODE=aws)."""
    if settings is None:
        settings = get_settings()

    if settings.is_local:
        raise RuntimeError("start_glue_job_aws solo disponible en APP_MODE=aws")

    from api.services.storage_service import start_glue_job
    job_run_id = start_glue_job(settings)
    return {"job_run_id": job_run_id, "status": "STARTING"}
