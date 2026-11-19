"""A detected piece of personal data is a typed character range in the input text."""

import re
from dataclasses import dataclass

TYPES = ("PERSON", "ADDRESS", "EMAIL", "PHONE", "IBAN", "TAX_ID", "BIRTHDATE")


@dataclass(frozen=True, order=True)
class Span:
    start: int
    end: int
    type: str

    def text(self, s: str) -> str:
        return s[self.start:self.end]


def at_token_boundary(text: str, start: int, end: int) -> bool:
    """Neither end of the range cuts a word or a number: "Berg" inside "Bergmann" does not count."""
    return (start == 0 or not text[start - 1].isalnum()) and (end == len(text) or not text[end].isalnum())


def occurrences(value: str, text: str, type_: str) -> list[Span]:
    """Every whole-token occurrence of a value in the text (case-sensitive: "Koch" the name, not "koch" the verb)."""
    if not value.strip():
        return []
    return [Span(m.start(), m.end(), type_) for m in re.finditer(re.escape(value), text)
            if at_token_boundary(text, m.start(), m.end())]


def merge(spans: list[Span]) -> list[Span]:
    """Overlapping or touching-inside spans become one; the merged span keeps the type of its longest part."""
    out: list[tuple[int, int, Span]] = []  # (start, end, longest part)
    for s in sorted(spans):
        if out and s.start < out[-1][1]:
            start, end, longest = out[-1]
            if s.end - s.start > longest.end - longest.start:
                longest = s
            out[-1] = (start, max(end, s.end), longest)
        else:
            out.append((s.start, s.end, s))
    return [Span(start, end, longest.type) for start, end, longest in out]
