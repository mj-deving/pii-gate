---
task: "pii-gate: deutsche Texte vor einem gehosteten Modell pseudonymisieren, Antwort zurückübersetzen, Lecks je Entitätstyp gemessen"
slug: 20261119_pii-gate
project: pii-gate
effort: advanced
effort_source: inferred
phase: climbing
progress: 16/16
mode: interactive
started: 2026-11-19T18:30:00+01:00
updated: 2026-11-19T18:30:00+01:00
principal_stated_goal: "pii-gate bauen" (auf den Vorschlag: pseudonymisieren vor einem gehosteten Modell, Recall je Entitätstyp)
absence_review: pending
---

> **Über diese Datei.** Das ist die ISA (Ideal State Artifact), gegen die dieses Repo gebaut wurde:
> was „fertig“ hieß, mit welcher Probe jedes Kriterium widerlegt würde und was bewusst als Grenze
> stehen blieb. Es ist der Arbeitsstand aus dem Bau, nur um private Bezüge bereinigt; Hinweise wie
> „Push nur nach Go“ oder „ISA.md gitignored“ beschreiben die Zeit vor der Veröffentlichung. Die
> Leak-Probes lesen ihre Begriffe aus einer lokalen, nicht versionierten Datei `.private-terms`.

## Ideal State

### L3 · One sentence

Ein Engineering-Lead einer Versicherung sieht in einem Repo, wie personenbezogene Daten aus deutschen Texten entfernt werden, bevor ein gehostetes Modell sie sieht, wie die Antwort wieder zurückübersetzt wird, und wie viel je Entitätstyp trotzdem durchrutscht, ehrlich gemessen.

### L2 · Summary

Eine kleine Python-Bibliothek mit CLI ersetzt Namen, Adressen, IBANs, E-Mails, Telefonnummern, Geburtsdaten und Steuer-IDs durch stabile Platzhalter, schickt nur den maskierten Text weiter und setzt die Originale in der Antwort wieder ein.

- Zwei Detektoren: deterministische Muster mit Prüfziffern, wo es sie gibt (IBAN mod 97, Steuer-ID ISO 7064), und ein lokales Modell für Namen und freie Adressen; ein Modell-Fund zählt nur, wenn er wörtlich im Text steht.
- Gemessen wird das Leck, nicht die Genauigkeit: Anteil echter PII-Spans je Typ, die unmaskiert bleiben, mit Wilson-Intervall, für Regex allein, Modell allein und beide zusammen.
- Golden-Set für die Entwicklung, ein blind geschriebenes Held-out-Set genau einmal; eine Mutationsprobe zeigt, dass der Eval ein abgeschaltetes Muster findet.
- Lokal, ohne API-Key; der Rückweg ist verlustfrei getestet.

### L1 · Full articulation

Vor jedem gehosteten Modell steht in einer regulierten Firma dieselbe Frage: Was davon darf das Haus verlassen? Pseudonymisierung beantwortet sie nur, wenn man weiß, was sie übersieht. Das Repo zeigt deshalb keinen Detektor mit hübscher F1, sondern eine Leck-Tabelle je Entitätstyp: Strukturierte Daten mit Prüfziffer fängt ein Muster fast sicher, Namen nicht; das Modell schließt einen Teil der Lücke und kostet Zeit. Die Zahlen stehen neben ihren Grenzen (synthetische Texte, ein Modell, eine Maschine, Pseudonymisierung ist keine Anonymisierung). `uv run pytest` läuft ohne Modell, der Eval mit einem Befehl.

## Constraints

- Python 3.13 mit uv, Pydantic v2, httpx, pytest, ruff, pyright; keine globale Installation, kein `uvx`.
- Lokales Modell `qwen3:8b` über Ollama mit JSON-Schema-`format`; jeder Eval-Lauf unter einem gemeinsamen Ollama-Lock.
- Nur synthetische Personen, Adressen, IBANs (gültige Prüfziffer aus Test-Bankleitzahlen) und Steuer-IDs (gültige Prüfziffer, erfundene Ziffern).
- ISA.md gitignored; Repo ohne private Bezüge; Push nur nach Go des Maintainers.

## Criteria

