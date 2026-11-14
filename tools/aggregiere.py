#!/usr/bin/env python3
"""Aggregiert Teile einer Lichess-Monatsdatei zu der kleinen CSV `data/stellungen.csv` (und `data/meta.json`).

    python tools/aggregiere.py <Stück1.pgn.zst> [<Stück2.pgn.zst> ...] [--ausgabe data] [--quelle-name <Originaldatei>] [--gesamtgroesse <Bytes>]

Was geschieht (alles Entscheidungen dieses Skripts, siehe README „Daten“):
* Jede Datei wird als Strom gelesen (Zstandard aus der Standardbibliothek, Python 3.14), mehrere Dateien parallel in eigenen Prozessen.
  Die Dateien dürfen abgeschnittene Stücke der Monatsdatei sein: Eine Partie, die mitten im Stück beginnt oder endet, wird verworfen.
  Die Stücke dürfen sich nicht überlappen (sonst zählen Partien doppelt).
* Behalten werden Partien, deren Event „Rapid“ oder „Classical“ enthält (Einzel- und Turnierpartien, ohne Correspondence),
  mit beiden Wertungen ≥ MIN_ELO (ohne Fragezeichen), gewertetem Ergebnis (1-0, 0-1, 1/2-1/2) und Termination „Normal“ oder „Time forfeit“.
* Wertungsklasse = die kleinere der beiden Wertungen (beide Spieler mindestens so stark): 2000–2199, 2200–2399, ab 2400.
* Aus jeder behaltenen Partie wird die Stellung nach Halbzug 20, 30, 40, 50, 60, 70 und 80 gelesen, falls die Partie dann noch läuft und die
  Stellung ruhig ist (Anzugsseite nicht im Schach, letzter Zug kein Schlagzug). Alle diese Halbzüge sind gerade: Weiß ist am Zug.
* Je Stellung: Materialunterschied Weiß minus Schwarz je Figurenart (Bauer, Springer, Läufer, Turm, Dame), Läuferpaar je Seite
  (Läufer auf hellem und dunklem Feld) und das Partieergebnis aus Weißsicht. Gleiche Zeilen werden gezählt.
Die Rohdateien kommen nicht ins Repo; `data/meta.json` hält Quelle, Stücke mit Zeitraum und alle Zählungen fest.
Lizenz der Daten: Lichess-Datenbank, CC0 (https://database.lichess.org/). `chess` (python-chess, GPL-3.0 oder neuer) wird nur hier und in den Tests benutzt.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from compression.zstd import ZstdDecompressor
from pathlib import Path

import chess
import chess.pgn

MIN_ELO = 2000
PLIES = (20, 30, 40, 50, 60, 70, 80)
BANDEN = ((2000, "2000–2199"), (2200, "2200–2399"), (2400, "ab 2400"))
ERGEBNIS = {"1-0": 1.0, "0-1": 0.0, "1/2-1/2": 0.5}
TAG = re.compile(r'^\[(\w+) "(.*)"\]$')
SPALTEN = ["band", "ply", "dP", "dN", "dB", "dR", "dQ", "wBP", "bBP", "win", "draw", "loss"]


def band_von(minelo: int) -> str | None:
    name = None
    for grenze, label in BANDEN:
        if minelo >= grenze:
            name = label
    return name


def zeilen_aus_zst(pfad: Path):
    """Zeilen (bytes) des entpackten Stroms; mehrere Zstandard-Frames und abgeschnittenes Ende sind erlaubt."""
    dec = ZstdDecompressor()
    rest = b""
    with open(pfad, "rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            teile = []
            while chunk:
                if dec.eof:
                    chunk = dec.unused_data + chunk
                    dec = ZstdDecompressor()
                teile.append(dec.decompress(chunk))
                if dec.eof and dec.unused_data:
                    chunk = dec.unused_data
                    dec = ZstdDecompressor()
                    continue
                break
            zeilen = (rest + b"".join(teile)).split(b"\n")
            rest = zeilen.pop()
            yield from zeilen
    # `rest` ist eine unvollständige letzte Zeile und wird verworfen.


def partien(pfad: Path):
    """Liefert (Kopf-Wörterbuch, Zugtext) je vollständiger Partie. Die erste Partie fehlt, wenn der Strom mitten in ihr beginnt
    (alles vor dem ersten „[Event“ wird verworfen), und die letzte, womöglich unvollständige Partie fehlt ebenfalls."""
    kopf: dict[str, str] = {}
    zuege: list[str] = []
    offen = False
    for z in zeilen_aus_zst(pfad):
        text = z.decode("utf-8", "replace").rstrip("\r")
        if text.startswith("[Event "):
            if offen:
                yield kopf, " ".join(zuege)
            kopf, zuege, offen = {}, [], True
        if not offen:
            continue
        if text.startswith("["):
            m = TAG.match(text)
            if m:
                kopf[m.group(1)] = m.group(2)
        elif text.strip():
            zuege.append(text.strip())


def passt(kopf: dict[str, str]) -> tuple[bool, str]:
    """Filter der Köpfe. Gibt (behalten, Grund der Ablehnung) zurück."""
    ev = kopf.get("Event", "")
    if "Rapid" not in ev and "Classical" not in ev:
        return False, "andere Bedenkzeit"
    if "Correspondence" in ev:
        return False, "andere Bedenkzeit"
    try:
        w, s = int(kopf["WhiteElo"]), int(kopf["BlackElo"])
    except (KeyError, ValueError):
        return False, "Wertung fehlt"
    if min(w, s) < MIN_ELO:
        return False, "Wertung unter Grenze"
    if kopf.get("Result") not in ERGEBNIS:
        return False, "kein gewertetes Ergebnis"
    if kopf.get("Termination") not in ("Normal", "Time forfeit"):
        return False, "Ende nicht normal"
    return True, ""


def material(board: chess.Board) -> tuple[int, int, int, int, int, int, int]:
    """(dP, dN, dB, dR, dQ, Läuferpaar Weiß, Läuferpaar Schwarz); Unterschiede Weiß minus Schwarz."""
    w, s = board.occupied_co[chess.WHITE], board.occupied_co[chess.BLACK]
    arten = (board.pawns, board.knights, board.bishops, board.rooks, board.queens)
    d = tuple((a & w).bit_count() - (a & s).bit_count() for a in arten)
    wb, sb = board.bishops & w, board.bishops & s
    wpaar = int(bool(wb & chess.BB_LIGHT_SQUARES) and bool(wb & chess.BB_DARK_SQUARES))
    spaar = int(bool(sb & chess.BB_LIGHT_SQUARES) and bool(sb & chess.BB_DARK_SQUARES))
    return (*d, wpaar, spaar)


def stellungen(zugtext: str, plies=PLIES):
    """Material der ruhigen Stellungen nach den angegebenen Halbzügen (nur gerade, Weiß am Zug) einer Partie."""
    spiel = chess.pgn.read_game(io.StringIO(zugtext))
    if spiel is None:
        return
    board = spiel.board()
    letzter = max(plies)
    for n, zug in enumerate(spiel.mainline_moves(), start=1):
        schlag = board.is_capture(zug)
        board.push(zug)
        if n in plies and not schlag and not board.is_check():
            yield n, material(board)
        if n >= letzter:
            break


def verarbeite(pfad: Path) -> dict:
    """Liest eine Datei und gibt Zählungen, Zellen und den Zeitraum der Partien zurück (läuft in einem eigenen Prozess)."""
    zaehl: Counter = Counter()
    zellen: Counter = Counter()
    erste = letzte = None
    for kopf, zugtext in partien(pfad):
        zaehl["Partien im Strom"] += 1
        zeit = (kopf.get("UTCDate", "?"), kopf.get("UTCTime", "?"))
        erste = zeit if erste is None or zeit < erste else erste
        letzte = zeit if letzte is None or zeit > letzte else letzte
        ok, grund = passt(kopf)
        if not ok:
            zaehl["abgelehnt: " + grund] += 1
            continue
        band = band_von(min(int(kopf["WhiteElo"]), int(kopf["BlackElo"])))
        zaehl["behalten"] += 1
        zaehl["behalten " + band] += 1
        ev = kopf["Event"].lower()
        if "tournament" in ev or "swiss" in ev:
            zaehl["davon Turnier-Event (Arena oder Swiss)"] += 1
        res = ERGEBNIS[kopf["Result"]]
        spalte = "win" if res == 1.0 else "draw" if res == 0.5 else "loss"
        for ply, mat in stellungen(zugtext):
            zaehl[f"Stellungen Halbzug {ply}"] += 1
            zellen[(band, ply, *mat, spalte)] += 1
    return {"datei": pfad.name, "bytes": pfad.stat().st_size, "zaehl": zaehl, "zellen": zellen, "erste": erste, "letzte": letzte}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("quellen", type=Path, nargs="+", help="eine oder mehrere (auch abgeschnittene) .pgn.zst-Dateien, die sich nicht überlappen")
    ap.add_argument("--ausgabe", type=Path, default=Path(__file__).resolve().parent.parent / "data")
    ap.add_argument("--quelle-name", default=None, help="Name der Originaldatei (für meta.json), Standard: Name der ersten Datei")
    ap.add_argument("--gesamtgroesse", type=int, default=None, help="Größe der Originaldatei in Bytes (nur für meta.json)")
    args = ap.parse_args()

    with ProcessPoolExecutor(max_workers=min(len(args.quellen), os.cpu_count() or 1)) as pool:
        ergebnisse = list(pool.map(verarbeite, args.quellen))
    zaehl: Counter = Counter()
    zellen: Counter = Counter()
    for e in ergebnisse:
        zaehl.update(e["zaehl"])
        zellen.update(e["zellen"])

    schluessel = sorted({k[:-1] for k in zellen}, key=lambda k: (k[0], k[1], k[2:]))
    args.ausgabe.mkdir(parents=True, exist_ok=True)
    with open(args.ausgabe / "stellungen.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(SPALTEN)
        for k in schluessel:
            w.writerow([*k, zellen.get((*k, "win"), 0), zellen.get((*k, "draw"), 0), zellen.get((*k, "loss"), 0)])
    meta = {
        "quelle": "https://database.lichess.org/ (Lichess-Datenbank, CC0)",
        "datei": args.quelle_name or args.quellen[0].name,
        "gesamtgroesse_bytes": args.gesamtgroesse,
        "abgerufene_bytes": sum(e["bytes"] for e in ergebnisse),
        "stuecke": [{"datei": e["datei"], "bytes": e["bytes"], "erste_partie_utc": " ".join(e["erste"]), "letzte_partie_utc": " ".join(e["letzte"])}
                    for e in ergebnisse],
        "filter": {"min_elo": MIN_ELO, "ereignis": "Event enthält Rapid oder Classical (ohne Correspondence), Einzel- und Turnierpartien",
                   "termination": ["Normal", "Time forfeit"], "halbzuege": list(PLIES),
                   "ruhig": "Anzugsseite nicht im Schach, letzter Zug kein Schlagzug"},
        "zaehlungen": dict(sorted(zaehl.items())),
        "zeilen_csv": len(schluessel),
        "python_chess": chess.__version__,
    }
    (args.ausgabe / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(meta["zaehlungen"], ensure_ascii=False, indent=2))
    print("CSV-Zeilen:", len(schluessel))


if __name__ == "__main__":
    main()
