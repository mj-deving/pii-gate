"""Synthetic German texts with personal-data labels known by construction, and the blind held-out set's loader."""

import json
import random
import re
from dataclasses import dataclass
from pathlib import Path

from .patterns import make_iban, make_tax_id, tax_id_valid
from .spans import Span

SEED = 20261119
DATA = Path(__file__).resolve().parents[2] / "data"

FIRST = [
    "Anna",
    "Jonas",
    "Lea",
    "Mehmet",
    "Sophie",
    "Lukas",
    "Ewa",
    "Paul",
    "Hannah",
    "Thi Lan",
    "Karl-Heinz",
    "Marie",
    "Felix",
    "Aylin",
    "Jan",
    "Greta",
    "Tobias",
    "Ines",
    "Noah",
    "Johanna",
]
LAST = [
    "Berger",
    "Fuchs",
    "Winter",
    "Koch",
    "Yılmaz",
    "Nguyen",
    "Kowalski",
    "von Briesen",
    "Schmidt-Rau",
    "Hoffmann",
    "de Vries",
    "Brandl",
    "Wagner",
    "Krause",
    "Engel",
    "Lindqvist",
    "Scholz",
    "Petrović",
]
STREETS = [
    "Lindenweg",
    "Hauptstraße",
    "Am Mühlbach",
    "Berliner Straße",
    "Kirchgasse",
    "Schillerplatz",
    "Rosenstr.",
    "Zum Anger",
    "Bahnhofallee",
    "Gartenring",
]
CITIES = [
    "96047 Bamberg",
    "90402 Nürnberg",
    "80331 München",
    "01067 Dresden",
    "50667 Köln",
    "97070 Würzburg",
    "60311 Frankfurt am Main",
    "10115 Berlin",
]
MONTHS = [
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
]
COMPANIES = ["Schreinerei Bauer GmbH", "Dachdecker Koch & Söhne", "Elektro Winter KG", "Glaserei Fuchs"]

Part = str | tuple[str, str]  # plain text, or (TYPE, value)


@dataclass
class Case:
    id: str
    text: str
    spans: list[Span]


def render(id_: str, parts: list[Part]) -> Case:
    text, spans = "", []
    for p in parts:
        if isinstance(p, tuple):
            spans.append(Span(len(text), len(text) + len(p[1]), p[0]))
            text += p[1]
        else:
            text += p
    return Case(id_, text, spans)


def _ascii(s: str) -> str:
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"), ("ı", "i"), ("ć", "c"), (" ", "."), ("-", "")):
        s = s.replace(a, b)
    return s.lower()


class Gen:
    def __init__(self, seed: int):
        self.r = random.Random(seed)

    def person(self) -> tuple[str, str]:
        return self.r.choice(FIRST), self.r.choice(LAST)

    def phone(self) -> str:
        n = "".join(self.r.choice("0123456789") for _ in range(7))
        return self.r.choice(
            [f"0951/{n[:5]}", f"+49 911 {n}", f"(0911) {n[:2]} {n[2:4]} {n[4:6]}", f"0171-{n}", f"089 {n[:3]} {n[3:]}"]
        )

    def email(self, first: str, last: str) -> str:
        return f"{_ascii(first)}.{_ascii(last)}@{self.r.choice(['web.de', 'gmx.net', 'posteo.de', 'mail.de'])}"

    def iban(self, spaced: bool | None = None) -> str:
        iban = make_iban(self.r.choice(["76050101", "70020270", "12030000"]), str(self.r.randrange(10**9, 10**10)))
        if spaced if spaced is not None else self.r.random() < 0.5:
            iban = " ".join(iban[i : i + 4] for i in range(0, len(iban), 4))
        return iban

    def bad_iban(self) -> str:
        iban = self.iban(spaced=False)
        i = self.r.randrange(4, len(iban))
        return iban[:i] + str((int(iban[i]) + 1) % 10) + iban[i + 1 :]

    def tax_id(self) -> str:
        return make_tax_id(str(self.r.randrange(1, 10)) + "".join(self.r.choice("0123456789") for _ in range(9)))

    def order_no(self) -> str:
        """An 11-digit number that is not a tax ID (wrong check digit): a decoy."""
        while True:
            n = str(self.r.randrange(10**10, 10**11))
            if not tax_id_valid(n):
                return n

    def date(self, years: tuple[int, int]) -> str:
        d, m, y = self.r.randint(1, 28), self.r.randint(1, 12), self.r.randint(*years)
        return self.r.choice([f"{d:02d}.{m:02d}.{y}", f"{d}. {MONTHS[m - 1]} {y}"])

    def street(self) -> str:
        return f"{self.r.choice(STREETS)} {self.r.randint(1, 120)}{self.r.choice(['', '', 'a', 'b'])}"


