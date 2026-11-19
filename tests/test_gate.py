import hashlib
import json

import pytest

from pii_gate import gate, restore
from pii_gate import patterns as pt
from pii_gate.data import DATA, SEED, build_golden, load, parse_inline, to_json
from pii_gate.evaluate import leaked, run, score, wilson_ci
from pii_gate.llm import Item, spans_from_items
from pii_gate.spans import TYPES, Span, merge

GOLDEN = load("golden")


def types_of(text: str) -> dict[str, str]:
    return {s.text(text): s.type for s in gate(text).spans}


# ---- gate and restore (ISC-1, ISC-2) ----

def test_same_value_same_placeholder_different_value_different():
    m = gate("Herr Jan Koch rief an. Später schrieb Herr Jan Koch nochmal, dann Frau Ines Engel.")
    assert m.text.count("[PERSON_1]") == 2 and "[PERSON_2]" in m.text
    assert "Koch" not in m.text and "Engel" not in m.text


def test_roundtrip_restores_every_golden_text():
    for c in GOLDEN:
        m = gate(c.text)
        assert restore(m.text, m.mapping) == c.text


def test_restore_puts_originals_into_a_model_answer():
    m = gate("Bitte an anna.berger@web.de antworten.")
    assert restore("Ich schreibe an [EMAIL_1].", m.mapping) == "Ich schreibe an anna.berger@web.de."
    assert restore("Unbekannt: [EMAIL_9]", m.mapping) == "Unbekannt: [EMAIL_9]"


def test_surname_alone_is_masked_once_the_full_name_was_found():
    m = gate("Mit freundlichen Grüßen\nAnna Berger\n\nNachtrag: Frau Berger ruft zurück.")
    assert "Berger" not in m.text


# ---- patterns (ISC-3) ----

@pytest.mark.parametrize("text,value,type_", [
    ("Mail an jan.koch@posteo.de bitte", "jan.koch@posteo.de", "EMAIL"),
    ("Tel. 0951/12345 ab 9 Uhr", "0951/12345", "PHONE"),
    ("erreichbar unter +49 911 1234567.", "+49 911 1234567", "PHONE"),
    ("oder (0911) 12 34 56 abends", "(0911) 12 34 56", "PHONE"),
    ("wohnt Lindenweg 14a in", "Lindenweg 14a", "ADDRESS"),
    ("Berliner Straße 12, 10115 Berlin", "Berliner Straße 12", "ADDRESS"),
    ("Berliner Straße 12, 10115 Berlin", "10115 Berlin", "ADDRESS"),
    ("Am Mühlbach 3", "Am Mühlbach 3", "ADDRESS"),
    ("Name: X, geb. 03.11.1987", "03.11.1987", "BIRTHDATE"),
    ("geboren am 7. Mai 1990 in", "7. Mai 1990", "BIRTHDATE"),
])
def test_pattern_finds(text, value, type_):
    assert types_of(text).get(value) == type_


def test_pattern_iban_masked_with_or_without_valid_checksum():
    good = pt.make_iban("76050101", "1234567890")
    bad = good[:-1] + str((int(good[-1]) + 1) % 10)
    for iban in (good, bad, " ".join(good[i:i + 4] for i in range(0, 22, 4))):
        assert types_of(f"Konto {iban} bitte")[iban] == "IBAN"


def test_pattern_tax_id_needs_checksum_or_cue():
    valid = pt.make_tax_id("6538210497")
    assert pt.tax_id_valid(valid)
    invalid = valid[:-1] + str((int(valid[-1]) + 1) % 10)
    assert not pt.tax_id_valid(invalid)
    assert types_of(f"Nummer {valid} liegt vor")[valid] == "TAX_ID"
    assert invalid not in types_of(f"Bestellung {invalid} ist raus")
    assert types_of(f"Steuer-ID: {invalid}")[invalid] == "TAX_ID"  # a mistyped ID behind its cue is still one


@pytest.mark.parametrize("text", [
    "Rechnung vom 03.11.2025 über 1.250,00 €",       # a date that is not a birth date
    "die Baustelle an der Hauptstraße",               # street without number
    "Wir liefern nach Bamberg.",                      # city alone
    "12345 Euro wurden überwiesen",                   # a five-digit amount is not a postcode
])
def test_pattern_decoys_stay_unmasked(text):
    assert gate(text).spans == []


