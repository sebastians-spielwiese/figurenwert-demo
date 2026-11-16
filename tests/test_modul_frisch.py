"""modul_frisch: geänderte Hilfsmodule werden neu geladen, ungeänderte nicht; Abhängigkeiten werden zuerst neu geladen."""
import importlib
import os
import sys
import uuid

import pytest

import modul_frisch as MF


@pytest.fixture
def app_ordner(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(tmp_path))
    vorher = dict(MF._STAND)
    yield tmp_path
    for name in [n for n in sys.modules if n.startswith("mf_")]:
        del sys.modules[name]
    MF._STAND.clear()
    MF._STAND.update(vorher)


def schreibe(ordner, name, text, zeit=None):
    pfad = ordner / f"{name}.py"
    pfad.write_text(text, encoding="utf-8")
    if zeit is not None:
        os.utime(pfad, ns=(zeit, zeit))
    return pfad


def neue_namen():
    s = uuid.uuid4().hex[:8]
    return f"mf_basis_{s}", f"mf_ober_{s}"


def test_erster_aufruf_merkt_nur_den_stand(app_ordner):
    basis, ober = neue_namen()
    schreibe(app_ordner, basis, "WERT = 1\n", 10**18)
    importlib.import_module(basis)
    assert MF.aktualisieren(str(app_ordner / "app.py")) == []
    assert basis in MF._STAND


def test_geaenderte_datei_wird_neu_geladen(app_ordner):
    basis, _ = neue_namen()
    schreibe(app_ordner, basis, "WERT = 1\n", 10**18)
    m = importlib.import_module(basis)
    MF.aktualisieren(str(app_ordner / "app.py"))
    schreibe(app_ordner, basis, "WERT = 2\n", 10**18 + 5_000_000_000)
    assert m.WERT == 1
    assert MF.aktualisieren(str(app_ordner / "app.py")) == [basis]
    assert m.WERT == 2                                       # dasselbe Modulobjekt, neu ausgeführt: `import x as y` im Skript sieht den neuen Stand


def test_ungeaenderte_module_werden_nicht_neu_geladen(app_ordner):
    basis, _ = neue_namen()
    schreibe(app_ordner, basis, "import itertools\nZAEHLER = next(itertools.count())\nGELADEN = []\nGELADEN.append(1)\n", 10**18)
    m = importlib.import_module(basis)
    MF.aktualisieren(str(app_ordner / "app.py"))
    m.GELADEN.append("marke")
    assert MF.aktualisieren(str(app_ordner / "app.py")) == []
    assert m.GELADEN == [1, "marke"]                         # ein Neuladen hätte die Liste zurückgesetzt


def test_abhaengigkeit_wird_vor_dem_abhaengigen_neu_geladen(app_ordner):
    basis, ober = neue_namen()
    schreibe(app_ordner, basis, "WERT = 1\n", 10**18)
    schreibe(app_ordner, ober, f"import {basis} as B\nABGELEITET = B.WERT * 10\n", 10**18)
    o = importlib.import_module(ober)
    MF.aktualisieren(str(app_ordner / "app.py"))
    assert o.ABGELEITET == 10
    schreibe(app_ordner, basis, "WERT = 3\n", 10**18 + 5_000_000_000)
    assert MF.aktualisieren(str(app_ordner / "app.py")) == [basis]
    assert o.ABGELEITET == 30                                # der Abhängige wurde nach der Basis neu ausgeführt


def test_module_ausserhalb_des_app_ordners_bleiben_unberuehrt(app_ordner, tmp_path_factory):
    fremd = tmp_path_factory.mktemp("fremd")
    s = uuid.uuid4().hex[:8]
    name = f"mf_fremd_{s}"
    schreibe(fremd, name, "WERT = 1\n", 10**18)
    sys.path.insert(0, str(fremd))
    try:
        importlib.import_module(name)
        assert name not in MF.lokale_module(str(app_ordner / "app.py"))
    finally:
        sys.path.remove(str(fremd))


def test_eigenes_modul_wird_nie_neu_geladen(app_ordner):
    import pathlib
    assert "modul_frisch" not in MF.lokale_module(str(pathlib.Path(MF.__file__).parent / "app.py"))


def test_from_import_wird_durch_neues_laden_des_abhaengigen_aktualisiert(app_ordner):
    basis, ober = neue_namen()
    schreibe(app_ordner, basis, "def f():\n    return 1\n", 10**18)
    schreibe(app_ordner, ober, f"from {basis} import f\nERGEBNIS = f()\n", 10**18)
    o = importlib.import_module(ober)
    MF.aktualisieren(str(app_ordner / "app.py"))
    schreibe(app_ordner, basis, "def f():\n    return 2\n", 10**18 + 5_000_000_000)
    assert MF.aktualisieren(str(app_ordner / "app.py")) == [basis]
    assert o.ERGEBNIS == 2 and MF.reihenfolge(MF.lokale_module(str(app_ordner / "app.py"))).index(basis) < MF.reihenfolge(MF.lokale_module(str(app_ordner / "app.py"))).index(ober)
