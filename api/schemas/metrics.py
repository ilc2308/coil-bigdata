"""
schemas/metrics.py
Modelos Pydantic para métricas de corridas y respuestas de procesamiento.
"""

from __future__ import annotations
from typing import Optional, Dict
from pydantic import BaseModel, Field


class ConciliacionIntegridad(BaseModel):
    recibidas: int
    procesadas_mas_cuarentena: int
    diferencia: int
    estado: str


class RunMetrics(BaseModel):
    """Métricas completas de una corrida de procesamiento."""
    id_corrida: str
    timestamp_fin: str
    duracion_segundos: float
    rendimiento_ordenes_por_segundo: float

    total_recibidas: int
    total_procesadas: int
    total_cubiertas: int
    total_no_cubiertas: int
    total_cuarentena: int
    porcentaje_cubiertas: float

    valor_solicitado_total_cop: int
    valor_reconocido_total_cop: int

    perfiles_distribucion: Dict[str, int]
    conciliacion_integridad: ConciliacionIntegridad

    estimacion_costo_aws_usd: float
    cumple_sla_24h: bool
    cumple_rendimiento_minimo: bool

    formato_salida: Optional[str] = Field(default="csv", description="'parquet' o 'csv'")


class ProcessJobStatus(BaseModel):
    """Estado de un job de procesamiento en curso o completado."""
    run_id: str
    status: str = Field(description="pending | running | completed | failed")
    progress_pct: float = Field(default=0.0, ge=0, le=100)
    message: Optional[str] = None
    metrics: Optional[RunMetrics] = None


class ProcessStartRequest(BaseModel):
    """Solicitud para iniciar un nuevo procesamiento por lotes."""
    filename: str = Field(description="Nombre del archivo CSV ya subido vía /upload")
    run_id: Optional[str] = Field(default=None, description="ID personalizado; se genera automáticamente si es None")
    chunk_size: int = Field(default=100000, ge=1000, le=500000)
    write_parquet: bool = Field(default=True)
