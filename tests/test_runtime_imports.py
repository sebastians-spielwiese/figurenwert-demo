"""Jede Nicht-Standardbibliothek-Import der App steht in requirements.txt; `chess` (GPL) kommt in der App nicht vor."""
import ast
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
APP_DATEIEN = [WURZEL / "app.py", *sorted(WURZEL.glob("fw_*.py"))]
PAKETNAME = {"streamlit": "streamlit", "numpy": "numpy", "plotly": "plotly"}


def importe(pfad: Path) -> set[str]:
    baum = ast.parse(pfad.read_text(encoding="utf-8"))
    namen = set()
    for n in ast.walk(baum):
        if isinstance(n, ast.Import):
            namen |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            namen.add(n.module.split(".")[0])
    return namen


def test_laufzeitpakete_stehen_in_requirements():
    eigene = {p.stem for p in WURZEL.glob("*.py")}
    req = {z.split(">=")[0].strip().lower() for z in (WURZEL / "requirements.txt").read_text().splitlines() if z.strip() and not z.startswith("#")}
    for datei in APP_DATEIEN:
        fremd = {n for n in importe(datei) if n not in sys.stdlib_module_names and n not in eigene}
        assert fremd <= req, (datei.name, fremd - req)


def test_app_importiert_kein_python_chess():
    for datei in APP_DATEIEN:
        assert "chess" not in importe(datei), datei.name
    req = (WURZEL / "requirements.txt").read_text().lower()
    assert "chess" not in req