- [x] ISC-1: `gate(text)` liefert maskierten Text und Zuordnung; gleicher Wert und Typ ergibt im selben Text denselben Platzhalter (`[PERSON_1]`), verschiedene Werte verschiedene.
- [x] ISC-2: `restore(answer, mapping)` setzt alle Platzhalter einer Modellantwort zurück; Rundweg `restore(gate(t).text) == t` für jeden Golden-Text.
- [x] ISC-3: Muster-Detektor für EMAIL, PHONE, IBAN, TAX_ID, BIRTHDATE (Datum mit Geburts-Hinweis), ADDRESS (Straße mit Hausnummer, PLZ mit Ort). IBAN-förmige Strings werden auch mit falscher Prüfziffer maskiert (vertippt bleibt personenbezogen); eine elfstellige Zahl gilt als Steuer-ID bei gültiger ISO-7064-Prüfziffer oder Hinweiswort davor, sonst nicht (Rechnungsnummern).
- [x] ISC-4: Modell-Detektor liefert Typ und wörtlichen Text; ein Fund, der nicht an Token-Grenzen im Eingabetext steht, wird verworfen.
- [x] ISC-5: Überlappende Funde werden zum längsten Span vereinigt; kein Platzhalter steht mitten in einem Wort.
- [x] ISC-6: Golden-Set per Seed reproduzierbar, ≥ 50 Texte mit Span-Labels aus der Konstruktion, jeder Typ ≥ 15 Mal, inklusive Lockvögel ohne PII (Rechnungsnummern, IBAN mit falscher Prüfziffer, Daten ohne Geburtsbezug).
- [x] ISC-7: Held-out-Set (≥ 16 Texte) von einem Agenten ohne Zugriff auf Code und Golden-Set geschrieben, Labels inline (`⟦TYPE|text⟧`), genau einmal gelaufen, Ergebnis unverändert berichtet.
- [x] ISC-8: Eval schreibt `results/<set>.json` mit Leckquote je Typ und gesamt (Wilson 95 %), Überschuss-Maskierung (maskierte Spans ohne Label), Sekunden je Text, für `regex`, `llm` und `both`.
- [x] ISC-9: Leck zählt pro Label-Span, wenn irgendeines seiner Zeichen in irgendeinem von k = 3 Läufen unmaskiert bleibt.
- [x] ISC-10: Mutationsprobe: IBAN-Muster abgeschaltet ⇒ IBAN-Leckquote > 0 im Eval; als Test im Repo.
- [x] ISC-11: `uv run pytest`, `ruff check`, `pyright` grün ohne Modell und ohne Ollama.
- [x] ISC-12: README mit Quickstart, Method, Results (inkl. Fehlschläge), Limits; jede Zahl steht in `results/`.
- [x] ISC-13: Anti: Pseudonymisierung wird nirgends als Anonymisierung bezeichnet; README nennt, dass die Zuordnung personenbezogen bleibt.
- [x] ISC-14: Anti: keine privaten Bezüge, Secrets, absoluten Nutzerpfade oder echten Personendaten im Repo.
- [x] ISC-15: Anti: nach dem Held-out-Lauf keine Änderung an Mustern, Prompt oder Schwellen, ohne das Set als verbraucht zu markieren.
- [x] ISC-16: Commit erst nach autoreview `--engine claude`; offene P1 sind behoben oder im README als bekannte Klasse benannt.

## Test Strategy