# ---- model detector (ISC-4) ----

def test_invented_or_partial_model_items_are_dropped():
    text = "Frau Hannah Weiß meldet sich."
    items = [Item(type="PERSON", text="Hannah Weiß"), Item(type="PERSON", text="Anna"),
             Item(type="EMAIL", text="hannah@weiss.de")]
    found = {s.text(text) for s in spans_from_items(items, text)}
    assert found == {"Hannah Weiß"}  # "Anna" sits inside "Hannah", the email is not in the text


# ---- overlap (ISC-5) ----

def test_overlapping_spans_merge_to_the_longest_type():
    assert merge([Span(0, 5, "PERSON"), Span(3, 12, "ADDRESS"), Span(20, 25, "EMAIL")]) == [
        Span(0, 12, "ADDRESS"), Span(20, 25, "EMAIL")]


def test_no_placeholder_inside_a_word():
    m = gate("Bergmann und Berger", [lambda t: [Span(0, 5, "PERSON")] + [Span(13, 19, "PERSON")]])
    assert m.text.startswith("[PERSON_1]")  # a detector may cut a word; the gate masks what it is told
    assert spans_from_items([Item(type="PERSON", text="Berg")], "Bergmann") == []


# ---- data (ISC-6) ----

def test_golden_is_seed_reproducible_and_matches_the_file():
    built = "".join(json.dumps(to_json(c), ensure_ascii=False) + "\n" for c in build_golden())
    on_disk = (DATA / "golden.jsonl").read_bytes()
    assert hashlib.sha256(built.encode()).hexdigest() == hashlib.sha256(on_disk).hexdigest()
    assert SEED == 20261119


def test_golden_covers_every_type_and_has_decoy_only_texts():
    counts = {t: sum(s.type == t for c in GOLDEN for s in c.spans) for t in TYPES}
    assert len(GOLDEN) >= 50 and min(counts.values()) >= 15, counts
    assert sum(not c.spans for c in GOLDEN) >= 5


def test_inline_labels_parse_to_spans():
    c = parse_inline("x", "Frau ⟦PERSON|Ines Engel⟧, ⟦ADDRESS|96047 Bamberg⟧.")
    assert c.text == "Frau Ines Engel, 96047 Bamberg."
    assert [(s.text(c.text), s.type) for s in c.spans] == [("Ines Engel", "PERSON"), ("96047 Bamberg", "ADDRESS")]


# ---- eval (ISC-8, ISC-9, ISC-10) ----

def test_leak_in_any_run_counts():
    case = parse_inline("x", "an ⟦EMAIL|a@b.de⟧")
    full, none = [Span(3, 9, "EMAIL")], []
    assert score([[full], [none], [full]], [case])["leaked"] == 1
    assert leaked(Span(3, 9, "EMAIL"), [Span(3, 8, "EMAIL")])  # one character out is a leak


def test_mutation_without_the_iban_pattern_the_eval_turns_red():
    def no_iban(text: str) -> list[Span]:
        return [s for s in pt.detect(text) if s.type != "IBAN"]

    intact = score(run(GOLDEN, [pt.detect], 1), GOLDEN)["per_type"]["IBAN"]["leaked"]
    mutated = score(run(GOLDEN, [no_iban], 1), GOLDEN)["per_type"]["IBAN"]["leaked"]
    assert intact == 0 and mutated > 0


def test_wilson_widens_with_one_hit():
    assert wilson_ci(0, 16)[1] < wilson_ci(1, 16)[1]
    assert wilson_ci(0, 0) == (0.0, 0.0)


def test_surname_with_particle_is_masked_whole():
    m = gate("Hallo, hier ist Herr Felix von Briesen.\nDanke, Herr von Briesen.")
    assert "Briesen" not in m.text and "Herr von [" not in m.text


