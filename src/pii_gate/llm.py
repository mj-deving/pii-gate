"""Model detector: a local model lists personal data; only what it quotes verbatim from the text is kept."""

import os
import re
from typing import Literal

import httpx
from pydantic import BaseModel, ValidationError

from .spans import Span, occurrences

MODEL = os.environ.get("PII_MODEL", "qwen3:8b")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")

PROMPT = """Finde alle personenbezogenen Daten im folgenden Text und gib sie als Liste zurück.
Typen:
- PERSON: Name einer natürlichen Person (ohne Herr/Frau/Dr.). Firmennamen sind keine Personen.
- ADDRESS: Straße mit Hausnummer, oder Postleitzahl mit Ort, jeweils als eigener Eintrag.
- EMAIL, PHONE, IBAN.
- TAX_ID: steuerliche Identifikationsnummer (11 Ziffern).
- BIRTHDATE: nur das Datum einer Geburt.
Kopiere `text` Zeichen für Zeichen aus dem Text. Rechnungs-, Policen- und Bestellnummern, Firmennamen und
andere Daten als Geburtsdaten gehören nicht dazu. Gibt es nichts, liefere eine leere Liste.

Text:
"""


class Item(BaseModel):
    type: Literal["PERSON", "ADDRESS", "EMAIL", "PHONE", "IBAN", "TAX_ID", "BIRTHDATE"]
    text: str


class Found(BaseModel):
    items: list[Item]


class OllamaDetector:
    def __init__(self, model: str = MODEL, url: str = OLLAMA_URL, timeout: float = 180.0):
        self.model, self.url, self.timeout = model, url, timeout
        self.served_model: str | None = None

    def items(self, text: str) -> list[Item]:
        r = httpx.post(f"{self.url}/api/chat", timeout=self.timeout, json={
            "model": self.model,
            "messages": [{"role": "user", "content": PROMPT + text}],
            "format": Found.model_json_schema(),
            "think": False,
            "stream": False,
            "options": {"temperature": 0, "seed": 0},
        })
        r.raise_for_status()
        body = r.json()
        self.served_model = body.get("model")
        try:
            return Found.model_validate_json(body["message"]["content"]).items
        except ValidationError:
            return []  # unparseable: the pattern detector still runs; the eval counts what that leaves

    def __call__(self, text: str) -> list[Span]:
        return spans_from_items(self.items(text), text)


def plausible(type_: str, value: str) -> bool:
    """The value has to look like its type: the model called "10:05" a phone number."""
    digits = len(re.sub(r"\D", "", value))
    return {
        "PHONE": 6 <= digits <= 15,
        "EMAIL": "@" in value,
        "IBAN": re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9 ]{11,36}", value) is not None,
        "TAX_ID": digits == 11,
        "BIRTHDATE": digits >= 4,
        "PERSON": any(c.isalpha() for c in value),
        "ADDRESS": any(c.isalpha() for c in value),
    }[type_]


def spans_from_items(items: list[Item], text: str) -> list[Span]:
    """A model item counts only where its text stands in the input at token boundaries and looks like its type."""
    spans: list[Span] = []
    for it in items:
        if plausible(it.type, it.text.strip()):
            spans += occurrences(it.text.strip(), text, it.type)
    return spans
