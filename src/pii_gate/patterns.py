"""Deterministic detectors. No model in this file."""

import re

from .spans import Span

# Every Latin capital, not just A-Z and umlauts: "Çelik", "Şahin", "Šimić", "Élise", "İlhan".
UPPER = re.escape("".join(c for c in map(chr, range(0x41, 0x250)) if c.isupper()))
WORD = r"[\w-]"
PARTICLE = r"(?:von der|van der|de la|von|van|de|zu|di|da|del)"

EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# +49 911 123456, 0951/12345, (0911) 12 34 56, 0171-1234567: a leading 0 or +49, then at least six more digits
# No line break inside a number, and a "/" followed by 0 or +49 starts the next number ("0951 123456 / 0171 …").
PHONE = re.compile(r"(?<![\w+])(?:\(?\+49[ \t/-]*(?:\(0\)[ \t]?)?|\(?0)\d{2,5}\)?"
                   r"(?:(?![ \t]*/[ \t]*\(?(?:0|\+49))[ \t/-]{0,3}\d){5,10}(?!\d)")
IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,3})?\b")
TAX_ID = re.compile(r"(?<!\d)(?<!\d )\d{2}\s?\d{3}\s?\d{3}\s?\d{3}(?! ?\d)")
TAX_CUE = re.compile(r"(steuer-?id|steuer-identifikationsnummer|identifikationsnummer|idnr\.?|tin)\W{0,6}$",
                     re.IGNORECASE)
MONTHS = r"(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)"
DATE = rf"\d{{1,2}}\.\s?(?:\d{{1,2}}\.\s?\d{{2,4}}|{MONTHS}\s\d{{4}})"
BIRTHDATE = re.compile(rf"(?:(?i:geb\.|geboren|geburtsdatum:?)(?:\s+am)?|\*)\s*({DATE})")
STREET_SUFFIX = r"(?:straße|strasse|str\.|weg|gasse|platz|allee|ring|damm|ufer|steig|pfad|markt|hof)"
STREET_WORD = r"(?:Straße|Strasse|Str\.|Weg|Gasse|Platz|Allee|Ring|Damm|Ufer|Steig|Pfad|Markt|Hof)"
HOUSE_NO = r"\d{1,4}\s?[A-Za-z]?(?![\w])"
STREET = re.compile(
    rf"\b(?:[{UPPER}]{WORD}*{STREET_SUFFIX}"                        # Lindenweg, Hauptstr.
    rf"|[{UPPER}]{WORD}*[\s-]{STREET_WORD}"                          # Berliner Straße, Karl-Marx-Straße, Alter Markt
    rf"|(?:Am|An der|Auf dem|Im|In der|Zum|Zur)\s[{UPPER}]{WORD}+)"     # Am Lindenhof
    rf"\s{HOUSE_NO}")
# "96047 Bamberg", "97688 Bad Kissingen", "15230 Frankfurt (Oder)", "92637 Weiden in der Oberpfalz"
POSTCODE_CITY = re.compile(
    rf"(?<![\d.,])\d{{5}}\s(?!Euro\b|EUR\b|Stück\b)[{UPPER}][\w.-]*"
    rf"(?:\s(?:an der|am|im|bei|ob der|in der|vor der|a\.\s?d\.|[{UPPER}][\w.-]*|\([^)\n]{{1,20}}\))){{0,3}}")
TITLE = r"(?:Herrn?|Frau|Hr\.|Fr\.|Dr\.|Prof\.)"
# Up to three given names, an optional particle, a surname: "Anna Maria Berger", "de Vries", "Ludwig van der Meer"
NAME = rf"(?:[{UPPER}]{WORD}+\s){{0,3}}(?:{PARTICLE}\s)?[{UPPER}]{WORD}+"
# Any run of academic titles after the salutation: "Prof.", "Dr. med.", "Dr.-Ing.", "Dipl.-Ing."; never a name itself.
ACADEMIC = r"(?:(?:Prof\.|Dr\.(?:-Ing\.|[ ](?:med|rer\.[ ]nat|phil|jur)\.)?|Dipl\.-\w+\.?)[ \t]+)*"
TITLED_NAME = re.compile(rf"\b{TITLE}[ \t]+{ACADEMIC}(?!(?:Prof|Dr|Dipl)\b)({NAME.replace(r'\s', '[ ]')})")
SIGNATURE = re.compile(
    rf"(?:Grüße|Gruß|Grüßen|Dank)[,!.]?(?:[ \t]*\r?\n){{0,3}}[ \t]*"
    rf"([{UPPER}]{WORD}+(?:[ ](?:{PARTICLE}[ ])?[{UPPER}]{WORD}+){{1,3}})[ \t]*\r?$", re.MULTILINE)


def tax_id_valid(digits: str) -> bool:
    """ISO 7064 MOD 11,10 check digit of the 11-digit German tax ID; the first digit is never 0."""
    d = re.sub(r"\D", "", digits)
    if len(d) != 11 or d[0] == "0":
        return False
    product = 10
    for c in d[:10]:
        s = (int(c) + product) % 10 or 10
        product = (2 * s) % 11
    return (11 - product) % 10 == int(d[10])


def make_tax_id(first_ten: str) -> str:
    """Append the check digit (for the synthetic data generator)."""
    product = 10
    for c in first_ten:
        s = (int(c) + product) % 10 or 10
        product = (2 * s) % 11
    return first_ten + str((11 - product) % 10)


def make_iban(bank_code: str, account: str) -> str:
    """A German IBAN with a correct ISO 13616 check number (for the synthetic data generator)."""
    bban = bank_code + account.zfill(10)
    check = 98 - int("".join(str(int(c, 36)) for c in bban + "DE00")) % 97
    return f"DE{check:02d}{bban}"


def detect(text: str) -> list[Span]:
    spans: list[Span] = []
    for rx, type_ in ((EMAIL, "EMAIL"), (PHONE, "PHONE"), (IBAN, "IBAN"), (STREET, "ADDRESS"),
                      (POSTCODE_CITY, "ADDRESS")):
        spans += [Span(m.start(), m.end(), type_) for m in rx.finditer(text)]
    # A mistyped IBAN is still someone's account: IBAN-shaped is enough, no checksum gate.
    for m in TAX_ID.finditer(text):
        if tax_id_valid(m.group()) or TAX_CUE.search(text[max(0, m.start() - 40):m.start()]):
            spans.append(Span(m.start(), m.end(), "TAX_ID"))
    for rx, type_ in ((BIRTHDATE, "BIRTHDATE"), (TITLED_NAME, "PERSON"), (SIGNATURE, "PERSON")):
        spans += [Span(m.start(1), m.end(1), type_) for m in rx.finditer(text)]
    return spans
