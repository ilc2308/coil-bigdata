"""
routers/reports.py
Endpoints de exportación de reportes.

GET /api/v1/reports/gold/csv          — órdenes gold → CSV
GET /api/v1/reports/gold/excel        — reporte completo → Excel (múltiples hojas)
GET /api/v1/reports/quarantine/csv    — cuarentena → CSV
GET /api/v1/reports/metrics/csv       — historial de corridas → CSV
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from api.middleware.auth import get_current_user
from api.services import report_service
from api.services.config import Settings, get_settings

router = APIRouter(prefix="/api/v1/reports", tags=["Reportes"])


@router.get(
    "/gold/csv",
    summary="Exportar órdenes gold a CSV",
    description=(
        "Descarga los registros de la capa gold como CSV. "
        "Soporta filtros. Máximo 100,000 filas por descarga."
    ),
    response_class=Response,
)
async def export_gold_csv(
    decision: Optional[str] = Query(default=None),
    perfil_cobertura: Optional[str] = Query(default=None),
    fecha_desde: Optional[str] = Query(default=None),
    fecha_hasta: Optional[str] = Query(default=None),
    entidad_emisora: Optional[str] = Query(default=None),
    codigo_servicio: Optional[str] = Query(default=None),
    run_id: Optional[str] = Query(default=None),
    max_rows: int = Query(default=100000, ge=1, le=500000),
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    filters = {k: v for k, v in {
        "decision": decision,
        "perfil_cobertura": perfil_cobertura,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "entidad_emisora": entidad_emisora,
        "codigo_servicio": codigo_servicio,
        "run_id": run_id,
    }.items() if v is not None}

    try:
        csv_bytes = report_service.export_gold_csv(filters=filters, max_rows=max_rows, settings=settings)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=coil_ordenes_gold.csv"},
    )


@router.get(
    "/gold/excel",
    summary="Exportar reporte ejecutivo a Excel",
    description=(
        "Genera un archivo .xlsx con 4 hojas: "
        "Resumen Ejecutivo, Órdenes Cubiertas, Órdenes No Cubiertas, "
        "Cuarentena e Historial de Corridas."
    ),
    response_class=Response,
)
async def export_gold_excel(
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    try:
        excel_bytes = report_service.export_gold_excel(settings=settings)
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=coil_reporte_ejecutivo.xlsx"},
    )


@router.get(
    "/quarantine/csv",
    summary="Exportar cuarentena a CSV",
    response_class=Response,
)
async def export_quarantine_csv(
    run_id: Optional[str] = Query(default=None),
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    try:
        csv_bytes = report_service.export_quarantine_csv(run_id=run_id, settings=settings)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=coil_cuarentena.csv"},
    )


@router.get(
    "/metrics/csv",
    summary="Exportar historial de corridas a CSV",
    response_class=Response,
)
async def export_metrics_csv(
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    try:
        csv_bytes = report_service.export_metrics_csv(settings=settings)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=coil_metricas_corridas.csv"},
    )