def test_model_items_that_do_not_look_like_their_type_are_dropped():
    text = "[10:05] Support: Rückruf unter 0951/12345, Mail an a@b.de."
    items = [Item(type="PHONE", text="10:05"), Item(type="PHONE", text="0951/12345"),
             Item(type="EMAIL", text="Support"), Item(type="EMAIL", text="a@b.de")]
    assert {s.text(text) for s in spans_from_items(items, text)} == {"0951/12345", "a@b.de"}


def test_placeholder_literals_already_in_the_input_survive_the_roundtrip():
    """Review round 1: an existing "[PERSON_1]" collided with the new placeholder for Jan Koch."""
    text = "Kopie an [PERSON_1]. Herr Jan Koch rief an."
    m = gate(text)
    assert restore(m.text, m.mapping) == text and "[PERSON_1]" not in m.mapping


@pytest.mark.parametrize("text,value,type_", [
    # review round 1: case, "am" after geb., several separators, capitalised street words, "12A"
    ("Geb. 14.08.1990, ledig", "14.08.1990", "BIRTHDATE"),
    ("geb. am 12.03.1980", "12.03.1980", "BIRTHDATE"),
    ("Geboren am 2. Januar 1968 in Fürth", "2. Januar 1968", "BIRTHDATE"),
    ("Tel. 0931 / 12 34 56", "0931 / 12 34 56", "PHONE"),
    ("Tel. 0951/ 12 34 56", "0951/ 12 34 56", "PHONE"),
    ("Tel. 0911 - 123456", "0911 - 123456", "PHONE"),
    ("wohnt Karl-Marx-Straße 12 seit", "Karl-Marx-Straße 12", "ADDRESS"),
    ("Lange Straße 5", "Lange Straße 5", "ADDRESS"),
    ("Alter Markt 3", "Alter Markt 3", "ADDRESS"),
    ("Hauptstraße 12A", "Hauptstraße 12A", "ADDRESS"),
])
def test_pattern_variants_from_review(text, value, type_):
    assert types_of(text).get(value) == type_


@pytest.mark.parametrize("text,value", [
    # review round 2: particle right after the title, three-word names, non-ASCII capitals
    ("Danke, Frau de Vries.", "de Vries"),
    ("Herr Ludwig van der Meer rief an", "Ludwig van der Meer"),
    ("Frau Anna Maria Berger kommt", "Anna Maria Berger"),
    ("Herr Mehmet Çelik ist da", "Mehmet Çelik"),
    ("Frau Şahin hat geschrieben", "Şahin"),
])
def test_titled_names_from_review(text, value):
    assert types_of(text).get(value) == "PERSON"


def test_signature_with_particle():
    assert types_of("Mit freundlichen Grüßen\nMehmet de Vries").get("Mehmet de Vries") == "PERSON"


@pytest.mark.parametrize("text,value,type_", [
    ("in 97688 Bad Kissingen gemeldet", "97688 Bad Kissingen", "ADDRESS"),
    ("15230 Frankfurt (Oder)", "15230 Frankfurt (Oder)", "ADDRESS"),
    ("Mobil (+49 171 2345678)", "(+49 171 2345678", "PHONE"),
])
def test_city_and_phone_variants_from_review(text, value, type_):
    found = types_of(text)
    assert any(value in k and t == type_ for k, t in found.items()), found


@pytest.mark.parametrize("text,value", [
    # review round 3: academic titles, blank line or CRLF before the signature
    ("Herr Prof. Müller hat zugesagt", "Müller"),
    ("Frau Dr. med. Anna Berger ist Gutachterin", "Anna Berger"),
    ("Herr Dipl.-Ing. Koch prüft", "Koch"),
    ("Mit freundlichen Grüßen\n\nGreta Scholz", "Greta Scholz"),
    ("Mit freundlichen Grüßen\r\nGreta Scholz\r\n", "Greta Scholz"),
])
def test_names_from_review_round_3(text, value):
    m = gate(text)
    assert types_of(text).get(value) == "PERSON" and value not in m.text


@pytest.mark.parametrize("text", ["Tel. 0951 123456 / 0171 2345678", "0951/12345\n0171-1234567"])
def test_two_numbers_in_a_row_are_both_masked(text):
    m = gate(text)
    assert not any(ch.isdigit() for ch in m.text.replace("PHONE_1", "").replace("PHONE_2", "")), m.text
