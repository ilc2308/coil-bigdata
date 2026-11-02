"""
routers/coverage.py
Endpoints de catálogos y evaluación de reglas de cobertura.

GET  /api/v1/coverage/servicios     — catálogo de servicios cubiertos
GET  /api/v1/coverage/perfiles      — catálogo de perfiles de cobertura
POST /api/v1/coverage/evaluate      — evaluar una orden médica puntual
GET  /api/v1/coverage/stats         — estadísticas de cobertura del dataset
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from api.middleware.auth import get_current_user
from api.schemas.coverage import (
    CatalogoPerfil,
    CatalogoServicio,
    CoverageStats,
    EvaluacionRequest,
    EvaluacionResult,
)
from api.services import storage_service
from api.services.config import Settings, get_settings

router = APIRouter(prefix="/api/v1/coverage", tags=["Cobertura"])


@router.get(
    "/servicios",
    summary="Catálogo de servicios cubiertos",
    description="Lista los 20 servicios médicos cubiertos con códigos, categorías y rangos de valor.",
)
async def get_servicios(
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    try:
        servicios = storage_service.read_catalogo_servicios(settings)
        return {"total": len(servicios), "servicios": servicios}
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/perfiles",
    summary="Catálogo de perfiles de cobertura",
    description="Lista los 3 perfiles (PRIORITARIO 100%, ESTANDAR 50%, COPAGO 25%).",
)
async def get_perfiles(
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    try:
        perfiles = storage_service.read_catalogo_perfiles(settings)
        return {"total": len(perfiles), "perfiles": perfiles}
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/evaluate",
    response_model=EvaluacionResult,
    summary="Evaluar una orden médica puntual",
    description=(
        "Aplica las reglas de cobertura a una orden individual sin procesamiento por lotes. "
        "Útil para pruebas y auditorías puntuales."
    ),
)
async def evaluate_order(
    request: EvaluacionRequest,
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    try:
        from src.utils.rule_engine import CoverageRuleEngine
        engine = CoverageRuleEngine(
            settings.catalogo_servicios_path,
            settings.catalogo_perfiles_path,
            settings.version_catalogo,
        )
        result = engine.evaluate_order(
            servicio_solicitado=request.servicio_solicitado,
            perfil_cobertura=request.perfil_cobertura,
            valor_procedimiento=request.valor_procedimiento,
            medicaciones=request.medicaciones,
        )
        return EvaluacionResult(**result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/stats",
    summary="Estadísticas de cobertura del dataset completo",
    description="KPIs de cobertura calculados sobre la capa gold sin cargar el dataset completo.",
)
async def get_coverage_stats(
    _user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    stats = storage_service.compute_gold_stats(settings)
    return stats
