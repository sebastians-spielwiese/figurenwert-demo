"""Kern gegen Handrechnung und unabhängige Gegenproben (scikit-learn für die Koeffizienten, Einzelpartien-Schleife für den Sandwich-Schätzer)."""
import numpy as np
import pytest

import fw_modell as m


def tabelle(zeilen, band="x", ply=40):
    """zeilen: Liste (x[6], win, draw, loss)."""
    n = len(zeilen)
    return m.Tabelle(
        band=np.array([band] * n), ply=np.array([ply] * n),
        x=np.array([z[0] for z in zeilen], dtype=float),
        win=np.array([z[1] for z in zeilen], dtype=float),
        draw=np.array([z[2] for z in zeilen], dtype=float),
        loss=np.array([z[3] for z in zeilen], dtype=float),
    )


def logit(p):
    return np.log(p / (1 - p))


def test_handrechnung_zwei_zellen():
    # Nur dP streut: zwei Zellen, drei Parameter weniger als Zellen? Achsenabschnitt + dP bei zwei Zellen ist exakt bestimmt.
    # Zelle 0: dP=0, 1000 Partien, Punktequote 0,55; Zelle 1: dP=1, 1000 Partien, Quote 0,70 (Remis zählen ½).
    t = tabelle([
        ([0, 0, 0, 0, 0, 0], 400, 300, 300),   # (400 + 150) / 1000 = 0,55
        ([1, 0, 0, 0, 0, 0], 600, 200, 200),   # (600 + 100) / 1000 = 0,70
    ])
    e = m.anpassen(t)
    assert e.konvergiert
    assert e.beta[0] == pytest.approx(logit(0.55), abs=1e-8)
    assert e.beta[1] == pytest.approx(logit(0.70) - logit(0.55), abs=1e-8)
    assert list(e.aktiv) == [True, True, False, False, False, False, False]
    assert np.isnan(e.beta[2:]).all()


def expandiere(t: m.Tabelle):
    """Jede Partie einzeln: x, Punkte (1, ½, 0)."""
    X, y = [], []
    for x, w, d, l in zip(t.x, t.win, t.draw, t.loss):
        X += [x] * int(w) + [x] * int(d) + [x] * int(l)
        y += [1.0] * int(w) + [0.5] * int(d) + [0.0] * int(l)
    return np.array(X), np.array(y)


def zufallstabelle(seed=1, zellen=60):
    rng = np.random.default_rng(seed)
    x = np.column_stack([
        rng.integers(-3, 4, zellen), rng.integers(-1, 2, zellen), rng.integers(-1, 2, zellen),
        rng.integers(-1, 2, zellen), rng.integers(-1, 2, zellen), rng.integers(-1, 2, zellen),
    ])
    # Ergebnisse aus einem bekannten Modell, damit die Anpassung Sinn hat
    beta = np.array([0.1, 0.35, 1.0, 1.0, 1.6, 3.2, 0.15])
    p = 1 / (1 + np.exp(-(beta[0] + x @ beta[1:])))
    n = rng.integers(30, 120, zellen)
    win = rng.binomial(n, p * 0.8)
    draw = rng.binomial(n - win, 0.2)
    loss = n - win - draw
    return m.Tabelle(np.array(["x"] * zellen), np.full(zellen, 40), x.astype(float), win.astype(float), draw.astype(float), loss.astype(float))


def test_koeffizienten_gegen_scikit_learn():
    from sklearn.linear_model import LogisticRegression
    t = zufallstabelle()
    e = m.anpassen(t, min_besetzung=1)
    # Remis als halber Sieg plus halbe Niederlage (gleiche Quasi-Likelihood)
    X = np.vstack([t.x, t.x])
    y = np.r_[np.ones(len(t.x)), np.zeros(len(t.x))]
    w = np.r_[t.win + 0.5 * t.draw, t.loss + 0.5 * t.draw]
    ref = LogisticRegression(C=np.inf, tol=1e-12, max_iter=10000).fit(X, y, sample_weight=w)
    soll = np.r_[ref.intercept_, ref.coef_[0]]
    assert e.konvergiert
    assert np.max(np.abs(e.beta - soll)) < 1e-5


