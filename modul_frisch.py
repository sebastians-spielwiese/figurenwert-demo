"""Hilfsmodule der Demo neu laden, wenn sich ihre Datei geändert hat (nur Standardbibliothek).

Hintergrund: Die Streamlit Community Cloud führt `app.py` bei jedem Lauf neu aus, behält aber die Hilfsmodule, die der Prozess einmal importiert hat. Nach einem Push
mit geänderten Hilfsmodulen lief die App deshalb mit neuer `app.py` und alten Modulen weiter, bis jemand sie im Dashboard neu startete. `aktualisieren(__file__)` steht in
`app.py` hinter den eigenen Imports und lädt die Module des App-Ordners neu, sobald eines geändert ist (Abhängigkeiten zuerst), ohne den Prozess neu zu starten.

Grenzen: Wer `from modul import name` schreibt, behält den alten Wert; die Demos benutzen `import modul as kürzel`. Zustand im Modul (Caches mit `st.cache_*` in `app.py` eingeschlossen)
bleibt nicht erhalten, wenn das Modul neu geladen wird. Diese Datei selbst wird nie neu geladen.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

_STAND: dict[str, int] = {}          # Modulname -> Änderungszeit (ns) der Datei beim letzten Lauf


def lokale_module(app_datei: str) -> dict:
    """Modulname -> (Modul, Änderungszeit) aller bereits importierten Module, die als .py-Datei im Ordner der App liegen."""
    ordner = Path(app_datei).resolve().parent
    eigen = Path(__file__).resolve().name
    gefunden = {}
    for name, modul in list(sys.modules.items()):
        datei = getattr(modul, "__file__", None)
        if not datei or name == "__main__":
            continue
        try:
            pfad = Path(datei).resolve()
            if pfad.parent == ordner and pfad.suffix == ".py" and pfad.name != eigen:
                gefunden[name] = (modul, pfad.stat().st_mtime_ns)
        except OSError:
            continue
    return gefunden


def reihenfolge(module: dict) -> list[str]:
    """Modulnamen so geordnet, dass jedes Modul nach den Modulen kommt, von denen es etwas benutzt (Modulobjekt oder Name im Namensraum, auch `from m import f`).
    Die Reihenfolge in sys.modules taugt dafür nicht: Sie hängt von der Python-Version ab."""
    nach_objekt = {id(m): n for n, (m, _) in module.items()}
    abhaengig: dict[str, set[str]] = {}
    for name, (modul, _) in module.items():
        ziele = set()
        for wert in vars(modul).values():
            if id(wert) in nach_objekt:                                  # import m as alias
                ziele.add(nach_objekt[id(wert)])
            herkunft = getattr(wert, "__module__", None)                  # from m import f, Klasse
            if isinstance(herkunft, str) and herkunft in module:
                ziele.add(herkunft)
        ziele.discard(name)
        abhaengig[name] = ziele
    fertig: list[str] = []
    besucht: set[str] = set()

    def besuche(n: str) -> None:
        if n in besucht:
            return
        besucht.add(n)                                                    # Zyklen: nicht erneut hineinlaufen
        for z in sorted(abhaengig[n]):
            besuche(z)
        fertig.append(n)

    for n in sorted(module):
        besuche(n)
    return fertig


def aktualisieren(app_datei: str) -> list[str]:
    """Lädt die geänderten Module des App-Ordners neu und nennt ihre Namen. Beim ersten Aufruf wird nur der Stand gemerkt."""
    module = lokale_module(app_datei)
    geaendert = [n for n, (_, t) in module.items() if n in _STAND and _STAND[n] != t]
    if geaendert:
        for name in reihenfolge(module):
            importlib.reload(module[name][0])
    for name, (_, t) in module.items():
        _STAND[name] = t
    return geaendert
