# Wie viel ist eine Figur wert? (figurenwert-demo)

Interaktive Streamlit-Demo der [Sebastians Spielwiese](https://sebastians-spielwiese.net/) (Schach-Linie, Demo A). Sie schätzt aus echten
Online-Partien, wie viele Bauern eine Figur wert ist, und legt das Ergebnis neben die Faustregel **Bauer 1, Springer 3, Läufer 3, Turm 5, Dame 9**.

Lauffähig mit: `streamlit run app.py`

## Was die Demo zeigt

* **Geschätzter Wert je Figur** in Bauern, mit 95-%-Band, gegen die Faustregel (Schnellstart und Regler: Wertungsklasse, Halbzug, Läuferpaar).
* **Kernfrage:** Wie viele Punkte bringt Weiß ein Mehr an Material? Das Modell und die rohe, nur gezählte Quote stehen nebeneinander. Dazu ein **Rechner**: Materialunterschied einstellen, erwartete Punktequote ablesen.
* **Verdikt:** Bei wie vielen Figuren liegt die Faustregel im Band, wo nicht, was ist nicht schätzbar.
* Ausklappbar: Rechenregeln und Datenlage, beides aus denselben Zahlen wie diese README.

## Daten

* **Quelle:** Lichess-Datenbank, Datei `lichess_db_standard_rated_2026-10.pgn.zst` (30.982.323.881 Bytes), Lizenz CC0 (Hinweis auf <https://database.lichess.org/> im Seitenkopf: „Database exports are released under the Creative Commons CC0 license“).
* **Abruf:** sechs Stücke zu je 2 GiB (zusammen 12.884.901.888 Bytes) per HTTP-Bereichsanfrage; sie beginnen hinter 0, 5, 10, 15, 20 und 25 Milliarden Bytes der Datei, die fünf späteren an einer Zstandard-Frame-Grenze.
  Die Zeitfenster (UTC, 2026) stehen in `data/meta.json`: 1. Oktober 00:00 bis 3. Oktober 06:26, 6. Oktober 01:02 bis 8. Oktober 07:15, 11. Oktober bis 13. Oktober, 16. bis 18., 21. bis 23. und 26. bis 28. Oktober.
  Die Stichprobe deckt also rund 2,3 Tage je Stück ab und nicht den ganzen Monat. Die Rohdateien liegen nicht im Repo.
* **Umfang:** In den sechs Stücken stehen 39.575.722 Partien. Behalten werden Partien, deren Event „Rapid“ oder „Classical“ enthält (ohne Correspondence), mit beiden Wertungen ≥ 2000, gewertetem Ergebnis und Termination „Normal“ oder „Time forfeit“: **321.160 Partien**.
  12.636 davon sind Turnierpartien (Arena oder Swiss). Klassen (nach der **kleineren** der beiden Wertungen; der andere Spieler ist mindestens so stark): 2000–2199: 259.614, 2200–2399: 46.493, ab 2400: 15.053.
* **Stellungen:** Aus jeder behaltenen Partie die Stellung nach Halbzug 20, 30, 40, 50, 60, 70 und 80, sofern die Partie diesen Halbzug erreicht und die Stellung **ruhig** ist (Anzugsseite nicht im Schach, letzter Zug kein Schlagzug).
  Gezählt wurden 240.517, 212.622, 190.612, 165.786, 139.621, 114.203 und 91.926 Stellungen. Weiß ist in allen Stellungen am Zug.
* **Aggregation:** `tools/aggregiere.py` erzeugt `data/stellungen.csv` (17.725 Zeilen: Klasse, Halbzug, Materialunterschied je Figurenart, Läuferpaar je Seite, Zahl der Siege, Remis, Niederlagen aus Weißsicht) und `data/meta.json` mit allen Zählungen.
  Aufruf: `python tools/aggregiere.py <Stück1.pgn.zst> <Stück2.pgn.zst> … --quelle-name <Originaldatei> --gesamtgroesse <Bytes>` (Python 3.14, Zstandard aus der Standardbibliothek; braucht `chess`). Eine Partie, die mitten im Stück beginnt oder endet, wird verworfen.

## Methode

Zielgröße: Punkte von Weiß (Sieg 1, Remis ½). Modell: logistische Regression der Punkte auf den Materialunterschied (Weiß minus Schwarz: Bauern, Springer, Läufer, Türme, Damen) und das Läuferpaar (Läufer auf Feldern beider Farben, Weiß minus Schwarz), plus Achsenabschnitt.
Angepasst wird die Quasi-Binomial-Likelihood mit dem Newton-Verfahren (reines numpy, `fw_modell.py`); ein Remis zählt als halber Sieg. Der **Wert einer Figur** in Bauern ist ihr Koeffizient geteilt durch den Bauernkoeffizienten.
Standardfehler: Sandwich-Schätzer (HC0) aus den Zählungen, für den Quotienten die Delta-Methode; das 95-%-Band ist Wert ± 1,96 Standardfehler und ein Näherungsband aus der Normalverteilung, in kleinen Klassen kann es zu eng sein.
Ein Merkmal, das in weniger als 30 Stellungen der Auswahl von 0 abweicht, wird nicht angepasst („nicht schätzbar“). Das Modell ist linear im Materialunterschied; wo es von den gezählten Quoten abweicht, steht es unten.

## Befunde (alle Zahlen: diese Stichprobe, siehe Daten)

Jede Zahl wird in `tests/test_claims.py` nachgerechnet (Spalte „Test“).

| Aussage | Voraussetzung | Test |
|---|---|---|
| Springer 3,04 ± 0,05, Läufer 3,05 ± 0,05, Turm 4,49 ± 0,08, Dame 9,53 ± 0,18 Bauern; die Faustregel liegt bei Springer und Läufer im 95-%-Band, bei Turm und Dame nicht | Halbzug 40, alle Klassen, 190.612 Stellungen | `test_halbzug_40_alle_klassen` |
| 28 Auswahlen (4 Klassen × 7 Halbzüge) mal 4 Figuren = 112 Werte; 109 sind schätzbar, 3 nicht (alle Dame: Halbzug 20 in den Klassen 2200–2399 und ab 2400, Halbzug 30 ab 2400). Bei 62 der 109 liegt die Faustregel außerhalb des 95-%-Bands | alle 28 Auswahlen; sie überlappen (dieselben Partien in mehreren Halbzügen, die Klassen sind Teilmengen), die Zählung beschreibt nur | `test_raster_zaehlungen` |
| Bei Halbzug 40 bis 80 sind alle vier Figuren in allen vier Klassen schätzbar (80 Werte) | Schwelle 30 Stellungen | `test_halbzug_40_bis_80_alles_schaetzbar` |
| Stellungen mit Dame-Unterschied: 28 und 15 bei Halbzug 20 (2200–2399, ab 2400), 24 bei Halbzug 30 (ab 2400), sonst mindestens 82 je Auswahl | alle 28 Auswahlen | `test_dame_unterschiede_je_auswahl` |
| Turm in den Klassen 2000–2199 und 2200–2399: zwischen 4,06 und 4,55 Bauern, die 5 in allen 10 Auswahlen außerhalb des Bands | Halbzug 40 bis 80 | `test_turm_in_den_grossen_klassen_unter_fuenf` |
| Turm in der Klasse ab 2400: 6,41 / 4,92 / 5,06 / 5,88 / 6,10; die 5 liegt bei Halbzug 40, 50 und 60 im Band, bei 70 und 80 nicht | Halbzug 40 bis 80, 7.959 bis 10.452 Stellungen | `test_turm_ab_2400` |
| Springer, Läufer und Dame sinken von Halbzug 30 bis 80 bei jedem Schritt (Springer 3,21 → 2,71; Läufer 3,23 → 2,64; Dame 10,23 → 8,04); der Turm bleibt zwischen 4,20 und 4,55 | alle Klassen | `test_werte_sinken_mit_dem_halbzug` |
| In der Klasse ab 2400 liegen alle vier Werte als Punktschätzung höher als in 2000–2199 (20 von 20 Vergleichen); die 95-%-Bänder überlappen sich dabei nicht in 11 der 20 (Halbzug 70 und 80: alle 8, Halbzug 60: 3, Halbzug 40 und 50: keines von 8) | Halbzug 40 bis 80 | `test_klasse_ab_2400_hoeher` |
| Der Bauernkoeffizient wächst von 0,16 (Halbzug 20) über 0,28, 0,37, 0,44, 0,49 und 0,54 auf 0,57 (Halbzug 80), in Logit-Einheiten je Bauer | alle Klassen | `test_bauernkoeffizient_waechst_mit_dem_halbzug` |
| Bei gleichem Material erwartet das Modell für Weiß 52,0 bis 53,0 % der Punkte; roh (Stellungen mit exakt gleichem Material und gleichem Läuferpaar-Status) sind es 51,7 bis 52,3 % | alle Klassen, je Halbzug | `test_achsenabschnitt_gegen_rohe_quote` |
| Ein Bauer mehr: Modell 52,9 → 62,0 %, roh 51,7 % (56.738 Stellungen) → 63,7 % (12.542). Bei Halbzug 80 liegt das Modell bei 65,7 %, roh bei 68,4 % (8.105 Stellungen): das lineare Modell unterschätzt den Bauern dort | Halbzug 40 bzw. 80, alle Klassen | `test_bauer_mehr` |
| Läuferpaar +0,55 ± 0,04 Bauern; in 21 der 28 Auswahlen liegt sein 95-%-Band strikt über 0, in keiner strikt darunter; ab 2400 bei Halbzug 30 ist es −0,49 ± 0,49 | Halbzug 40, alle Klassen (erste Zahl); alle 28 Auswahlen (Zählung) | `test_laeuferpaar` |
| Ohne das Läuferpaar-Merkmal steigt der Läuferwert von 3,05 auf 3,37, der Springerwert bleibt bei 3,04 | Halbzug 40, alle Klassen | `test_ohne_laeuferpaar_steigt_der_laeuferwert` |
| Nach Halbzug 20 ist in 70 % der Stellungen das Material gleich (alle Klassen) | Halbzug 20 | `TestHilfetexte.test_frueh_sieben_von_zehn_gleiches_material` |
| In der Klasse ab 2400 sind die Standardfehler bei Halbzug 40 11,8- bis 13,2-mal so groß wie bei allen Klassen | Halbzug 40 | `TestHilfetexte.test_ab_2400_baender_deutlich_breiter` |
| Die Zählungen im Abschnitt „Daten“ | Aggregationslauf | `test_readme_zahlen_aus_meta`, `test_csv_und_meta_stimmen_ueberein` |

Was daraus **nicht** folgt:
* Die Faustregel „im Band“ heißt nur, dass die Daten ihr nicht widersprechen. Bei 190.612 Stellungen ist das Band eng (Springer ± 0,10), schon kleine Abweichungen liegen außerhalb; zur Größe der Abweichung zählen die Werte, nicht die Bandzählung.
* Dass der Turm in den Klassen 2000–2399 unter 5 Bauern liegt, gilt für diese Stichprobe (Rapid und Classical ab 2000, sechs Zeitfenster im Oktober 2026, ruhige Stellungen). Es sagt nichts über Blitz, Bullet oder Partien am Brett. Warum es so ist, wurde nicht untersucht; ebenso wenig, warum die Werte in der Klasse ab 2400 höher liegen.
* Mehrere Halbzüge zusammen zu fassen vergrößert die Datenmenge, aber Stellungen derselben Partie sind nicht unabhängig, die Fehlerbalken sind dann zu klein. Die Demo warnt dort. Wie groß der Fehler ist, misst die aggregierte Tabelle nicht (sie hat keine Partie-Kennung); eine Nachmessung des Prüfers außerhalb des Repos ergab für fünf Halbzüge (früherer Stand) den 1,3- bis 1,45-fachen, für alle sieben Halbzüge den 1,4- bis 1,6-fachen Standardfehler; dieser Faktor steht in keinem Test.
* Die Werte ändern sich mit dem Halbzug (siehe Zeile zu Springer, Läufer, Dame); alle Koeffizienten wachsen mit dem Halbzug. Ein Wert „in Bauern“ ist deshalb an einen Halbzug und an die Stichprobe gebunden.
* Eine Stellung je Partie heißt nicht, dass die Partien unabhängig sind: Spieler können mehrfach vorkommen. Das ist nicht bereinigt.

## Bewusst nicht enthalten

* Kein Stellungswert: Die Schätzung ist ein Durchschnitt über viele Stellungen. Dass ein Turm in einer bestimmten Stellung mehr oder weniger wiegt (offene Linien, Bauernstruktur), steht hier nicht.
* Keine Engine-Bewertung und keine Unterscheidung von Bedenkzeit-Stufen innerhalb von Rapid und Classical; Turnierpartien sind nicht herausgenommen.
* Keine Wertung nach Spielerfarbe getrennt über den Anzugsvorteil hinaus.
* Halbzug 20 und 30 in den oberen Klassen bleiben bei der Dame „nicht schätzbar“, weil dort fast keine Stellung einen Dame-Unterschied hat (15, 24 und 28 Stellungen); mehr Daten würden das ändern.

## Tests

`python -m pytest tests -q` (Test-venv, `requirements-dev.txt`): **65 Tests**. Orakel: Koeffizienten gegen `scikit-learn` (Remis als halber Sieg plus halbe Niederlage), Sandwich-Schätzer gegen eine Schleife über Einzelpartien,
Material gegen eine unabhängige Buchstabenzählung der FEN, Handrechnung für eine Zwei-Zellen-Anpassung (Achsenabschnitt und Bauernkoeffizient exakt aus den Logits),
Strom-Leser mit mehreren Zstandard-Frames, abgeschnittenem Anfang und Ende, AppTest für jedes Preset. Ein unabhängiger Prüfer hat die Fassung mit einer Stichprobe vom Monatsanfang (1 GiB) gegengerechnet (Aggregation, Köpfe-Zählung, Koeffizienten, Sandwich, Delta-Methode, Bootstrap); seine Befunde zu den Texten sind eingearbeitet, die neue Fassung mit sechs Stücken ist nicht noch einmal komplett geprüft.

## Lizenzen

* Daten: CC0 (Lichess-Datenbank).
* `chess` (python-chess, GPL-3.0 oder neuer) wird nur im Aggregationsskript und in den Tests benutzt, steht in `requirements-dev.txt` und **nicht** in `requirements.txt`; die App importiert es nicht (`tests/test_runtime_imports.py`).
* Lizenz des eigenen Codes: noch nicht festgelegt.