def test_sandwich_gegen_einzelpartien():
    t = zufallstabelle(seed=2, zellen=25)
    e = m.anpassen(t, min_besetzung=1)
    X1, y = expandiere(t)
    X = np.column_stack([np.ones(len(y)), X1])
    p = 1 / (1 + np.exp(-X @ e.beta))
    H = X.T @ (X * (p * (1 - p))[:, None])
    meat = X.T @ (X * ((y - p) ** 2)[:, None])
    cov = np.linalg.inv(H) @ meat @ np.linalg.inv(H)
    assert np.max(np.abs(e.cov - cov)) < 1e-9


def test_delta_methode_gegen_differenzen():
    t = zufallstabelle(seed=3)
    e = m.anpassen(t, min_besetzung=1)
    for i in range(1, 5):
        h = 1e-6
        g = np.zeros(7)
        for k in (1, 1 + i):
            b = e.beta.copy()
            b[k] += h
            b2 = e.beta.copy()
            b2[k] -= h
            f = lambda bb: bb[1 + i] / bb[1]
            g[k] = (f(b) - f(b2)) / (2 * h)
        assert e.wert_se(i) == pytest.approx(float(np.sqrt(g @ e.cov @ g)), rel=1e-6)


def test_farbentausch_dreht_nur_den_achsenabschnitt():
    t = zufallstabelle(seed=4)
    e = m.anpassen(t, min_besetzung=1)
    s = m.Tabelle(t.band, t.ply, -t.x, t.loss, t.draw, t.win)
    f = m.anpassen(s, min_besetzung=1)
    assert f.beta[0] == pytest.approx(-e.beta[0], abs=1e-7)
    assert np.max(np.abs(f.beta[1:] - e.beta[1:])) < 1e-7


def test_zu_selten_besetztes_merkmal_ist_nicht_schaetzbar():
    # Dame-Unterschied nur in einer Zelle mit 5 Partien: unter der Schwelle 30
    t = tabelle([
        ([0, 0, 0, 0, 0, 0], 40, 10, 50),
        ([1, 0, 0, 0, 0, 0], 60, 10, 30),
        ([0, 1, 0, 0, 0, 0], 60, 10, 30),
        ([0, 0, 0, 0, 1, 0], 5, 0, 0),
    ])
    e = m.anpassen(t)
    assert not e.aktiv[5]                      # dQ
    assert np.isnan(e.wert(4)) and np.isnan(e.wert_se(4))
    assert e.aktiv[1] and e.aktiv[2]
    assert np.isfinite(e.wert_se(1))           # andere Standardfehler bleiben endlich
    # Ohne Schwelle läge die Dame-Zelle (nur Siege) in vollständiger Trennung: Newton findet keinen endlichen Koeffizienten.
    with pytest.raises(np.linalg.LinAlgError):
        m.anpassen(t, min_besetzung=1)


def test_daten_csv_hat_keine_leere_merkmalsspalte():
    """Nullspalte = Bug-Signal: jedes der sechs Merkmale weicht in der echten Tabelle in vielen Stellungen von 0 ab."""
    t = m.laden()
    n = t.win + t.draw + t.loss
    for j, name in enumerate(m.MERKMALE):
        assert n[t.x[:, j] != 0].sum() >= 100, name


def test_faustregel_vergleichszahlen_gesamtbild():
    """Die Zahlen, die die README nennt: alle Halbzüge, alle Klassen (eine Stellung je Halbzug und Partie, siehe README)."""
    e = m.anpassen(m.auswahl(m.laden(), None, None))
    assert e.konvergiert
    assert 2.8 < e.wert(1) < 3.3 and 2.8 < e.wert(2) < 3.3
    assert 4.2 < e.wert(3) < 5.0
    assert 8.5 < e.wert(4) < 10.5
