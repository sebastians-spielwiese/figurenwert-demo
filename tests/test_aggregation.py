"""Aggregationsskript: Strom, Filter, Material und ruhige Stellungen, gegen Handrechnung und eine unabhängige FEN-Zählung."""
import csv
import json
import random
from pathlib import Path

import chess
import pytest

# Die Aggregation liest Zstandard aus der Standardbibliothek (ab Python 3.14); die App und ihre übrigen Tests laufen auch mit 3.12.
zstd = pytest.importorskip("compression.zstd", reason="Aggregation braucht Python 3.14")
import aggregiere as a  # noqa: E402
import fw_modell as m

DATEN = Path(__file__).resolve().parent.parent / "data"


def fen_zaehlung(fen: str):
    """Unabhängige Gegenprobe: Buchstaben der FEN zählen (ohne python-chess-Brettobjekt)."""
    brett = fen.split()[0]
    z = {c: brett.count(c) for c in "PNBRQpnbrq"}
    return tuple(z[k] - z[k.lower()] for k in "PNBRQ")


def test_material_gegen_fen_zaehlung_auf_zufallspartien():
    rng = random.Random(7)
    geprueft = 0
    for _ in range(30):
        b = chess.Board()
        for _ in range(rng.randint(10, 90)):
            zuege = list(b.legal_moves)
            if not zuege:
                break
            b.push(rng.choice(zuege))
            mat = a.material(b)
            assert mat[:5] == fen_zaehlung(b.fen())
            geprueft += 1
    assert geprueft > 500


def test_laeuferpaar_braucht_beide_feldfarben():
    assert a.material(chess.Board())[5:] == (1, 1)
    # Feldfarbe: a1 ist dunkel, ein Feld ist hell, wenn Dateiindex + Reihenindex ungerade ist
    b = chess.Board("4k3/8/8/8/2B5/8/8/2B1K3 w - - 0 1")  # c4 hell, c1 dunkel: Paar
    assert a.material(b)[5] == 1
    b = chess.Board("4k3/8/8/8/2B5/8/8/4KB2 w - - 0 1")    # c4 hell, f1 hell: kein Paar
    assert a.material(b)[5] == 0
    b = chess.Board("2b1kb2/8/8/8/8/8/8/4K3 w - - 0 1")    # c8 hell, f8 dunkel: Paar
    assert a.material(b)[6] == 1
    b = chess.Board("2b1k3/3b4/8/8/8/8/8/4K3 w - - 0 1")   # c8 hell, d7 hell: kein Paar
    assert a.material(b)[6] == 0


def test_band_grenzen():
    assert a.band_von(1999) is None
    assert a.band_von(2000) == "2000–2199" and a.band_von(2199) == "2000–2199"
    assert a.band_von(2200) == "2200–2399" and a.band_von(2399) == "2200–2399"
    assert a.band_von(2400) == "ab 2400" and a.band_von(3100) == "ab 2400"


def kopf(**kw):
    k = {"Event": "Rated Rapid game", "WhiteElo": "2100", "BlackElo": "2050", "Result": "1-0", "Termination": "Normal"}
    k.update(kw)
    return k


@pytest.mark.parametrize("aenderung,erwartet", [
    ({}, (True, "")),
    ({"Event": "Rated Classical game"}, (True, "")),
    ({"Event": "Rated Blitz game"}, (False, "andere Bedenkzeit")),
    ({"Event": "Rated Correspondence game"}, (False, "andere Bedenkzeit")),
    ({"BlackElo": "1999"}, (False, "Wertung unter Grenze")),
    ({"BlackElo": "?"}, (False, "Wertung fehlt")),
    ({"Result": "*"}, (False, "kein gewertetes Ergebnis")),
    ({"Termination": "Abandoned"}, (False, "Ende nicht normal")),
    ({"Termination": "Time forfeit"}, (True, "")),
])
def test_filter(aenderung, erwartet):
    assert a.passt(kopf(**aenderung)) == erwartet


def test_ruhige_stellungen_handgerechnet():
    # 1. e4 d5 2. exd5 Nf6 3. Nc3 Nxd5 4. Nxd5 Qxd5: nach Halbzug 4 (2...Nf6) Weiß einen Bauern mehr, ruhig
    text = "1. e4 d5 2. exd5 Nf6 3. Nc3 Nxd5 4. Nxd5 Qxd5 *"
    erg = dict(a.stellungen(text, plies=(2, 3, 4, 5, 6, 7, 8)))
    # 2 (1...d5) ruhig, Material gleich; 3 (2.exd5) Schlag; 4 ruhig, dP=+1; 5 (3.Nc3) ruhig, dP=+1; 6 (3...Nxd5) Schlag
    # 7 (4.Nxd5) Schlag; 8 (4...Qxd5) Schlag
    assert sorted(erg) == [2, 4, 5]
    assert erg[2] == (0, 0, 0, 0, 0, 1, 1)
    assert erg[4] == (1, 0, 0, 0, 0, 1, 1)
    assert erg[5] == (1, 0, 0, 0, 0, 1, 1)


