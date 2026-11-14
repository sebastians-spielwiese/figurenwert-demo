"""Kern der Demo: logistische Regression des Partieergebnisses auf den Materialunterschied (reines numpy).

Modell: Wahrscheinlichkeit-Punkte p = 1 / (1 + exp(-(b0 + bP·dP + bN·dN + bB·dB + bR·dR + bQ·dQ + bL·dL))) für Weiß,
dP … dQ = Materialunterschied Weiß minus Schwarz, dL = Läuferpaar Weiß minus Läuferpaar Schwarz (je 0 oder 1).
Zielgröße je Partie: Punkte aus Weißsicht (1, ½, 0); angepasst wird die Quasi-Binomial-Likelihood (Remis zählen ½), per Newton-Verfahren
(IRLS). Standardfehler: Sandwich-Schätzer (HC0), der die tatsächliche Streuung der Punkte nutzt (Remis streuen weniger als eine Münze).
Wert einer Figur in Bauerneinheiten = bFigur / bP; Standardfehler per Delta-Methode.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

FIGUREN = ("Bauer", "Springer", "Läufer", "Turm", "Dame")
MERKMALE = ("dP", "dN", "dB", "dR", "dQ", "Läuferpaar")
FAUSTREGEL = {"Bauer": 1.0, "Springer": 3.0, "Läufer": 3.0, "Turm": 5.0, "Dame": 9.0}
DATEI = Path(__file__).resolve().parent / "data" / "stellungen.csv"
MIN_BESETZUNG = 30  # Mindestzahl Stellungen, in denen ein Merkmal von 0 abweichen muss, damit sein Koeffizient angepasst wird


@dataclass(frozen=True)
class Tabelle:
    """Aggregierte Stellungen: je Zeile Wertungsklasse, Halbzug, Merkmale (6 Spalten) und Zählungen Sieg/Remis/Niederlage (Weißsicht)."""
    band: np.ndarray      # Text
    ply: np.ndarray       # int
    x: np.ndarray         # (n, 6) Materialunterschiede und Läuferpaar-Differenz
    win: np.ndarray
    draw: np.ndarray
    loss: np.ndarray


@dataclass(frozen=True)
class Ergebnis:
    beta: np.ndarray          # (7,) Achsenabschnitt, dP, dN, dB, dR, dQ, Läuferpaar
    se: np.ndarray            # Sandwich-Standardfehler, gleiche Reihenfolge
    cov: np.ndarray           # (7, 7) Sandwich-Kovarianz
    n: float                  # Zahl der Stellungen (= Partien, eine Stellung je Partie)
    konvergiert: bool
    schritte: int
    aktiv: np.ndarray         # (7,) bool: welche Koeffizienten angepasst wurden

    def wert(self, i: int) -> float:
        """Wert von Merkmal i (0 = Bauer … 4 = Dame, 5 = Läuferpaar) in Bauerneinheiten; NaN, wenn nicht schätzbar."""
        return float(self.beta[1 + i] / self.beta[1])

    def wert_se(self, i: int) -> float:
        """Standardfehler des Werts per Delta-Methode (Quotient b_i / b_P); NaN, wenn nicht schätzbar."""
        if i == 0:
            return 0.0 if self.aktiv[1] else float("nan")
        if not (self.aktiv[1] and self.aktiv[1 + i]):
            return float("nan")
        b = self.beta
        g = np.zeros(7)
        g[1 + i] = 1.0 / b[1]
        g[1] = -b[1 + i] / b[1] ** 2
        idx = np.flatnonzero(self.aktiv)
        return float(np.sqrt(g[idx] @ self.cov[np.ix_(idx, idx)] @ g[idx]))


def laden(pfad: Path = DATEI) -> Tabelle:
    zeilen = list(csv.DictReader(open(pfad, encoding="utf-8", newline="")))
    n = len(zeilen)
    x = np.zeros((n, 6))
    for i, z in enumerate(zeilen):
        x[i] = [int(z["dP"]), int(z["dN"]), int(z["dB"]), int(z["dR"]), int(z["dQ"]), int(z["wBP"]) - int(z["bBP"])]
    return Tabelle(
        band=np.array([z["band"] for z in zeilen]),
        ply=np.array([int(z["ply"]) for z in zeilen]),
        x=x,
        win=np.array([int(z["win"]) for z in zeilen], dtype=float),
        draw=np.array([int(z["draw"]) for z in zeilen], dtype=float),
        loss=np.array([int(z["loss"]) for z in zeilen], dtype=float),
    )


def auswahl(t: Tabelle, band: str | None, ply: int | tuple[int, ...] | None) -> Tabelle:
    """Teilmenge; band None = alle Klassen, ply None = alle Halbzüge, sonst ein Halbzug oder mehrere (dann zählen mehrere
    Stellungen derselben Partie, die Standardfehler sind zu klein)."""
    m = np.ones(len(t.ply), dtype=bool)
    if band is not None:
        m &= t.band == band
    if ply is not None:
        m &= np.isin(t.ply, np.atleast_1d(ply))
    return Tabelle(t.band[m], t.ply[m], t.x[m], t.win[m], t.draw[m], t.loss[m])


def anpassen(t: Tabelle, mit_laeuferpaar: bool = True, min_besetzung: int = MIN_BESETZUNG, max_schritte: int = 50,
             tol: float = 1e-10) -> Ergebnis:
    """Newton/IRLS für die Quasi-Binomial-Likelihood. Merkmale, die in weniger als `min_besetzung` Stellungen von 0 abweichen,
    werden nicht angepasst (Koeffizient und Standardfehler NaN, `aktiv` False); ohne Bauer-Streuung ist alles nicht schätzbar."""
    n_i = t.win + t.draw + t.loss
    ys = (t.win + 0.5 * t.draw) / n_i
    X = np.column_stack([np.ones(len(n_i)), t.x])
    aktiv = np.ones(7, dtype=bool)
    if not mit_laeuferpaar:
        aktiv[6] = False
    # Merkmal nur anpassen, wenn es in mindestens MIN_BESETZUNG Stellungen von 0 abweicht (sonst Matrix singulär bzw. Zufallswert)
    besetzt = np.array([n_i[X[:, 1 + j] != 0].sum() for j in range(6)])
    aktiv[1:] &= besetzt >= min_besetzung
    Xa = X[:, aktiv]
    b = np.zeros(Xa.shape[1])
    ok, schritte = False, 0
    for schritte in range(1, max_schritte + 1):
        p = 1.0 / (1.0 + np.exp(-Xa @ b))
        grad = Xa.T @ (n_i * (ys - p))
        w = n_i * p * (1 - p)
        H = Xa.T @ (Xa * w[:, None])
        schritt = np.linalg.solve(H, grad)
        b = b + schritt
        if np.max(np.abs(schritt)) < tol:
            ok = True
            break
    p = 1.0 / (1.0 + np.exp(-Xa @ b))
    w = n_i * p * (1 - p)
    H = Xa.T @ (Xa * w[:, None])
    # Streuung der Punkte je Zeile um p, aus den Zählungen: Σ (y - p)² über die Partien der Zeile
    s2 = t.win * (1 - p) ** 2 + t.draw * (0.5 - p) ** 2 + t.loss * p ** 2
    meat = Xa.T @ (Xa * s2[:, None])
    Hinv = np.linalg.inv(H)
    cov_a = Hinv @ meat @ Hinv
    beta = np.full(7, np.nan)
    beta[aktiv] = b
    cov = np.full((7, 7), np.nan)
    cov[np.ix_(aktiv, aktiv)] = cov_a
    return Ergebnis(beta, np.sqrt(np.diag(cov)), cov, float(n_i.sum()), ok, schritte, aktiv)
