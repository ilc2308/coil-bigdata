"""
components/charts.py
Gráficos Plotly reutilizables para el dashboard COIL.
Todos los datos llegan ya agregados desde la API (no se carga el dataset completo aquí).
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

# Paleta corporativa COIL
COLORS = {
    "primary":   "#1F4E79",
    "secondary": "#2E86AB",
    "cubre":     "#27AE60",
    "no_cubre":  "#E74C3C",
    "cuarentena":"#F39C12",
    "prioritario":"#8E44AD",
    "estandar":  "#2980B9",
    "copago":    "#16A085",
    "gray":      "#7F8C8D",
    "light":     "#ECF0F1",
}

PERFIL_COLORS = {
    "PRIORITARIO": COLORS["prioritario"],
    "ESTANDAR":    COLORS["estandar"],
    "COPAGO":      COLORS["copago"],
}

DECISION_COLORS = {
    "CUBRE":    COLORS["cubre"],
    "NO CUBRE": COLORS["no_cubre"],
}


def _base_layout(title: str = "") -> dict:
    return dict(
        title=dict(text=title, font=dict(size=14, color=COLORS["primary"])),
        paper_bgcolor="white",
        plot_bgcolor="#FAFAFA",
        font=dict(family="Inter, sans-serif", size=12),
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
    )


# ---------------------------------------------------------------------------
# KPI card (pseudo-gráfico — retorna figura con número grande)
# ---------------------------------------------------------------------------

def kpi_card(value: Any, label: str, delta: str = "", color: str = "#1F4E79") -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="number+delta" if delta else "number",
        value=float(str(value).replace(",", "").replace("$", "").replace("%", "")) if value else 0,
        number={"font": {"size": 42, "color": color}, "valueformat": ","},
        delta={"reference": 0, "valueformat": ".2f"} if delta else None,
        title={"text": f"<b>{label}</b>", "font": {"size": 13, "color": COLORS["gray"]}},
        domain={"x": [0, 1], "y": [0, 1]},
    ))
    fig.update_layout(height=130, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="white")
    return fig


# ---------------------------------------------------------------------------
# Donut: distribución de decisiones (CUBRE / NO CUBRE)
# ---------------------------------------------------------------------------

def decision_donut(distribucion: Dict[str, int], title: str = "Distribución de Decisiones") -> go.Figure:
    labels = list(distribucion.keys())
    values = list(distribucion.values())
    colors = [DECISION_COLORS.get(l, COLORS["gray"]) for l in labels]

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.55,
        marker=dict(colors=colors, line=dict(color="white", width=2)),
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>%{value:,} órdenes (%{percent})<extra></extra>",
    ))
    fig.update_layout(
        **_base_layout(title),
        height=300,
        annotations=[dict(
            text=f"<b>{sum(values):,}</b><br>total",
            x=0.5, y=0.5,
            font_size=13,
            showarrow=False,
        )],
    )
    return fig


# ---------------------------------------------------------------------------
# Barras apiladas: distribución por perfil de cobertura
# ---------------------------------------------------------------------------

def perfiles_bar(distribucion: Dict[str, int], title: str = "Órdenes por Perfil") -> go.Figure:
    perfiles = list(distribucion.keys())
    valores = list(distribucion.values())
    colors = [PERFIL_COLORS.get(p, COLORS["gray"]) for p in perfiles]

    fig = go.Figure(go.Bar(
        x=perfiles,
        y=valores,
        marker_color=colors,
        text=[f"{v:,}" for v in valores],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>%{y:,} órdenes<extra></extra>",
    ))
    fig.update_layout(
        **_base_layout(title),
        height=280,
        xaxis=dict(title="", tickfont=dict(size=11)),
        yaxis=dict(title="Órdenes", gridcolor="#EEE"),
        showlegend=False,
    )
    return fig


# ---------------------------------------------------------------------------
# Barras horizontales: top servicios
# ---------------------------------------------------------------------------

def top_servicios_bar(servicios: List[Dict], title: str = "Top 10 Servicios") -> go.Figure:
    if not servicios:
        return go.Figure().update_layout(**_base_layout(title), height=300)

    df = pd.DataFrame(servicios).head(10)
    df = df.sort_values("total", ascending=True)

    fig = go.Figure(go.Bar(
        x=df["total"],
        y=df.get("nombre", df.get("codigo", df.index)),
        orientation="h",
        marker_color=COLORS["secondary"],
        text=[f"{v:,}" for v in df["total"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>%{x:,} órdenes<extra></extra>",
    ))
    fig.update_layout(
        **_base_layout(title),
        height=max(280, len(df) * 30 + 60),
        xaxis=dict(title="Total Órdenes", gridcolor="#EEE"),
        yaxis=dict(title=""),
        showlegend=False,
    )
    return fig


# ---------------------------------------------------------------------------
# Valor solicitado vs reconocido (barras agrupadas por perfil)
# ---------------------------------------------------------------------------

def valor_cobertura_bar(
    stats: Dict,
    title: str = "Valor Solicitado vs Reconocido (COP)",
) -> go.Figure:
    solicitado = stats.get("valor_solicitado_total_cop", 0)
    reconocido  = stats.get("valor_reconocido_total_cop", 0)
    brecha = solicitado - reconocido

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Solicitado",
        x=["Total"],
        y=[solicitado],
        marker_color=COLORS["estandar"],
        text=[f"${solicitado/1e6:.1f}M"],
        textposition="outside",
    ))
    fig.add_trace(go.Bar(
        name="Reconocido",
        x=["Total"],
        y=[reconocido],
        marker_color=COLORS["cubre"],
        text=[f"${reconocido/1e6:.1f}M"],
        textposition="outside",
    ))
    fig.add_trace(go.Bar(
        name="Brecha",
        x=["Total"],
        y=[brecha],
        marker_color=COLORS["no_cubre"],
        text=[f"${brecha/1e6:.1f}M"],
        textposition="outside",
    ))

    fig.update_layout(
        **_base_layout(title),
        height=300,
        barmode="group",
        yaxis=dict(title="COP", tickformat="$,.0f", gridcolor="#EEE"),
    )
    return fig


# ---------------------------------------------------------------------------
# Línea temporal de corridas (rendimiento en el tiempo)
# ---------------------------------------------------------------------------

def runs_timeline(runs: List[Dict], title: str = "Rendimiento por Corrida") -> go.Figure:
    if not runs:
        return go.Figure().update_layout(**_base_layout(title), height=250)

    df = pd.DataFrame(runs)[["id_corrida", "duracion_segundos", "total_recibidas",
                               "rendimiento_ordenes_por_segundo", "timestamp_fin"]].copy()
    df = df.sort_values("timestamp_fin")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["timestamp_fin"],
        y=df["rendimiento_ordenes_por_segundo"],
        mode="lines+markers",
        name="órd/s",
        line=dict(color=COLORS["secondary"], width=2),
        marker=dict(size=8),
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Rendimiento: %{y:,.0f} órd/s<br>"
            "<extra></extra>"
        ),
    ))
    fig.add_hline(y=139, line_dash="dash", line_color=COLORS["cuarentena"],
                  annotation_text="SLA mínimo (139 órd/s)")
    fig.update_layout(
        **_base_layout(title),
        height=260,
        xaxis=dict(title=""),
        yaxis=dict(title="Órdenes/segundo", gridcolor="#EEE"),
    )
    return fig


# ---------------------------------------------------------------------------
# Gauge de conciliación (integridad contable)
# ---------------------------------------------------------------------------

def conciliacion_gauge(estado: str, diferencia: int = 0) -> go.Figure:
    ok = estado == "CUADRADA_PERFECTA"
    color = COLORS["cubre"] if ok else COLORS["no_cubre"]
    label = "✅ CUADRADA" if ok else f"⚠️ DESCUADRE ({diferencia:+,})"

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=0 if ok else abs(diferencia),
        title={"text": f"<b>Conciliación</b><br><span style='font-size:0.9em'>{label}</span>"},
        gauge={
            "axis": {"range": [0, max(abs(diferencia) * 2, 10)]},
            "bar": {"color": color},
            "bgcolor": "white",
            "steps": [{"range": [0, 0], "color": COLORS["cubre"]}],
        },
        number={"font": {"color": color}},
    ))
    fig.update_layout(height=200, margin=dict(l=20, r=20, t=50, b=10), paper_bgcolor="white")
    return fig


# ---------------------------------------------------------------------------
# Tabla de alertas (barras horizontales)
# ---------------------------------------------------------------------------

def alertas_bar(alertas: List[Dict], title: str = "Distribución de Alertas") -> go.Figure:
    if not alertas:
        return go.Figure().update_layout(**_base_layout(title), height=200)

    df = pd.DataFrame(alertas).sort_values("total", ascending=True)

    alerta_colors = {
        "NINGUNA":                  COLORS["cubre"],
        "VALOR_SOBRE_RANGO":        COLORS["no_cubre"],
        "VALOR_BAJO_RANGO":         COLORS["cuarentena"],
        "SERVICIO_FUERA_DE_CATALOGO": COLORS["gray"],
        "MEDICACION_NO_CONCUERDA":  COLORS["secondary"],
    }

    fig = go.Figure(go.Bar(
        x=df["total"],
        y=df["alerta"],
        orientation="h",
        marker_color=[alerta_colors.get(a, COLORS["gray"]) for a in df["alerta"]],
        text=[f"{v:,}" for v in df["total"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>%{x:,} casos<extra></extra>",
    ))
    fig.update_layout(
        **_base_layout(title),
        height=max(220, len(df) * 32 + 60),
        xaxis=dict(title="Casos", gridcolor="#EEE"),
        yaxis=dict(title=""),
        showlegend=False,
    )
    return fig


# ---------------------------------------------------------------------------
# Treemap de categorías de servicio
# ---------------------------------------------------------------------------

def categoria_treemap(servicios: List[Dict], title: str = "Servicios por Volumen") -> go.Figure:
    if not servicios:
        return go.Figure().update_layout(**_base_layout(title), height=300)

    df = pd.DataFrame(servicios)
    nombres = df.get("nombre", df.get("codigo", pd.Series(range(len(df))))).tolist()
    valores = df["total"].tolist()

    fig = go.Figure(go.Treemap(
        labels=nombres,
        parents=[""] * len(nombres),
        values=valores,
        textinfo="label+value",
        hovertemplate="<b>%{label}</b><br>%{value:,} órdenes<extra></extra>",
        marker=dict(colorscale="Blues"),
    ))
    fig.update_layout(**_base_layout(title), height=320, margin=dict(l=5, r=5, t=35, b=5))
    return fig