def test_stellung_im_schach_wird_ausgelassen():
    # 1. e4 f6 2. Bc4 g5 3. Qh5# : Halbzug 4 ruhig, Halbzug 5 matt (Schach)
    erg = dict(a.stellungen("1. e4 f6 2. Bc4 g5 3. Qh5# 1-0", plies=(4, 5)))
    assert sorted(erg) == [4]


def test_partie_endet_vor_dem_halbzug():
    assert list(a.stellungen("1. e4 e5 *", plies=(20,))) == []


def test_zst_strom_mit_mehreren_frames_und_abgeschnittenem_ende(tmp_path):
    p1 = '[Event "Rated Rapid game"]\n[WhiteElo "2100"]\n[BlackElo "2100"]\n[Result "1-0"]\n[Termination "Normal"]\n\n1. e4 e5 1-0\n\n'
    p2 = '[Event "Rated Blitz game"]\n[Result "0-1"]\n\n1. d4 d5 0-1\n\n'
    p3 = '[Event "Rated Rapid game"]\n[Result "1/2-1/2"]\n\n1. c4 c5 1/2'      # abgeschnitten
    daten = zstd.compress(p1.encode()) + zstd.compress(p2.encode()) + zstd.compress(p3.encode())
    datei = tmp_path / "t.pgn.zst"
    datei.write_bytes(daten[:-3])                                              # auch das Ende des letzten Frames fehlt
    ps = list(a.partien(datei))
    assert [k["Event"] for k, _ in ps] == ["Rated Rapid game", "Rated Blitz game"]  # unvollständige dritte Partie verworfen
    assert ps[0][1] == "1. e4 e5 1-0"


def test_stueck_beginnt_mitten_in_einer_partie(tmp_path):
    """Ein Stück ab einer Frame-Grenze kann mitten in einer Partie beginnen: Rest davor verwerfen, nicht an die nächste Partie hängen."""
    rest = "5. Nf3 Nc6 6. Bb5 a6 1-0\n\n"
    p1 = '[Event "Rated Rapid game"]\n[Result "1-0"]\n\n1. e4 e5 1-0\n\n'
    p2 = '[Event "Rated Rapid game"]\n[Result "0-1"]\n\n1. d4 d5 0-1\n\n'
    datei = tmp_path / "t.pgn.zst"
    datei.write_bytes(zstd.compress((rest + p1 + p2).encode()))
    ps = list(a.partien(datei))
    assert [z for _, z in ps] == ["1. e4 e5 1-0"]          # die zweite Partie ist die letzte und fehlt
    datei.write_bytes(zstd.compress((rest + p1 + p2 + '[Event "x"]\n').encode()))
    assert [z for _, z in a.partien(datei)] == ["1. e4 e5 1-0", "1. d4 d5 0-1"]


def test_mehrere_stuecke_werden_summiert(tmp_path):
    def spiel(elo, zuege, res="1-0"):
        return (f'[Event "Rated Rapid game"]\n[UTCDate "2026.10.01"]\n[UTCTime "00:00:01"]\n[WhiteElo "{elo}"]\n[BlackElo "{elo}"]\n'
                f'[Result "{res}"]\n[Termination "Normal"]\n\n{zuege} {res}\n\n')
    schluss = '[Event "Ende"]\n\n'
    zuege = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6"
    d1, d2 = tmp_path / "a.pgn.zst", tmp_path / "b.pgn.zst"
    d1.write_bytes(zstd.compress((spiel(2100, zuege) + spiel(2450, zuege, "0-1") + schluss).encode()))
    d2.write_bytes(zstd.compress((spiel(2100, zuege, "1/2-1/2") + schluss).encode()))
    e1, e2 = a.verarbeite(d1), a.verarbeite(d2)
    assert e1["zaehl"]["behalten"] == 2 and e2["zaehl"]["behalten"] == 1
    assert e1["zaehl"]["behalten ab 2400"] == 1 and e1["erste"] == ("2026.10.01", "00:00:01")
    summe = e1["zaehl"] + e2["zaehl"]
    assert summe["behalten 2000–2199"] == 2


def test_csv_und_meta_stimmen_ueberein():
    meta = json.loads((DATEN / "meta.json").read_text(encoding="utf-8"))
    zeilen = list(csv.DictReader(open(DATEN / "stellungen.csv", encoding="utf-8", newline="")))
    assert len(zeilen) == meta["zeilen_csv"]
    z = meta["zaehlungen"]
    for ply in a.PLIES:
        n = sum(int(r["win"]) + int(r["draw"]) + int(r["loss"]) for r in zeilen if int(r["ply"]) == ply)
        assert n == z[f"Stellungen Halbzug {ply}"]
    assert z["behalten"] == sum(v for k, v in z.items() if k.startswith("behalten ") )
    abgelehnt = sum(v for k, v in z.items() if k.startswith("abgelehnt"))
    assert z["Partien im Strom"] == z["behalten"] + abgelehnt
    # Läuferpaar-Spalten sind 0/1
    assert {r["wBP"] for r in zeilen} <= {"0", "1"} and {r["bBP"] for r in zeilen} <= {"0", "1"}
    assert m.MIN_BESETZUNG > 0