def _claim_mail(g: Gen, i: int) -> list[Part]:
    f, ln = g.person()
    return [
        "Betreff: Schaden vom ",
        g.date((2025, 2026)),
        "\n\nSehr geehrte Damen und Herren,\n\n",
        "die ",
        g.r.choice(COMPANIES),
        " hat am ",
        g.date((2025, 2026)),
        " den Schaden begutachtet (Rechnung RE-",
        str(2026000 + i),
        "). Bitte überweisen Sie den Betrag auf ",
        ("IBAN", g.iban()),
        ".\n",
        "Sie erreichen mich unter ",
        ("PHONE", g.phone()),
        ".\n\nMit freundlichen Grüßen\n",
        ("PERSON", f"{f} {ln}"),
        "\n",
        ("ADDRESS", g.street()),
        ", ",
        ("ADDRESS", g.r.choice(CITIES)),
    ]


def _hr_note(g: Gen, i: int) -> list[Part]:
    f, ln = g.person()
    return [
        "Personalakte, Neueinstellung\nName: ",
        ("PERSON", f"{f} {ln}"),
        ", geb. ",
        ("BIRTHDATE", g.date((1960, 2004))),
        "\nAnschrift: ",
        ("ADDRESS", g.street()),
        ", ",
        ("ADDRESS", g.r.choice(CITIES)),
        "\nSteuer-ID: ",
        ("TAX_ID", g.tax_id()),
        "\nGehaltskonto: ",
        ("IBAN", g.iban()),
        "\nEintritt zum ",
        g.date((2026, 2027)),
        ", Personalnummer P-",
        str(4000 + i),
    ]


def _call_note(g: Gen, i: int) -> list[Part]:
    f, ln = g.person()
    return [
        "Telefonnotiz ",
        g.date((2026, 2026)),
        "\nAnruf von Frau ",
        ("PERSON", ln),
        " (Rückruf unter ",
        ("PHONE", g.phone()),
        "). Sie fragt nach Bestellung ",
        g.order_no(),
        " und bittet um Antwort an ",
        ("EMAIL", g.email(f, ln)),
        ". Info-Postfach info@",
        _ascii(g.r.choice(LAST)).replace(".", ""),
        "-handel.de hat nicht geantwortet.",
    ]


def _contract(g: Gen, i: int) -> list[Part]:
    f, ln = g.person()
    f2, l2 = g.person()
    return [
        "Mietvertrag\nzwischen Herrn ",
        ("PERSON", f"{f} {ln}"),
        ", geboren am ",
        ("BIRTHDATE", g.date((1950, 2000))),
        ", wohnhaft ",
        ("ADDRESS", g.street()),
        ", ",
        ("ADDRESS", g.r.choice(CITIES)),
        " (Vermieter)\nund Frau ",
        ("PERSON", f"{f2} {l2}"),
        " (Mieterin).\nMietbeginn: ",
        g.date((2026, 2027)),
        ". Die Kaution geht auf ",
        ("IBAN", g.iban()),
        ".",
    ]


def _chat(g: Gen, i: int) -> list[Part]:
    f, ln = g.person()
    return [
        "[10:02] Kunde: Hallo, hier ist ",
        ("PERSON", f"{f} {ln}"),
        ", meine Mail ist ",
        ("EMAIL", g.email(f, ln)),
        "\n[10:03] Support: Danke, Frau ",
        ("PERSON", ln),
        ". Ihre Vertragsnummer?\n[10:04] Kunde: V-",
        str(88000 + i),
        ", und die neue Kontonummer ist ",
        ("IBAN", g.iban()),
        "\n[10:05] Support: Notiert. Lieferung an ",
        ("ADDRESS", g.street()),
        "?\n[10:05] Kunde: Ja, in ",
        g.r.choice(["Bamberg", "Köln", "Dresden"]),
        ".",
    ]


