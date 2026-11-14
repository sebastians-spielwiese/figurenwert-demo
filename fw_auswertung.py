"""Auswertung der Anpassung: Vergleich mit der Faustregel, Verdikt, erwartete Punkte einer Stellung."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

import fw_modell as m

Z95 = 1.959963984540054  # 97,5-%-Quantil der Standardnormalverteilung


def de(x: float, nd: int = 2) -> str:
    """Zahl mit Dezimalkomma; NaN als Gedankenstrich."""
    return "–" if not np.isfinite(x) else f"{x:.{nd}f}".replace(".", ",")


@dataclass(frozen=True)
class Zeile:
    figur: str
    wert: float
    se: float
    unten: float
    oben: float
    faust: float
    im_band: bool | None      # None = nicht schätzbar
    abstand_se: float         # (Wert - Faustregel) / SE, NaN wenn nicht schätzbar


def vergleich(e: m.Ergebnis, mit_laeuferpaar: bool = True) -> list[Zeile]:
    """Zeilen für Bauer (= 1 per Definition), Springer, Läufer, Turm, Dame; Läuferpaar siehe `laeuferpaar`."""
    zeilen = []
    for i, name in enumerate(m.FIGUREN):
        w, se = e.wert(i), e.wert_se(i)
        faust = m.FAUSTREGEL[name]
        if i == 0 or not np.isfinite(w) or not np.isfinite(se):
            zeilen.append(Zeile(name, w if i == 0 else float("nan"), se if i == 0 else float("nan"), float("nan"), float("nan"),
                                faust, None if i else True, float("nan")))
            continue
        unten, oben = w - Z95 * se, w + Z95 * se
        zeilen.append(Zeile(name, w, se, unten, oben, faust, bool(unten <= faust <= oben), (w - faust) / se))
    return zeilen


def laeuferpaar(e: m.Ergebnis) -> tuple[float, float] | None:
    """Zuschlag für das Läuferpaar in Bauerneinheiten und sein Standardfehler; None, wenn nicht geschätzt."""
    if not (e.aktiv[6] and e.aktiv[1]):
        return None
    return e.wert(5), e.wert_se(5)


def erwartete_punkte(e: m.Ergebnis, d: dict[str, int]) -> float | None:
    """Erwartete Punkte (0 bis 1) für Weiß bei Materialunterschied d (Schlüssel dP, dN, dB, dR, dQ, LP); None, wenn ein genutztes
    Merkmal nicht angepasst wurde (dann ist der Wert nicht durch Daten gedeckt)."""
    x = np.array([d.get(k, 0) for k in ("dP", "dN", "dB", "dR", "dQ", "LP")], dtype=float)
    nicht_angepasst = ~e.aktiv[1:] & (x != 0)
    if not e.aktiv[0] or nicht_angepasst.any():
        return None
    b = np.where(e.aktiv, e.beta, 0.0)
    z = b[0] + float(x @ b[1:])
    return 1.0 / (1.0 + math.exp(-z))


def verdikt(zeilen: list[Zeile]) -> tuple[str, str]:
    """(Stufe, Text) mit Stufe 'success', 'info' oder 'warning'. Zählt nur die schätzbaren Figuren ohne den Bauern."""
    z = [r for r in zeilen[1:] if r.im_band is not None]
    fehlend = [r.figur for r in zeilen[1:] if r.im_band is None]
    if not z:
        return "warning", "Für diese Auswahl ist keine Figur schätzbar (zu wenige Stellungen mit Materialunterschied)."
    ausserhalb = [r for r in z if not r.im_band]
    text = f"Von {len(z)} schätzbaren Figurenarten liegt die Faustregel bei {len(z) - len(ausserhalb)} im 95-%-Band der Schätzung."
    if len(ausserhalb) < len(z):
        text += " „Im Band“ heißt nur: Die Daten widersprechen der Faustregel nicht; breite Bänder bestätigen sie nicht."
    if ausserhalb:
        text += " Außerhalb: " + ", ".join(f"{r.figur} (Schätzung {de(r.wert)}, Faustregel {r.faust:.0f})" for r in ausserhalb) + "."
    if fehlend:
        text += " Nicht schätzbar: " + ", ".join(fehlend) + "."
    return ("success" if not ausserhalb else "info"), text


def rohe_quote(t: m.Tabelle, dp: int = 0) -> tuple[float, int]:
    """Rohe Punktequote von Weiß (ohne Modell) und Zahl der Stellungen, in denen nur der Bauernunterschied `dp` von 0 abweicht
    (Springer-, Läufer-, Turm- und Dame-Unterschied 0, gleicher Läuferpaar-Status auf beiden Seiten)."""
    maske = (t.x[:, 0] == dp) & np.all(t.x[:, 1:] == 0, axis=1)
    n = float((t.win + t.draw + t.loss)[maske].sum())
    if n == 0:
        return float("nan"), 0
    return float((t.win[maske].sum() + 0.5 * t.draw[maske].sum()) / n), int(n)