| isc | type | check | threshold | tool | anchors_to |
|-----|------|-------|-----------|------|------------|
| ISC-1 | bash | Platzhalter-Konsistenz | grün | uv run pytest -k placeholder | src/pii_gate/gate.py |
| ISC-2 | bash | Rundweg über Golden | alle gleich | uv run pytest -k roundtrip | |
| ISC-3 | bash | Muster je Typ inkl. falscher Prüfziffer | grün | uv run pytest -k pattern | ISO 13616, ISO 7064 |
| ISC-4 | bash | erfundener Modell-Fund verworfen | grün | uv run pytest -k llm | |
| ISC-5 | bash | Überlappung, Wortgrenze | grün | uv run pytest -k overlap | |
| ISC-6 | bash | Seed-Hash, Typ-Zählung, Lockvögel | ≥ 15 je Typ | uv run pytest -k data | data/ |
| ISC-7 | manual | Brief ohne Code-Zugriff, ein Lauf | einmal | results/heldout-v1.json | |
| ISC-8 | bash | Ergebnisfelder | vorhanden | `jq 'keys' results/golden.json` | |
| ISC-9 | bash | Leck in Lauf 2 zählt | grün | uv run pytest -k leak | |
| ISC-10 | bash | Mutation | rot erkannt | uv run pytest -k mutation | |
| ISC-11 | bash | Suite offline | exit 0 | `OLLAMA_URL=http://127.0.0.1:9 uv run pytest` | .github/workflows/ci.yml |
| ISC-12 | bash | README-Abschnitte | 4 | `rg "^## (Quickstart\|Method\|Results\|Limits)" README.md` | |
| ISC-13 | bash | Wortwahl | 0 Treffer "anonymi" außer Abgrenzung | `rg -n -i anonymi README.md` | |
| ISC-14 | bash | Leak-Scan | 0 Treffer | `git ls-files -z \| xargs -0 rg -il -f .private-terms` | |
| ISC-15 | manual | Git-Log nach Held-out | keine Muster-/Prompt-Änderung | git log -- src/ | |
| ISC-16 | manual | autoreview-Ausgabe | 0 offene P1 | autoreview `--engine claude` | |

## Decisions

