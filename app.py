"""
Wie viel ist eine Figur wert? Figurenwerte aus echten Partien geschätzt: logistische Regression auf dem Materialunterschied.
Sebastians Spielwiese - Demo A der Schach-Linie

Aus ruhigen Stellungen von Rapid- und Classical-Partien der Lichess-Datenbank (beide Spieler mindestens 2000) wird geschätzt, wie stark ein
Mehr an Springer, Läufer, Turm oder Dame die Punkte von Weiß erhöht, gemessen in Bauern. Das Ergebnis steht neben der Faustregel 1 / 3 / 3 / 5 / 9.

Lauffähig mit: streamlit run app.py
"""
import numpy as np
import streamlit as st

import fw_auswertung as AU
import fw_constants as C
import fw_modell as M
import fw_visualisierung as V
import modul_frisch

modul_frisch.aktualisieren(__file__)      # geänderte Hilfsmodule nach einem Update neu laden (Cloud behält sie sonst bis zum Neustart)

st.set_page_config(page_title="Figurenwert – Sebastians Spielwiese", layout="wide")


@st.cache_data(show_spinner=False)
def _tabelle():
    return M.laden()


@st.cache_data(show_spinner=False, max_entries=64)
def _anpassung(band: str, plies: tuple, paar: bool):
    t = M.auswahl(_tabelle(), None if band == "Alle Klassen" else band, plies)
    return M.anpassen(t, mit_laeuferpaar=paar)


_fmt = AU.de


def _apply_preset(name: str) -> None:
    for k, v in C.PRESETS[name].items():
        st.session_state[k] = list(v) if isinstance(v, list) else v


for _k, _v in C.STANDARD.items():
    st.session_state.setdefault(_k, list(_v) if isinstance(_v, list) else _v)

st.title("♟️ Wie viel ist eine Figur wert?")
st.markdown(
    """
Die Faustregel sagt: **Bauer 1, Springer 3, Läufer 3, Turm 5, Dame 9**. Hier prüfst Du sie an echten Partien. Aus ruhigen Stellungen von
**Rapid- und Classical-Partien** der Lichess-Datenbank (beide Spieler mindestens 2000) schätzt eine **logistische Regression**, wie viele
Punkte ein Mehr an Material für Weiß bringt. Ein Bauer ist der Maßstab, die anderen Figuren werden in Bauern gemessen. Unten stehen
**Fehlerbalken**, ein **Rechner** für eine Stellung Deiner Wahl, die **Rechenregeln** und die **Grenzen der Daten**.
"""
)

with st.sidebar:
    st.header("🎯 Schnellstart")
    st.caption("Eine Auswahl laden: Wertungsklasse und Halbzug werden gesetzt.")
    aktiv_name = next((n for n, p in C.PRESETS.items() if all(st.session_state.get(k) == v for k, v in p.items())), None)
    for name in C.PRESETS:
        st.button(name, key=f"preset_{name}", width="stretch", on_click=_apply_preset, args=(name,),
                  help=C.PRESET_HELP.get(name, ""), type="primary" if name == aktiv_name else "secondary")
    st.header("⚙️ Einstellungen")
    st.radio("Wertungsklasse (kleinere der beiden Wertungen)", C.BANDEN, key="fw_band")
    st.multiselect("Halbzug der Stellung", C.HALBZUEGE, key="fw_plies",
                   help="Gemessen nach diesem Halbzug, Weiß ist am Zug. Mehrere Halbzüge: dieselbe Partie zählt mehrfach.")
    st.checkbox("Läuferpaar als eigenes Merkmal", key="fw_paar",
                help="Zuschlag für zwei Läufer auf Feldern beider Farben, zusätzlich zum Läuferwert.")

plies = tuple(sorted(st.session_state["fw_plies"]))
if not plies:
    st.warning("Wähle in der Seitenleiste mindestens einen Halbzug.")
    st.stop()
band, paar = st.session_state["fw_band"], bool(st.session_state["fw_paar"])
erg = _anpassung(band, plies, paar)
zeilen = AU.vergleich(erg, paar)

st.header("Ergebnis: geschätzter Wert in Bauern")
c1, c2, c3 = st.columns(3)
c1.metric("Stellungen (je eine pro Partie und Halbzug)", f"{int(erg.n):,}".replace(",", "."))
c2.metric("Wertungsklasse", band)
c3.metric("Halbzüge", ", ".join(str(p) for p in plies))
if len(plies) > 1:
    st.warning("Mehrere Halbzüge gewählt: Stellungen derselben Partie hängen zusammen, die Fehlerbalken sind zu klein.")
