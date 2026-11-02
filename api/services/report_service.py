"""
services/report_service.py
Generador de reportes exportables en CSV y Excel.
Lee los datos de la capa gold de forma paginada para no saturar memoria.
"""

from __future__ import annotations

import csv
import glob
import io
import os
from typing import Any, Dict, List, Optional

from api.services.config import Settings, get_settings
from api.services.storage_service import (
    _gold_dir,
    _quarantine_dir,
    read_gold_paginated,
    read_quarantine_paginated,
    list_run_metrics,
)

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    _EXCEL_AVAILABLE = True
except ImportError:
    _EXCEL_AVAILABLE = False


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def export_gold_csv(
    filters: Optional[Dict[str, Any]] = None,
    max_rows: int = 100_000,
    settings: Optional[Settings] = None,
) -> bytes:
    """
    Exporta registros gold a CSV en memoria.
    Respeta filtros y limita a max_rows para evitar timeouts.
    """
    if settings is None:
        settings = get_settings()

    output = io.StringIO()
    writer = None
    total_written = 0
    page = 1

    while total_written < max_rows:
        rows, total = read_gold_paginated(
            page=page,
            page_size=min(5000, max_rows - total_written),
            filters=filters or {},
            settings=settings,
        )
        if not rows:
            break

        if writer is None:
            writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
            writer.writeheader()

        writer.writerows(rows)
        total_written += len(rows)
        page += 1

        if len(rows) < 5000:
            break

    return output.getvalue().encode("utf-8")


def export_quarantine_csv(
    run_id: Optional[str] = None,
    settings: Optional[Settings] = None,
) -> bytes:
    """Exporta registros de cuarentena a CSV en memoria."""
    if settings is None:
        settings = get_settings()

    rows, _ = read_quarantine_paginated(page=1, page_size=50000, run_id=run_id, settings=settings)

    if not rows:
        return b"id_solicitud,fecha_solicitud,motivo_rechazo\n"

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def export_metrics_csv(settings: Optional[Settings] = None) -> bytes:
    """Exporta el historial de métricas de corridas a CSV."""
    if settings is None:
        settings = get_settings()

    metrics_list = list_run_metrics(settings)
    if not metrics_list:
        return b"id_corrida,total_recibidas,total_procesadas,total_cubiertas,total_cuarentena\n"

    # Aplanar el JSON anidado a columnas planas
    flat_rows = []
    for m in metrics_list:
        row = {
            "id_corrida": m.get("id_corrida", ""),
            "timestamp_fin": m.get("timestamp_fin", ""),
            "duracion_segundos": m.get("duracion_segundos", ""),
            "rendimiento_ordenes_por_segundo": m.get("rendimiento_ordenes_por_segundo", ""),
            "total_recibidas": m.get("total_recibidas", ""),
            "total_procesadas": m.get("total_procesadas", ""),
            "total_cubiertas": m.get("total_cubiertas", ""),
            "total_no_cubiertas": m.get("total_no_cubiertas", ""),
            "total_cuarentena": m.get("total_cuarentena", ""),
            "porcentaje_cubiertas": m.get("porcentaje_cubiertas", ""),
            "valor_solicitado_total_cop": m.get("valor_solicitado_total_cop", ""),
            "valor_reconocido_total_cop": m.get("valor_reconocido_total_cop", ""),
            "conciliacion_estado": m.get("conciliacion_integridad", {}).get("estado", ""),
            "estimacion_costo_aws_usd": m.get("estimacion_costo_aws_usd", ""),
            "cumple_sla_24h": m.get("cumple_sla_24h", ""),
            "cumple_rendimiento_minimo": m.get("cumple_rendimiento_minimo", ""),
        }
        # Agregar distribución de perfiles
        for perfil, count in m.get("perfiles_distribucion", {}).items():
            row[f"perfil_{perfil.lower()}"] = count
        flat_rows.append(row)

    output = io.StringIO()
    if flat_rows:
        writer = csv.DictWriter(output, fieldnames=list(flat_rows[0].keys()))
        writer.writeheader()
        writer.writerows(flat_rows)

    return output.getvalue().encode("utf-8")


# ---------------------------------------------------------------------------
# Excel (requiere openpyxl)
# ---------------------------------------------------------------------------

def _style_header_row(ws, header_fill_hex: str = "1F4E79"):
    """Aplica estilos a la fila de encabezado de una hoja Excel."""
    fill = PatternFill(start_color=header_fill_hex, end_color=header_fill_hex, fill_type="solid")
    font = Font(color="FFFFFF", bold=True)
    align = Alignment(horizontal="center", vertical="center")

    for cell in ws[1]:
        cell.fill = fill
        cell.font = font
        cell.alignment = align

    # Autoajustar ancho de columnas (máx 50)
    for col_idx, col in enumerate(ws.columns, 1):
        max_len = max((len(str(c.value or "")) for c in col), default=10)
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 2, 50)


