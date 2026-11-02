"""
routers/quarantine.py
Endpoints de gestión de cuarentena.

GET /api/v1/quarantine           — registros rechazados, paginados
GET /api/v1/quarantine/summary   — conteo por run y motivo de rechazo
"""

from __future__ import annotations

import math
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.middleware.auth import get_current_user
from api.services import storage_service
from api.services.config import Settings, get_settings

router = APIRouter(prefix="/api/v1/quarantine", tags=["Cuarentena"])


@router.get(
    "",
    summary="Registros en cuarentena (paginado)",
    description="Retorna registros que fallaron validación o parseo, con paginación.",
)
async def get_quarantine(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=2000),
    run_id: Optional[str] = Query(default=None, description="Filtrar por ID de corrida"),
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    rows, total = storage_service.read_quarantine_paginated(
        page=page,
        page_size=page_size,
        run_id=run_id,
        settings=settings,
    )

    total_pages = math.ceil(total / page_size) if page_size > 0 else 1

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "data": rows,
    }


@router.get(
    "/summary",
    summary="Resumen de cuarentena por corrida y motivo",
)
async def quarantine_summary(
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    # Leer todos los registros de cuarentena para agregar
    rows, total = storage_service.read_quarantine_paginated(
        page=1,
        page_size=50000,
        settings=settings,
    )

    if not rows:
        return {"total": 0, "por_run": {}, "por_motivo": {}}

    por_run: dict = {}
    por_motivo: dict = {}

    for row in rows:
        run = row.get("id_corrida", "desconocido")
        motivo = row.get("motivo_rechazo", "desconocido")
        por_run[run] = por_run.get(run, 0) + 1
        por_motivo[motivo] = por_motivo.get(motivo, 0) + 1

    return {
        "total": total,
        "por_run": por_run,
        "por_motivo": sorted(
            [{"motivo": k, "total": v} for k, v in por_motivo.items()],
            key=lambda x: x["total"],
            reverse=True,
        ),
    }