if not erg.konvergiert:
    st.error("Das Newton-Verfahren ist nicht konvergiert; die Zahlen sind nicht verlässlich.")

st.plotly_chart(V.werte_figur(zeilen), width="stretch", config={"displayModeBar": False})
st.caption("Punkte: Schätzung mit 95-%-Band (± 1,96 Standardfehler). Rauten: Faustregel. Der Bauer ist der Maßstab (= 1) und nicht eingezeichnet.")

tabelle = [{"Figur": r.figur, "Schätzung (Bauern)": _fmt(r.wert), "Standardfehler": _fmt(r.se),
            "95-%-Band": "–" if r.im_band is None or r.figur == "Bauer" else f"{_fmt(r.unten)} bis {_fmt(r.oben)}",
            "Faustregel": f"{r.faust:.0f}",
            "Faustregel im Band": "Maßstab" if r.figur == "Bauer" else ("nicht schätzbar" if r.im_band is None else ("ja" if r.im_band else "nein"))}
           for r in zeilen]
lp = AU.laeuferpaar(erg) if paar else None
if paar:
    tabelle.append({"Figur": "Läuferpaar (Zuschlag)", "Schätzung (Bauern)": _fmt(lp[0]) if lp else "–", "Standardfehler": _fmt(lp[1]) if lp else "–",
                    "95-%-Band": f"{_fmt(lp[0] - AU.Z95 * lp[1])} bis {_fmt(lp[0] + AU.Z95 * lp[1])}" if lp else "–", "Faustregel": "–",
                    "Faustregel im Band": "–" if lp else "nicht schätzbar"})
st.dataframe(tabelle, hide_index=True, width="stretch")

stufe, text = AU.verdikt(zeilen)
getattr(st, stufe)(text)

st.header("Kernfrage: Wie viele Punkte bringt ein Mehr an Material?")
b = np.where(erg.aktiv, erg.beta, np.nan)
st.markdown(
    "Weiß ist am Zug und die Stellung ist ruhig. Bei **gleichem Material** erwartet das Modell für Weiß "
    + (f"**{AU.de(100 / (1 + np.exp(-b[0])), 1)} %** der Punkte (Sieg 1, Remis ½)" if erg.aktiv[0] else "keine Punktequote")
    + ". Das ist der Achsenabschnitt des Modells (Vorteil von Weiß am Zug in dieser Datenlage), kein Wert einer Figur."
)
_sel = M.auswahl(_tabelle(), None if band == "Alle Klassen" else band, plies)
_r0, _n0 = AU.rohe_quote(_sel, 0)
_r1, _n1 = AU.rohe_quote(_sel, 1)
if erg.aktiv[1]:
    p1 = AU.erwartete_punkte(erg, {"dP": 1})
    st.markdown(
        f"Bei **einem Bauern mehr** (sonst gleiches Material) erwartet das Modell für Weiß **{AU.de(100 * p1, 1)} %**. "
        f"Ohne Modell, nur gezählt: {AU.de(100 * _r1, 1)} % in {f'{_n1:,}'.replace(',', '.')} Stellungen mit einem Bauern mehr gegen "
        f"{AU.de(100 * _r0, 1)} % in {f'{_n0:,}'.replace(',', '.')} Stellungen mit gleichem Material."
    )

st.subheader("🧮 Rechne selbst")
st.caption("Stell den Materialunterschied ein (Weiß minus Schwarz). Das Modell sagt, wie viele Punkte Weiß erwartet. Gilt für die links gewählte Auswahl.")
cols = st.columns(len(C.RECHNER) + 1)
d = {}
for col, (schl, name) in zip(cols, C.RECHNER):
    d[schl] = col.slider(name, -3, 3, 0, key=f"rech_{schl}")
if paar:
    d["LP"] = cols[-1].select_slider("Läuferpaar", options=[-1, 0, 1], value=0, key="rech_LP",
                                     format_func=lambda v: {-1: "nur Schwarz", 0: "beide / keiner", 1: "nur Weiß"}[v])
p = AU.erwartete_punkte(erg, d)
if p is None:
    st.info("Für diese Stellung fehlt ein Merkmal, das in der gewählten Auswahl nicht schätzbar ist. Wähle mehr Daten (links) oder lass das Merkmal bei 0.")
else:
    st.metric("Erwartete Punkte für Weiß", f"{AU.de(100 * p, 1)} %")

