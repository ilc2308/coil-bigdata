"""
routers/results.py
Endpoints de consulta de resultados (capa gold) con paginación.

GET /api/v1/results          — órdenes procesadas, paginadas y filtradas
GET /api/v1/results/summary  — estadísticas agregadas del dataset completo
GET /api/v1/metrics          — historial de métricas de corridas
GET /api/v1/metrics/{run_id} — métricas de una corrida específica
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.middleware.auth import get_current_user
from api.schemas.order import PaginatedOrders
from api.services import storage_service
from api.services.config import Settings, get_settings

router = APIRouter(prefix="/api/v1", tags=["Resultados"])


@router.get(
    "/results",
    summary="Consultar órdenes procesadas (paginado)",
    description=(
        "Retorna registros de la capa gold con paginación y filtros opcionales. "
        "Máximo 2000 filas por página para proteger el rendimiento."
    ),
)
async def get_results(
    page: int = Query(default=1, ge=1, description="Número de página (1-based)"),
    page_size: int = Query(default=100, ge=1, le=2000, description="Filas por página"),
    decision: Optional[str] = Query(default=None, description="CUBRE | NO CUBRE"),
    perfil_cobertura: Optional[str] = Query(default=None, description="PRIORITARIO | ESTANDAR | COPAGO"),
    fecha_desde: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    fecha_hasta: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    entidad_emisora: Optional[str] = Query(default=None),
    medio_emisor: Optional[str] = Query(default=None),
    codigo_servicio: Optional[str] = Query(default=None, description="COV-001, NON-COVERED, etc."),
    alertas: Optional[str] = Query(default=None, description="NINGUNA | VALOR_SOBRE_RANGO | etc."),
    run_id: Optional[str] = Query(default=None, description="Filtrar por ID de corrida"),
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    filters = {
        "decision": decision,
        "perfil_cobertura": perfil_cobertura,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "entidad_emisora": entidad_emisora,
        "medio_emisor": medio_emisor,
        "codigo_servicio": codigo_servicio,
        "alertas": alertas,
        "run_id": run_id,
    }
    # Limpiar filtros vacíos
    filters = {k: v for k, v in filters.items() if v is not None}

    rows, total = storage_service.read_gold_paginated(
        page=page,
        page_size=page_size,
        filters=filters,
        settings=settings,
    )

    import math
    total_pages = math.ceil(total / page_size) if page_size > 0 else 1

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "data": rows,
    }


@router.get(
    "/results/summary",
    summary="Estadísticas agregadas del dataset gold",
    description=(
        "Calcula KPIs del dataset completo sin cargar todos los datos en memoria. "
        "Incluye distribución de decisiones, perfiles, top servicios y alertas."
    ),
)
async def get_results_summary(
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    stats = storage_service.compute_gold_stats(settings)
    return stats


@router.get(
    "/metrics",
    summary="Historial de métricas de corridas",
    description="Lista todas las corridas ejecutadas con sus métricas de rendimiento.",
)
async def get_all_metrics(
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    metrics = storage_service.list_run_metrics(settings)
    return {"total": len(metrics), "runs": metrics}


@router.get(
    "/metrics/{run_id}",
    summary="Métricas de una corrida específica",
)
async def get_metrics_by_run(
    run_id: str,
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    metrics = storage_service.get_run_metrics(run_id, settings)
    if not metrics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Métricas para corrida '{run_id}' no encontradas",
        )
    return metrics
