"""Plotly-Abbildungen: Achsen fest, keine Zoom-Interaktion."""
from __future__ import annotations

import plotly.graph_objects as go

import fw_auswertung as au

FARBE_SCHAETZUNG = "#1f5f99"
FARBE_FAUST = "#c0392b"


def werte_figur(zeilen: list[au.Zeile]) -> go.Figure:
    """Geschätzter Wert je Figur mit 95-%-Band (Fehlerbalken) gegen die Faustregel (Rauten). Bauer = 1 per Definition, nicht gezeigt."""
    z = [r for r in zeilen[1:] if r.im_band is not None]
    nicht = [r.figur for r in zeilen[1:] if r.im_band is None]
    fig = go.Figure()
    if z:
        fig.add_trace(go.Scatter(
            x=[r.figur for r in z], y=[r.wert for r in z], mode="markers", name="Schätzung aus den Partien",
            marker=dict(size=11, color=FARBE_SCHAETZUNG),
            error_y=dict(type="data", array=[r.oben - r.wert for r in z], arrayminus=[r.wert - r.unten for r in z], color=FARBE_SCHAETZUNG),
            hovertemplate="%{x}: %{y:.2f} Bauern<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=[r.figur for r in zeilen[1:]], y=[r.faust for r in zeilen[1:]], mode="markers", name="Faustregel 3 / 3 / 5 / 9",
        marker=dict(size=12, symbol="diamond-open", color=FARBE_FAUST, line=dict(width=2)),
        hovertemplate="%{x}: %{y:.0f} Bauern (Faustregel)<extra></extra>"))
    anno = []
    if nicht:
        anno.append(dict(text="Nicht schätzbar: " + ", ".join(nicht), xref="paper", yref="paper", x=0.01, y=0.98, showarrow=False,
                         xanchor="left", yanchor="top", font=dict(size=12)))
    fig.update_layout(
        height=420, margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", y=-0.15),
        xaxis=dict(fixedrange=True, categoryorder="array", categoryarray=[r.figur for r in zeilen[1:]]),
        yaxis=dict(title="Wert in Bauern", range=[0, 14], fixedrange=True, gridcolor="rgba(128,128,128,0.25)"),
        annotations=anno, dragmode=False)
    return fig
