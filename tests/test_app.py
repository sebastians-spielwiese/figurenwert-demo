"""AppTest-Rauchtests: Standard, jedes Preset, mehrere Halbzüge, Rechner. (AppTest löst keine Plotly-Klicks aus; Browser-Verifikation steht im README.)"""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import fw_constants as C

PFAD = str(Path(__file__).resolve().parent.parent / "app.py")


def neu() -> AppTest:
    at = AppTest.from_file(PFAD, default_timeout=60)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_standard_laeuft_und_zeigt_alle_bereiche():
    at = neu()
    assert at.title[0].value.startswith("♟️")
    assert [h.value for h in at.sidebar.header] == ["🎯 Schnellstart", "⚙️ Einstellungen"]
    assert {e.label for e in at.expander} >= {"📐 Mathematische Formulierung", "📊 Datenlage und Grenzen"}
    assert any(m.label == "Stellungen (je eine pro Partie und Halbzug)" for m in at.metric)


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_jedes_preset(name):
    at = neu()
    at.button(key=f"preset_{name}").click().run()
    assert not at.exception, [e.value for e in at.exception]
    p = C.PRESETS[name]
    assert at.session_state["fw_band"] == p["fw_band"]
    assert list(at.session_state["fw_plies"]) == p["fw_plies"]
    # aktives Preset hervorgehoben, die anderen nicht
    assert [b.proto.type for b in at.button if b.key == f"preset_{name}"] == ["primary"]


def verdikte(at) -> str:
    return " ".join(x.value for x in [*at.warning, *at.info, *at.success])


def test_preset_nur_ab_2400_alle_figuren_schaetzbar():
    at = neu()
    at.button(key="preset_Nur ab 2400").click().run()
    assert "Von 4 schätzbaren Figurenarten" in verdikte(at) and "Nicht schätzbar" not in verdikte(at)


def test_dame_in_klasse_ab_2200_bei_halbzug_20_nicht_schaetzbar():
    at = neu()
    at.radio(key="fw_band").set_value("2200–2399").run()
    at.multiselect(key="fw_plies").set_value([20]).run()
    assert "Nicht schätzbar: Dame" in verdikte(at) and "Von 3 schätzbaren Figurenarten" in verdikte(at)


def test_mehrere_halbzuege_zeigen_warnung():
    at = neu()
    at.button(key="preset_Alle Halbzüge zusammen").click().run()
    assert any("hängen zusammen" in w.value for w in at.warning)
    at2 = neu()
    assert not any("hängen zusammen" in w.value for w in at2.warning)


def test_rechner_gleiches_material_ist_anzugsvorteil_und_bauer_mehr_hebt():
    at = neu()
    p0 = next(m for m in at.metric if m.label == "Erwartete Punkte für Weiß").value
    at.slider(key="rech_dP").set_value(1).run()
    p1 = next(m for m in at.metric if m.label == "Erwartete Punkte für Weiß").value
    f = lambda s: float(s.replace(" %", "").replace(",", "."))
    assert f(p0) > 50 and f(p1) > f(p0)


def test_rechner_ohne_schaetzbares_merkmal_meldet_info():
    at = neu()
    at.radio(key="fw_band").set_value("2200–2399").run()
    at.multiselect(key="fw_plies").set_value([20]).run()
    at.slider(key="rech_dQ").set_value(1).run()
    assert any("nicht schätzbar" in i.value for i in at.info)
    assert not any(m.label == "Erwartete Punkte für Weiß" for m in at.metric)


def test_leere_halbzug_auswahl_haelt_an():
    at = neu()
    at.multiselect(key="fw_plies").set_value([]).run()
    assert not at.exception
    assert any("mindestens einen Halbzug" in w.value for w in at.warning)