def _tax_mail(g: Gen, i: int) -> list[Part]:
    f, ln = g.person()
    return [
        "Hallo zusammen,\nfür die Lohnabrechnung von ",
        ("PERSON", f"{f} {ln}"),
        " fehlt noch die Nummer ",
        ("TAX_ID", g.tax_id()),
        ". Der Auftrag ",
        g.order_no(),
        " ist davon unabhängig. Das Konto ",
        g.bad_iban(),
        " aus der alten Akte hat einen Tippfehler, bitte nicht verwenden.\nGruß, ",
        ("PERSON", g.r.choice(FIRST) + " " + g.r.choice(LAST)),
    ]


def _decoys_only(g: Gen, i: int) -> list[Part]:
    return [
        f"Wartungsbericht {i}\nAuftrag {g.order_no()} vom {g.date((2025, 2026))}, ausgeführt durch die ",
        g.r.choice(COMPANIES),
        ". Die Baustelle an der Hauptstraße bleibt bis ",
        g.date((2026, 2026)),
        " gesperrt. Rückfragen an service@",
        g.r.choice(["stadtwerke", "bauamt"]),
        "-beispiel.de.",
    ]


TEMPLATES = [_claim_mail, _hr_note, _call_note, _contract, _chat, _tax_mail, _decoys_only]


def _fix_bad_iban_labels(case: Case) -> Case:
    """The mistyped IBAN in _tax_mail is still personal data: label it like any IBAN."""
    m = re.search(r"Das Konto (\S+) aus der alten Akte", case.text)
    if m:
        case.spans.append(Span(m.start(1), m.end(1), "IBAN"))
    return case


def build_golden(n: int = 56, seed: int = SEED) -> list[Case]:
    g = Gen(seed)
    return [_fix_bad_iban_labels(render(f"g{i:02d}", TEMPLATES[i % len(TEMPLATES)](g, i))) for i in range(n)]


LABEL = re.compile(r"⟦(PERSON|ADDRESS|EMAIL|PHONE|IBAN|TAX_ID|BIRTHDATE)\|([^⟧]+)⟧")


def parse_inline(id_: str, marked: str) -> Case:
    parts: list[Part] = []
    pos = 0
    for m in LABEL.finditer(marked):
        parts += [marked[pos : m.start()], (m.group(1), m.group(2))]
        pos = m.end()
    parts.append(marked[pos:])
    return render(id_, parts)


def fill_heldout(seed: int = SEED + 1) -> list[dict[str, str]]:
    """Replace the placeholders the blind writer used for bank and tax data with generated values."""
    g = Gen(seed)
    out = []
    for line in (DATA / "heldout_draft.jsonl").read_text().splitlines():
        row = json.loads(line)
        text = row["text"]
        for ph, make in (("{IBAN_OK}", g.iban), ("{IBAN_BAD}", g.bad_iban), ("{TAXID_OK}", g.tax_id)):
            while ph in text:
                text = text.replace(ph, make(), 1)
        out.append({"id": row["id"], "text": text})
    return out


def to_json(c: Case) -> dict:
    return {"id": c.id, "text": c.text, "spans": [[s.start, s.end, s.type] for s in c.spans]}


def from_json(d: dict) -> Case:
    return Case(d["id"], d["text"], [Span(a, b, t) for a, b, t in d["spans"]])


def load(set_name: str) -> list[Case]:
    return [from_json(json.loads(line)) for line in (DATA / f"{set_name}.jsonl").read_text().splitlines()]


def _write(name: str, cases: list[Case]) -> None:
    DATA.mkdir(exist_ok=True)
    (DATA / f"{name}.jsonl").write_text("".join(json.dumps(to_json(c), ensure_ascii=False) + "\n" for c in cases))


def main() -> None:
    _write("golden", build_golden())


def fill_main() -> None:
    _write("heldout", [parse_inline(r["id"], r["text"]) for r in fill_heldout()])
