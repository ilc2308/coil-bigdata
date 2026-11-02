"""
routers/audit.py
Endpoints de auditoría y trazabilidad.

POST /api/v1/audit/validate/{run_id}  — lanzar oráculo de validación sobre una corrida
GET  /api/v1/audit/runs               — historial de corridas con estado de auditoría
GET  /api/v1/audit/parse              — parsear una glosa de prueba
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from api.middleware.auth import get_current_user
from api.services.config import Settings, get_settings
from api.services import storage_service

router = APIRouter(prefix="/api/v1/audit", tags=["Auditoría"])


class GlosaParseRequest(BaseModel):
    glosa: str


@router.get(
    "/runs",
    summary="Historial de corridas con métricas de auditoría",
    description="Lista todas las corridas con sus indicadores de conciliación e integridad.",
)
async def get_audit_runs(
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    runs = storage_service.list_run_metrics(settings)

    audit_summary = []
    for run in runs:
        ci = run.get("conciliacion_integridad", {})
        audit_summary.append({
            "id_corrida": run.get("id_corrida"),
            "timestamp_fin": run.get("timestamp_fin"),
            "total_recibidas": run.get("total_recibidas"),
            "total_procesadas": run.get("total_procesadas"),
            "total_cuarentena": run.get("total_cuarentena"),
            "conciliacion_estado": ci.get("estado"),
            "diferencia": ci.get("diferencia"),
            "cumple_sla_24h": run.get("cumple_sla_24h"),
            "cumple_rendimiento_minimo": run.get("cumple_rendimiento_minimo"),
            "porcentaje_cubiertas": run.get("porcentaje_cubiertas"),
        })

    return {"total": len(audit_summary), "runs": audit_summary}


@router.post(
    "/validate/{run_id}",
    summary="Ejecutar oráculo de validación independiente",
    description=(
        "Lanza el oracle_validator sobre los resultados de una corrida específica. "
        "Compara cada decisión contra el cálculo independiente del oráculo. "
        "Solo funciona con sample_1000.csv o datasets pequeños para no bloquear la API. "
        "Para 1.2M usar el script directo: python -m src.oracle_validator"
    ),
)
async def run_oracle_validation(
    run_id: str,
    input_filename: str = Query(
        default="sample_1000.csv",
        description="Nombre del CSV original (en dataset/ o uploads/)",
    ),
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    import asyncio
    from pathlib import Path

    # Resolver ruta del CSV de entrada
    input_path = None
    for base in [Path(settings.base_dir) / "dataset", Path(settings.upload_dir)]:
        candidate = base / input_filename
        if candidate.exists():
            input_path = str(candidate)
            break

    if not input_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Archivo '{input_filename}' no encontrado en dataset/ ni uploads/",
        )

    gold_dir = storage_service._gold_dir(settings)
    if not Path(gold_dir).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe capa gold. Ejecuta un procesamiento primero.",
        )

    try:
        import sys
        import os
        project_root = str(Path(__file__).resolve().parent.parent.parent)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        from src.oracle_validator import run_oracle_validation as oracle_fn

        # Ejecutar en executor para no bloquear el event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            oracle_fn,
            input_path,
            settings.catalogo_servicios_path,
            settings.catalogo_perfiles_path,
            gold_dir,
        )
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en oráculo: {str(exc)}",
        )


@router.post(
    "/parse",
    summary="Parsear y validar una glosa de prueba",
    description="Envía una glosa médica y recibe el resultado del parser con todos sus campos extraídos.",
)
async def parse_glosa_test(
    body: GlosaParseRequest,
    _user: str = Depends(get_current_user),
):
    import sys
    import os
    from pathlib import Path

    project_root = str(Path(__file__).resolve().parent.parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from src.utils.glosa_parser import parse_glosa

    es_valido, datos, error = parse_glosa(body.glosa)

    if es_valido:
        # No devolver datos PII crudos — solo los hashes y campos no sensibles
        return {
            "es_valido": True,
            "perfil_cobertura": datos["perfil_cobertura"],
            "servicio_solicitado": datos["servicio_solicitado"],
            "edad": datos["edad"],
            "medicaciones": datos["medicaciones"],
            "dno_hash": datos["dno_hash"],
            "seguro_social_hash": datos["seguro_social_hash"],
            "paciente_hash": datos["paciente_hash"],
        }
    else:
        return {"es_valido": False, "error": error}
