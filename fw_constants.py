"""Regler-Grenzen, Voreinstellungen und Beschriftungen. Jede Aussage der Hilfetexte steht in tests/test_claims.py (Klasse HilfetextTests)."""
from __future__ import annotations

import json
from pathlib import Path

BANDEN = ("Alle Klassen", "2000–2199", "2200–2399", "ab 2400")
HALBZUEGE = (20, 30, 40, 50, 60, 70, 80)
STANDARD = {"fw_band": "Alle Klassen", "fw_plies": [40], "fw_paar": True}
PRESETS = {
    "Alle Spieler, Halbzug 40": {"fw_band": "Alle Klassen", "fw_plies": [40], "fw_paar": True},
    "Nur 2000–2199": {"fw_band": "2000–2199", "fw_plies": [40], "fw_paar": True},
    "Nur ab 2400": {"fw_band": "ab 2400", "fw_plies": [40], "fw_paar": True},
    "Früh (Halbzug 20)": {"fw_band": "Alle Klassen", "fw_plies": [20], "fw_paar": True},
    "Spät (Halbzug 80)": {"fw_band": "Alle Klassen", "fw_plies": [80], "fw_paar": True},
    "Alle Halbzüge zusammen": {"fw_band": "Alle Klassen", "fw_plies": list(HALBZUEGE), "fw_paar": True},
}
PRESET_HELP = {
    "Alle Spieler, Halbzug 40": "Eine Stellung je Partie nach Halbzug 40. Mehrere Partien desselben Spielers werden nicht gesondert behandelt.",
    "Nur 2000–2199": "Der schwächere der beiden Spieler liegt zwischen 2000 und 2199, der andere ist mindestens so stark.",
    "Nur ab 2400": "Beide Spieler mindestens 2400: die kleinste Klasse. Alle Figuren sind bei Halbzug 40 schätzbar, aber die Bänder sind deutlich breiter als bei allen Klassen.",
    "Früh (Halbzug 20)": "Nach 10 Zügen ist in etwa sieben von zehn Stellungen das Material gleich. Die Dame ist in den Klassen ab 2200 nicht schätzbar.",
    "Spät (Halbzug 80)": "Nach 40 Zügen liegt die Schätzung aller vier Figuren unter der bei Halbzug 40 (alle Klassen).",
    "Alle Halbzüge zusammen": "Bis zu sieben Stellungen je Partie zusammen (Halbzug 20 bis 80, im Mittel 3,6): mehr Daten, aber die Fehlerbalken sind zu klein, weil Stellungen derselben Partie nicht unabhängig sind.",
}
RECHNER = (  # (Schlüssel, Beschriftung)
    ("dP", "Bauern"), ("dN", "Springer"), ("dB", "Läufer"), ("dR", "Türme"), ("dQ", "Damen"),
)
META = json.loads((Path(__file__).resolve().parent / "data" / "meta.json").read_text(encoding="utf-8"))