- 2026-11-19: Kennzahl ist die Leckquote je Typ, nicht F1: ein übersehener Name geht zum Anbieter, ein überflüssig maskiertes Wort kostet nur Antwortqualität. Überschuss-Maskierung wird trotzdem berichtet.
- 2026-11-19: Bibliothek plus CLI, kein HTTP-Endpoint: claims-extract zeigt FastAPI schon; hier zählt der Gate-Vertrag (`gate`/`restore`).
- 2026-11-19: L3/L2 im Chat gezeigt, Bau beginnt sofort (Maintainer: "pii-gate bauen"); default-unratified.
- 2026-11-19: Held-out vor dem ersten Code-Zeichen in Auftrag gegeben (Sonnet, nur Ausgabedatei schreiben): 20 Texte, PERSON 40, ADDRESS 28, PHONE 13, EMAIL 9, TAX_ID 9, BIRTHDATE 9, IBAN 8 (3 mit Tippfehler). Ich habe die Texte nicht gelesen; `fill-heldout` gibt nichts aus (Lehre aus claims-extract).
- 2026-11-19: Erster Testlauf fand einen echten Fehler: der Steuer-ID-Lookbehind schloss jedes vorangehende Leerzeichen aus, das Muster griff nie. Behoben, Test bleibt.
- 2026-11-19: Regex allein auf Golden: strukturierte Typen 0 Lecks, PERSON 30/72 (Namen ohne Anrede). Bewusst nicht mit weiteren Namensmustern auf Golden nachgezogen; das ist die Lücke, die der Modell-Detektor zeigen soll.
- 2026-11-19 (Golden k = 3, erster Lauf): llm 7/232 Lecks, both 2/232 (Wilson 0,2–3,1 %), beide "von Briesen"; 91 übermaskierte Spans, meist Uhrzeiten als PHONE. Zwei allgemeine Fixes: Nachname ab Namenszusatz ("von Briesen", nicht "Briesen"); Modell-Fund muss zu seinem Typ passen (PHONE 6–15 Ziffern, EMAIL mit @, TAX_ID 11 Ziffern …). 31 passed.
- 2026-11-19: Lehre aus claims-extract: Autoreview läuft vor dem Held-out-Lauf, damit kein Fix danach das Set verbraucht.
- 2026-11-19 (Autoreview Runde 1, vor Held-out, 4 × P1, übernommen): Platzhalter-Literale in der Eingabe kollidierten mit neuen (restore setzte fremde Werte ein) → Zähler starten über vorhandenen Nummern; BIRTHDATE "Geb.", "geb. am", "Geboren am"; PHONE mit mehreren Trennern ("0931 / 12 34 56"); STREET mit großem Grundwort ("Karl-Marx-Straße", "Alter Markt") und "12A". 42 passed. Kontaminationsrisiko offen gelegt: Das Review hatte data/heldout*.jsonl im Diff, seine Musterhinweise können Held-out-Wissen tragen. Ab Runde 2 liegen die Held-out-Dateien während des Reviews außerhalb des Repos.
- 2026-11-19 (Autoreview Runde 2, Held-out ausgelagert, 5 × P1, übernommen): Namenszusatz direkt nach Anrede ("Frau de Vries") und in Signaturen; bis zu drei Vornamen; alle lateinischen Großbuchstaben ("Çelik", "Şahin"); mehrwortige Orte ("Bad Kissingen", "Frankfurt (Oder)"); "(+49 …)". restore() und Eval-Zählung vom Reviewer ausdrücklich ohne Befund. 51 passed; Regex auf Golden PERSON 30 → 24 (die 6 vorhergesagten). Stoppregel: noch Runde 3, dann Einfrieren unabhängig vom Ergebnis; weitere Muster-Befunde gehen als bekannte Klasse ins README.
- 2026-11-19 (Autoreview Runde 3, Held-out ausgelagert, 3 × P1, übernommen, danach keine Runde 4): akademische Titel nach der Anrede ("Prof.", "Dr. med.", "Dipl.-Ing.") werden übersprungen statt als Name maskiert; Leerzeile/CRLF vor der Signatur; zwei Telefonnummern hintereinander (kein Zeilenumbruch in einer Nummer, "/ 0…" beginnt eine neue). 58 passed, Regex-Golden unverändert 24/232. Bekannte Grenze: eine Durchwahl nach "/", die mit 0 beginnt, wird nicht als Teil der Nummer gelesen. Code eingefroren, Fingerabdruck sha256(src/pii_gate/*.py) = 7f21b797d8b6605e; danach Golden k = 3 und Held-out k = 3 genau einmal.

## Evidence

- ISC-1/2/3/4/5/6/8/9/10/11 (2026-11-19): `OLLAMA_URL=http://127.0.0.1:9 uv run pytest -q` → 29 passed (tests/test_gate.py: Platzhalter-Konsistenz, Rundweg über alle 56 Golden-Texte, Muster je Typ, IBAN mit falscher Prüfziffer maskiert, Steuer-ID nur mit Prüfziffer oder Hinweiswort, Lockvögel unmaskiert, erfundener/teilweiser Modell-Fund verworfen, Merge, Seed-Hash = data/golden.jsonl, jeder Typ ≥ 15, ≥ 5 Lockvogel-Texte, Leck in irgendeinem Lauf zählt, Mutation ohne IBAN-Muster → rot). `ruff check`, `pyright` → 0 Fehler.

- ISC-7 (2026-11-19): Held-out (20 Texte, 116 Spans) genau einmal auf eingefrorenem Code 7f21b797d8b6605e gelaufen → results/heldout-v1.json: patterns 19/116 (10,7–24,2 %), model 6/116 (2,4–10,8 %), both 0/116 (0–3,2 %). Texte nicht gelesen.
- ISC-8/9 (2026-11-19): results/golden-v1.json und heldout-v1.json enthalten je Modus labels, leaked, leak_rate, leak_ci95, per_type, over_masked_spans, leaks (nur Fall-ID und Typ), k, seconds_per_text, model.
- ISC-12/13 (2026-11-19): README mit Quickstart, Method, Results, Limits; "anonymi" nur in der Abgrenzung "Pseudonymisation, not anonymisation". Jede Zahl aus results/*-v1.json abgeschrieben.
- ISC-14 (2026-11-19): Leak-Scan über alle versionierten Dateien: einziger Treffer in data/heldout*.jsonl, ein Wort aus einer synthetischen Personalnotiz ohne Bezug zu realen Personen; als Fehlalarm bewertet, Datei bleibt unverändert (Labels). Keine Pfade, Namen oder Arbeitgeber.
- ISC-15 (2026-11-19): nach dem Held-out-Lauf kein Byte unter src/ geändert; sha256(cat src/pii_gate/*.py) reproduziert 7f21b797d8b6605e.
- ISC-16 (2026-11-19): Autoreview Runde 4 (final, `--engine claude`, P1, Held-out ausgelagert): 4 × P1, alle README-Ebene. Behoben im README: Adress-Leck h06 genannt, "never misses" ersetzt durch belegte Aussage (Patterns 0 IBAN/TAX_ID-Lecks auf beiden Sets), Namensaussage als Konstruktionsfolge statt Beobachtung, Unabhängigkeitsannahme + Textebene 0/20 (Obergrenze 16 %), Limits um stillen Parse-Fallback und fehlendes num_ctx/Chunking ergänzt. Fingerabdruck-Berechnung im README dokumentiert. Code unverändert.