def export_gold_excel(
    filters: Optional[Dict[str, Any]] = None,
    max_rows: int = 50_000,
    settings: Optional[Settings] = None,
) -> bytes:
    """
    Exporta un reporte Excel con múltiples hojas:
    - Resumen ejecutivo
    - Órdenes Cubiertas (hasta max_rows/2)
    - Órdenes No Cubiertas (hasta max_rows/2)
    - Cuarentena
    - Métricas de Corridas
    """
    if not _EXCEL_AVAILABLE:
        raise RuntimeError("openpyxl no está instalado. Instala con: pip install openpyxl")

    if settings is None:
        settings = get_settings()

    wb = openpyxl.Workbook()

    # ---- Hoja 1: Resumen ejecutivo ----
    from api.services.storage_service import compute_gold_stats, get_latest_metrics

    ws_resumen = wb.active
    ws_resumen.title = "Resumen Ejecutivo"

    stats = compute_gold_stats(settings)
    latest = get_latest_metrics(settings) or {}

    summary_rows = [
        ["COIL — Reporte Ejecutivo de Cobertura Médica", ""],
        ["Sistema de Salud de Chernovia", ""],
        ["", ""],
        ["MÉTRICA", "VALOR"],
        ["Total Órdenes Procesadas", stats.get("total_ordenes", 0)],
        ["Total Cubiertas", stats.get("total_cubiertas", 0)],
        ["Total No Cubiertas", stats.get("total_no_cubiertas", 0)],
        ["% Cobertura", f"{stats.get('porcentaje_cubiertas', 0):.2f}%"],
        ["Valor Solicitado Total (COP)", f"${stats.get('valor_solicitado_total_cop', 0):,}"],
        ["Valor Reconocido Total (COP)", f"${stats.get('valor_reconocido_total_cop', 0):,}"],
        ["", ""],
        ["Última Corrida ID", latest.get("id_corrida", "N/A")],
        ["Duración (s)", latest.get("duracion_segundos", "N/A")],
        ["Rendimiento (órd/s)", latest.get("rendimiento_ordenes_por_segundo", "N/A")],
        ["Conciliación", latest.get("conciliacion_integridad", {}).get("estado", "N/A")],
        ["Cumple SLA 24h", latest.get("cumple_sla_24h", "N/A")],
    ]

    for row_data in summary_rows:
        ws_resumen.append(row_data)

    ws_resumen["A1"].font = Font(size=14, bold=True, color="1F4E79")
    ws_resumen["A4"].font = Font(bold=True)
    ws_resumen["B4"].font = Font(bold=True)
    ws_resumen.column_dimensions["A"].width = 40
    ws_resumen.column_dimensions["B"].width = 30

    # ---- Hoja 2: Órdenes (filtradas) ----
    def _add_orders_sheet(wb, title: str, decision_filter: Optional[str], max_r: int):
        ws = wb.create_sheet(title=title)
        f = dict(filters or {})
        if decision_filter:
            f["decision"] = decision_filter

        rows, total = read_gold_paginated(page=1, page_size=min(max_r, 2000), filters=f, settings=settings)
        if not rows:
            ws.append(["Sin datos disponibles"])
            return

        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([row.get(h, "") for h in headers])

        _style_header_row(ws)
        ws.freeze_panes = "A2"

        # Si hay más de 2000 filas, agregar nota
        if total > len(rows):
            ws.append([f"... y {total - len(rows):,} registros más. Usa la exportación CSV para el dataset completo."])

    _add_orders_sheet(wb, "Órdenes Cubiertas", "CUBRE", max_rows // 2)
    _add_orders_sheet(wb, "Órdenes No Cubiertas", "NO CUBRE", max_rows // 2)

    # ---- Hoja 3: Cuarentena ----
    ws_q = wb.create_sheet(title="Cuarentena")
    q_rows, _ = read_quarantine_paginated(page=1, page_size=5000, settings=settings)
    if q_rows:
        q_headers = list(q_rows[0].keys())
        ws_q.append(q_headers)
        for row in q_rows:
            ws_q.append([row.get(h, "") for h in q_headers])
        _style_header_row(ws_q, header_fill_hex="C0392B")
        ws_q.freeze_panes = "A2"
    else:
        ws_q.append(["Sin registros en cuarentena"])

    # ---- Hoja 4: Métricas de Corridas ----
    ws_m = wb.create_sheet(title="Historial Corridas")
    metrics_list = list_run_metrics(settings)
    if metrics_list:
        m_headers = [
            "id_corrida", "timestamp_fin", "duracion_segundos", "rendimiento_ordenes_por_segundo",
            "total_recibidas", "total_procesadas", "total_cubiertas", "total_no_cubiertas",
            "total_cuarentena", "porcentaje_cubiertas", "valor_solicitado_total_cop",
            "valor_reconocido_total_cop", "conciliacion_estado", "estimacion_costo_aws_usd",
            "cumple_sla_24h",
        ]
        ws_m.append(m_headers)
        for m in metrics_list:
            ws_m.append([
                m.get("id_corrida", ""),
                m.get("timestamp_fin", ""),
                m.get("duracion_segundos", ""),
                m.get("rendimiento_ordenes_por_segundo", ""),
                m.get("total_recibidas", ""),
                m.get("total_procesadas", ""),
                m.get("total_cubiertas", ""),
                m.get("total_no_cubiertas", ""),
                m.get("total_cuarentena", ""),
                m.get("porcentaje_cubiertas", ""),
                m.get("valor_solicitado_total_cop", ""),
                m.get("valor_reconocido_total_cop", ""),
                m.get("conciliacion_integridad", {}).get("estado", ""),
                m.get("estimacion_costo_aws_usd", ""),
                m.get("cumple_sla_24h", ""),
            ])
        _style_header_row(ws_m, header_fill_hex="1A5276")
        ws_m.freeze_panes = "A2"

    # Serializar a bytes
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()
