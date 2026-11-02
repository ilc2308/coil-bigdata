"""
schemas/coverage.py
Modelos Pydantic para catálogos de cobertura y evaluación de reglas.
"""

from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field


class CatalogoServicio(BaseModel):
    """Servicio médico cubierto del catálogo."""
    codigo_servicio: str
    servicio: str
    categoria: str
    medicaciones_referencia: str
    valor_min_referencia: int
    valor_max_referencia: int
    cubre_sistema_publico: str


class CatalogoPerfil(BaseModel):
    """Perfil de cobertura con su porcentaje."""
    perfil_cobertura: str
    porcentaje_cobertura_si_el_servicio_esta_cubierto: int
    descripcion: str


class EvaluacionRequest(BaseModel):
    """Solicitud de evaluación manual de una orden."""
    servicio_solicitado: str
    perfil_cobertura: str
    valor_procedimiento: int = Field(gt=0)
    medicaciones: List[str] = Field(default_factory=list)


class EvaluacionResult(BaseModel):
    """Resultado de evaluación de una orden."""
    decision: str
    porcentaje_cobertura: int
    valor_reconocido: int
    codigo_servicio: str
    categoria_servicio: str
    regla_aplicada: str
    version_catalogo: str
    alertas: str


class CoverageStats(BaseModel):
    """Estadísticas de cobertura del último run disponible."""
    total_ordenes: int
    total_cubiertas: int
    total_no_cubiertas: int
    porcentaje_cubiertas: float
    valor_solicitado_total_cop: int
    valor_reconocido_total_cop: int
    distribucion_perfiles: dict
    distribucion_decisiones: dict
    top_servicios: List[dict]
    top_alertas: List[dict]
