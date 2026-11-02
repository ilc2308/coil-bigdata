"""
schemas/order.py
Modelos Pydantic para órdenes médicas procesadas y cuarentena.
"""

from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field


class GoldOrder(BaseModel):
    """Registro procesado en la capa gold."""
    id_solicitud: str
    fecha_solicitud: str
    fecha_particion: str
    medio_emisor: str
    entidad_emisora: str
    edad: int
    perfil_cobertura: str
    servicio_solicitado: str
    codigo_servicio: str
    categoria_servicio: str
    medicaciones: str
    decision: str
    porcentaje_cobertura: int
    valor_procedimiento: int
    valor_reconocido: int
    regla_aplicada: str
    version_catalogo: str
    alertas: str
    dno_hash: str
    seguro_social_hash: str
    paciente_hash: str
    id_corrida: str
    timestamp_procesamiento: str


class QuarantineRecord(BaseModel):
    """Registro rechazado en cuarentena."""
    id_solicitud: str
    fecha_solicitud: str
    glosa_raw: str
    medio_emisor: str
    valor_procedimiento: str
    entidad_emisora: str
    motivo_rechazo: str
    id_corrida: str
    timestamp_rechazo: str


class PaginatedOrders(BaseModel):
    """Respuesta paginada de órdenes gold."""
    total: int
    page: int
    page_size: int
    total_pages: int
    data: List[GoldOrder]


class PaginatedQuarantine(BaseModel):
    """Respuesta paginada de cuarentena."""
    total: int
    page: int
    page_size: int
    total_pages: int
    data: List[QuarantineRecord]


class OrderFilters(BaseModel):
    """Filtros para consulta de órdenes."""
    decision: Optional[str] = Field(default=None, description="CUBRE | NO CUBRE")
    perfil_cobertura: Optional[str] = Field(default=None, description="PRIORITARIO | ESTANDAR | COPAGO")
    fecha_desde: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    fecha_hasta: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    entidad_emisora: Optional[str] = None
    medio_emisor: Optional[str] = None
    codigo_servicio: Optional[str] = None
    alertas: Optional[str] = None
    run_id: Optional[str] = None