with st.expander("📐 Mathematische Formulierung"):
    st.markdown(
        r"""
**Lesehilfe.** Gegeben sind Stellungen mit dem Materialunterschied $d$ (Weiß minus Schwarz) und dem Partieergebnis aus Weißsicht
(1, ½ oder 0). Gesucht sind Koeffizienten $b$, mit denen sich die erwarteten Punkte aus dem Material vorhersagen lassen.

| Symbol | Bedeutung |
|---|---|
| $d_P, d_N, d_B, d_R, d_Q$ | Bauern-, Springer-, Läufer-, Turm-, Dameunterschied (Weiß minus Schwarz) |
| $d_L$ | Läuferpaar Weiß minus Läuferpaar Schwarz (je 0 oder 1) |
| $b_0$ | Achsenabschnitt: Logit der erwarteten Punkte von Weiß (am Zug) bei gleichem Material |
| $b_P, b_N, \dots$ | Koeffizienten je Merkmal (logit-Einheiten pro Stück) |
| $v_X$ | Wert der Figur $X$ in Bauern, $v_X = b_X / b_P$ |

$$
p = \frac{1}{1 + e^{-(b_0 + b_P d_P + b_N d_N + b_B d_B + b_R d_R + b_Q d_Q + b_L d_L)}}
$$

$$
v_X = \frac{b_X}{b_P}
$$

Angepasst wird die Quasi-Binomial-Likelihood, in der ein Remis als halber Sieg zählt, mit dem Newton-Verfahren. Die Standardfehler kommen
aus dem Sandwich-Schätzer (HC0), der die tatsächliche Streuung der Punkte nutzt; für $v_X$ gilt die Delta-Methode. Das 95-%-Band ist
$v_X \pm 1{,}96 \cdot \mathrm{SE}$.
"""
    )

with st.expander("📊 Datenlage und Grenzen"):
    z = C.META["zaehlungen"]

    def _n(k: str) -> str:
        return f"{z[k]:,}".replace(",", ".")

    def _tag(utc: str) -> str:
        d, zeit = utc.split()
        return f"{int(d[8:])}.{int(d[5:7])}., {zeit[:5]} Uhr"

    stuecke = "; ".join(f"{_tag(s['erste_partie_utc'])} bis {_tag(s['letzte_partie_utc'])}" for s in C.META["stuecke"])
    st.markdown(
        f"""
* **Quelle:** Lichess-Datenbank (CC0), Datei `{C.META['datei']}` ({AU.de(C.META['gesamtgroesse_bytes'] / 1e9, 1)} GB). Abgerufen wurden {len(C.META['stuecke'])} Stücke zu je 2 GiB
  ({AU.de(C.META['abgerufene_bytes'] / 1e9, 1)} GB zusammen), verteilt über den Monat; die Zeitfenster (UTC, 2026): {stuecke}.
  Darin standen {_n('Partien im Strom')} Partien, **{_n('behalten')}** davon bleiben (Event mit Rapid oder Classical, beide Spieler mindestens {C.META['filter']['min_elo']},
  Ende „normal“ oder Zeitüberschreitung). {_n('davon Turnier-Event (Arena oder Swiss)')} davon sind Turnierpartien.
* **Klassen** (nach der kleineren der beiden Wertungen): 2000–2199: {_n('behalten 2000–2199')} Partien, 2200–2399: {_n('behalten 2200–2399')}, ab 2400: {_n('behalten ab 2400')}.
* **Stellungen:** Halbzug 20: {_n('Stellungen Halbzug 20')}, 30: {_n('Stellungen Halbzug 30')}, 40: {_n('Stellungen Halbzug 40')}, 50: {_n('Stellungen Halbzug 50')},
  60: {_n('Stellungen Halbzug 60')}, 70: {_n('Stellungen Halbzug 70')}, 80: {_n('Stellungen Halbzug 80')}. Nur ruhige Stellungen (Anzugsseite nicht im Schach,
  letzter Zug kein Schlagzug) und nur Partien, die den Halbzug erreichen.
* **Nicht schätzbar** heißt: Das Merkmal weicht in weniger als {M.MIN_BESETZUNG} Stellungen der Auswahl von 0 ab.
* **Das Band** (± 1,96 Standardfehler) ist ein Näherungsband aus der Normalverteilung; in den kleinen Klassen kann es zu eng sein.
* **Was die Zahlen nicht sagen:** Sie beschreiben diese Stichprobe (Online-Partien im Oktober 2026, zwei Bedenkzeit-Arten), keine Partien am Brett und nicht
  jede Spielstärke. Der Wert einer Figur hängt an der Stellung; hier steht ein Durchschnitt über viele Stellungen.
"""
    )

st.markdown("---")
st.caption("Teil von [Sebastians Spielwiese](https://sebastians-spielwiese.net/) · Daten: Lichess-Datenbank (CC0) · Quelltext und Aggregation im Repo.")
