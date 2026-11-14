"""Jede Zahl der README-Tabelle „Befunde“ und jede Aussage der Hilfetexte steht hier (Band oder exakt, wie in der README angegeben) und wird aus
data/stellungen.csv nachgerechnet. Zahlen aus data/meta.json (Zählungen des Aggregationslaufs) prüft ein eigener Test gegen den Text der README."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

import fw_auswertung as au
import fw_constants as C
import fw_modell as m

WURZEL = Path(__file__).resolve().parent.parent
README = (WURZEL / "README.md").read_text(encoding="utf-8")
KLASSEN = (None, "2000–2199", "2200–2399", "ab 2400")
PLIES = (20, 30, 40, 50, 60, 70, 80)
SPAET = (40, 50, 60, 70, 80)
NAMEN = ("Springer", "Läufer", "Turm", "Dame")


@pytest.fixture(scope="module")
def tabelle():
    return m.laden()


@pytest.fixture(scope="module")
def raster(tabelle):
    return {(b, p): m.anpassen(m.auswahl(tabelle, b, p)) for b in KLASSEN for p in PLIES}


def test_halbzug_40_alle_klassen(raster):
    """Springer 3,04 ± 0,05, Läufer 3,05 ± 0,05, Turm 4,49 ± 0,08, Dame 9,53 ± 0,18 (190.612 Stellungen); die Faustregel liegt bei Springer und Läufer im Band, bei Turm und Dame nicht."""
    e = raster[(None, 40)]
    assert int(e.n) == 190612
    soll = {1: (3.04, 0.05), 2: (3.05, 0.05), 3: (4.49, 0.08), 4: (9.53, 0.18)}
    for i, (w, se) in soll.items():
        assert e.wert(i) == pytest.approx(w, abs=0.005), i
        assert e.wert_se(i) == pytest.approx(se, abs=0.005), i
    assert [r.im_band for r in au.vergleich(e)[1:]] == [True, True, False, False]


def test_raster_zaehlungen(raster):
    """28 Auswahlen (4 Klassen × 7 Halbzüge) × 4 Figuren = 112 Werte; 109 schätzbar, 3 nicht (alle Dame); bei 62 der 109 liegt die Faustregel außerhalb des Bands."""
    zeilen = {(k, r.figur): r for k, e in raster.items() for r in au.vergleich(e)[1:]}
    assert len(raster) == 28 and len(zeilen) == 112
    nicht = sorted((k, f) for (k, f), r in zeilen.items() if r.im_band is None)
    assert nicht == [(("2200–2399", 20), "Dame"), (("ab 2400", 20), "Dame"), (("ab 2400", 30), "Dame")]
    schaetzbar = [r for r in zeilen.values() if r.im_band is not None]
    assert len(schaetzbar) == 109
    assert sum(1 for r in schaetzbar if not r.im_band) == 62


def test_halbzug_40_bis_80_alles_schaetzbar(raster):
    """Bei Halbzug 40 bis 80 sind alle vier Figuren in allen vier Klassen schätzbar (5 × 4 × 4 = 80 Werte)."""
    for k, e in raster.items():
        if k[1] in SPAET:
            assert all(r.im_band is not None for r in au.vergleich(e)[1:]), k
    assert sum(1 for k in raster if k[1] in SPAET) * 4 == 80


def test_dame_unterschiede_je_auswahl(tabelle):
    """Stellungen mit Dame-Unterschied: 28 und 15 bei Halbzug 20 (2200–2399, ab 2400), 24 bei Halbzug 30 (ab 2400): unter der Schwelle 30; sonst mindestens 82."""
    def zahl(b, p):
        s = m.auswahl(tabelle, b, p)
        return int((s.win + s.draw + s.loss)[s.x[:, 4] != 0].sum())
    assert (zahl("2200–2399", 20), zahl("ab 2400", 20), zahl("ab 2400", 30)) == (28, 15, 24)
    assert m.MIN_BESETZUNG == 30
    assert min(zahl(b, p) for b in KLASSEN for p in PLIES if (b, p) not in {("2200–2399", 20), ("ab 2400", 20), ("ab 2400", 30)}) == 82


def test_turm_in_den_grossen_klassen_unter_fuenf(raster):
    """Klassen 2000–2199 und 2200–2399, Halbzug 40 bis 80: Turm zwischen 4,06 und 4,55, die 5 in allen 10 Auswahlen außerhalb des Bands."""
    werte, im = [], []
    for b in ("2000–2199", "2200–2399"):
        for p in SPAET:
            r = au.vergleich(raster[(b, p)])[3]
            werte.append(r.wert)
            im.append(r.im_band)
    assert (round(min(werte), 2), round(max(werte), 2)) == (4.06, 4.55)
    assert not any(im) and len(im) == 10


def test_turm_ab_2400(raster):
    """Klasse ab 2400, Halbzug 40 bis 80: Turm 6,41 / 4,92 / 5,06 / 5,88 / 6,10; die 5 liegt bei 40, 50 und 60 im Band, bei 70 und 80 nicht."""
    r = [au.vergleich(raster[("ab 2400", p)])[3] for p in SPAET]
    assert [round(x.wert, 2) for x in r] == [6.41, 4.92, 5.06, 5.88, 6.10]
    assert [x.im_band for x in r] == [True, True, True, False, False]


def test_werte_sinken_mit_dem_halbzug(raster):
    """Alle Klassen: Springer, Läufer und Dame sinken von Halbzug 30 bis 80 bei jedem Schritt (3,21 → 2,71; 3,23 → 2,64; 10,23 → 8,04); der Turm bleibt zwischen 4,20 und 4,55."""
    for i, (a, b) in {1: (3.21, 2.71), 2: (3.23, 2.64), 4: (10.23, 8.04)}.items():
        w = [raster[(None, p)].wert(i) for p in (30, 40, 50, 60, 70, 80)]
        assert w == sorted(w, reverse=True), i
        assert (round(w[0], 2), round(w[-1], 2)) == (a, b), i
    turm = [raster[(None, p)].wert(3) for p in (30, 40, 50, 60, 70, 80)]
    assert (round(min(turm), 2), round(max(turm), 2)) == (4.20, 4.55)


def test_klasse_ab_2400_hoeher(raster):
    """Halbzug 40 bis 80: Alle vier Werte liegen in der Klasse ab 2400 höher als in 2000–2199 (20 von 20 Vergleichen)."""
    hoeher = sum(raster[("ab 2400", p)].wert(i) > raster[("2000–2199", p)].wert(i) for p in SPAET for i in range(1, 5))
    assert hoeher == 20
    # Bänder ohne Überlappung (untere Grenze ab 2400 über der oberen Grenze von 2000–2199): 11 von 20 (Halbzug 70 und 80: alle, 60: 3, 40 und 50: keines)
    ohne = {}
    for p in SPAET:
        a, b = au.vergleich(raster[("ab 2400", p)])[1:], au.vergleich(raster[("2000–2199", p)])[1:]
        ohne[p] = sum(x.unten > y.oben for x, y in zip(a, b))
    assert ohne == {40: 0, 50: 0, 60: 3, 70: 4, 80: 4}


def test_stuecke_ab_2400_turm_stellungen(tabelle):
    """README: Turm ab 2400, Halbzug 40 bis 80: 7.959 bis 10.452 Stellungen (Gesamtzahl der Auswahl)."""
    n = [m.anpassen(m.auswahl(tabelle, "ab 2400", p)).n for p in SPAET]
    assert (int(min(n)), int(max(n))) == (7959, 10452)


def test_mittlere_stellungen_je_partie():
    """Preset „Alle Halbzüge zusammen“: im Mittel 3,6 Stellungen je behaltener Partie."""
    z = json.loads((WURZEL / "data" / "meta.json").read_text(encoding="utf-8"))["zaehlungen"]
    mittel = sum(z[f"Stellungen Halbzug {p}"] for p in PLIES) / z["behalten"]
    assert round(mittel, 1) == 3.6 and "im Mittel 3,6" in C.PRESET_HELP["Alle Halbzüge zusammen"]


def test_bauernkoeffizient_waechst_mit_dem_halbzug(raster):
    """b_P (Logit-Einheiten je Bauer, alle Klassen): 0,16 / 0,28 / 0,37 / 0,44 / 0,49 / 0,54 / 0,57 für Halbzug 20 bis 80."""
    b = [raster[(None, p)].beta[1] for p in PLIES]
    assert b == pytest.approx([0.16, 0.28, 0.37, 0.44, 0.49, 0.54, 0.57], abs=0.006)   # 0,535 liegt auf der Rundungsgrenze: mit Toleranz prüfen
    assert b == sorted(b)


def test_achsenabschnitt_gegen_rohe_quote(raster, tabelle):
    """Bei gleichem Material erwartet das Modell 52,0 bis 53,0 %; roh liegt die Quote in Stellungen mit exakt gleichem Material bei 51,7 bis 52,3 % (alle Klassen, je Halbzug)."""
    modell = [100 * au.erwartete_punkte(raster[(None, p)], {}) for p in PLIES]
    roh = [100 * au.rohe_quote(m.auswahl(tabelle, None, p), 0)[0] for p in PLIES]
    assert (round(min(modell), 1), round(max(modell), 1)) == (52.0, 53.0)
    assert (round(min(roh), 1), round(max(roh), 1)) == (51.7, 52.3)


def test_bauer_mehr(raster, tabelle):
    """Halbzug 40 (alle Klassen): Modell 52,9 → 62,0 %; roh 51,7 % (56.738 Stellungen) → 63,7 % (12.542). Halbzug 80: Modell 65,7 %, roh 68,4 % (8.105)."""
    s = m.auswahl(tabelle, None, 40)
    e = raster[(None, 40)]
    assert round(100 * au.erwartete_punkte(e, {}), 1) == 52.9 and round(100 * au.erwartete_punkte(e, {"dP": 1}), 1) == 62.0
    (r0, n0), (r1, n1) = au.rohe_quote(s, 0), au.rohe_quote(s, 1)
    assert (round(100 * r0, 1), n0, round(100 * r1, 1), n1) == (51.7, 56738, 63.7, 12542)
    s80 = m.auswahl(tabelle, None, 80)
    r, n = au.rohe_quote(s80, 1)
    assert (round(100 * r, 1), n) == (68.4, 8105)
    assert round(100 * au.erwartete_punkte(raster[(None, 80)], {"dP": 1}), 1) == 65.7


def test_laeuferpaar(raster):
    """Läuferpaar 0,55 ± 0,04 Bauern (Halbzug 40, alle Klassen); in 21 der 28 Auswahlen liegt das 95-%-Band strikt über 0, in keiner strikt darunter; ab 2400 bei Halbzug 30: −0,49 ± 0,49."""
    lp = au.laeuferpaar(raster[(None, 40)])
    assert lp[0] == pytest.approx(0.55, abs=0.005) and lp[1] == pytest.approx(0.04, abs=0.005)
    ueber = unter = 0
    for e in raster.values():
        w, se = au.laeuferpaar(e)
        ueber += w - au.Z95 * se > 0
        unter += w + au.Z95 * se < 0
    assert (ueber, unter) == (21, 0)
    w, se = au.laeuferpaar(raster[("ab 2400", 30)])
    assert (round(w, 2), round(se, 2)) == (-0.49, 0.49)


def test_ohne_laeuferpaar_steigt_der_laeuferwert(tabelle):
    """Ohne das Läuferpaar-Merkmal steigt der Läuferwert bei Halbzug 40 (alle Klassen) von 3,05 auf 3,37, der Springerwert bleibt bei 3,04."""
    t = m.auswahl(tabelle, None, 40)
    mit, ohne = m.anpassen(t), m.anpassen(t, mit_laeuferpaar=False)
    assert (round(mit.wert(2), 2), round(ohne.wert(2), 2)) == (3.05, 3.37)
    assert (round(mit.wert(1), 2), round(ohne.wert(1), 2)) == (3.04, 3.04)


class TestHilfetexte:
    """Aussagen der Hilfetexte in fw_constants.PRESET_HELP."""

    def test_frueh_sieben_von_zehn_gleiches_material(self, tabelle):
        s = m.auswahl(tabelle, None, 20)
        n = s.win + s.draw + s.loss
        anteil = n[np.all(s.x == 0, axis=1)].sum() / n.sum()
        assert round(anteil, 2) == 0.70
        assert "sieben von zehn" in C.PRESET_HELP["Früh (Halbzug 20)"]

    def test_frueh_dame_ab_2200_nicht_schaetzbar(self, raster):
        assert not raster[("2200–2399", 20)].aktiv[5] and not raster[("ab 2400", 20)].aktiv[5]
        assert raster[("2000–2199", 20)].aktiv[5] and raster[(None, 20)].aktiv[5]

    def test_spaet_alle_vier_unter_halbzug_40(self, raster):
        assert all(raster[(None, 80)].wert(i) < raster[(None, 40)].wert(i) for i in range(1, 5))

    def test_ab_2400_baender_deutlich_breiter(self, raster):
        """Standardfehler bei Halbzug 40: ab 2400 mindestens das Zehnfache von „alle Klassen“ (gemessen 11,8 bis 13,2); README sagt „mehr als das Zehnfache“."""
        quot = [raster[("ab 2400", 40)].wert_se(i) / raster[(None, 40)].wert_se(i) for i in range(1, 5)]
        assert min(quot) > 10 and round(min(quot), 1) == 11.8 and round(max(quot), 1) == 13.2

    def test_ab_2400_halbzug_40_alles_schaetzbar(self, raster):
        assert raster[("ab 2400", 40)].aktiv[1:].all()

    def test_texte_nennen_keine_absolutwoerter(self):
        import re
        alle = " ".join(C.PRESET_HELP.values())
        assert not re.search(r"\b(nie|immer|fast nie|ehrlich)\b", alle)


def zahl(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def test_readme_zahlen_aus_meta():
    meta = json.loads((WURZEL / "data" / "meta.json").read_text(encoding="utf-8"))
    z = meta["zaehlungen"]
    for k in ("Partien im Strom", "behalten", "behalten 2000–2199", "behalten 2200–2399", "behalten ab 2400",
              "davon Turnier-Event (Arena oder Swiss)", *[f"Stellungen Halbzug {p}" for p in PLIES]):
        assert zahl(z[k]) in README, k
    assert zahl(meta["abgerufene_bytes"]) in README and zahl(meta["gesamtgroesse_bytes"]) in README
    assert zahl(meta["zeilen_csv"]) in README
    assert len(meta["stuecke"]) == 6 and "sechs Stücke" in README


def test_readme_testzahl_stimmt():
    if sys.version_info < (3, 14):
        pytest.skip("Die Aggregationstests werden vor Python 3.14 übersprungen; die Zahl der README gilt für 3.14")
    ausgabe = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", str(WURZEL / "tests")],
                             capture_output=True, text=True, encoding="utf-8", cwd=WURZEL).stdout
    zeile = [x for x in ausgabe.splitlines() if x.strip().endswith("collected") or " tests collected" in x]
    n = int(zeile[-1].split()[0]) if zeile else None
    assert n is not None and f"{n} Tests" in README, (n, ausgabe[-200:])
