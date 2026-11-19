"""The gate: personal data out before the hosted model, back in after."""

import argparse
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field

from . import patterns
from .spans import Span, merge, occurrences

Detector = Callable[[str], list[Span]]
PLACEHOLDER = re.compile(r"\[(PERSON|ADDRESS|EMAIL|PHONE|IBAN|TAX_ID|BIRTHDATE)_(\d+)\]")


@dataclass
class Masked:
    text: str
    mapping: dict[str, str] = field(default_factory=dict)  # placeholder -> original; personal data, keep it local
    spans: list[Span] = field(default_factory=list)       # what was masked, in input coordinates


def find(text: str, detectors: list[Detector]) -> list[Span]:
    spans = [s for d in detectors for s in d(text)]
    # A value found once is masked everywhere it occurs; for a person, the surname alone too ("Frau Berger").
    for s in list(spans):
        value = s.text(text)
        spans += occurrences(value, text, s.type)
        if s.type == "PERSON" and len(surname := _surname(value)) > 2:
            spans += occurrences(surname, text, "PERSON")
    return merge(spans)


def _surname(name: str) -> str:
    """"Felix von Briesen" -> "von Briesen", "Anna Berger" -> "Berger"; a single word has no separate surname."""
    words = name.split()
    if len(words) < 2:
        return ""
    for i, w in enumerate(words[1:], 1):
        if w in ("von", "van", "de", "zu", "der", "di", "da"):
            return " ".join(words[i:])
    return words[-1]


def gate(text: str, detectors: list[Detector] | None = None) -> Masked:
    spans = find(text, detectors if detectors is not None else [patterns.detect])
    mapping: dict[str, str] = {}
    by_value: dict[tuple[str, str], str] = {}
    # Number new placeholders above any already in the text (a quoted earlier answer), so restore() never
    # puts a value where the input only held a placeholder literal.
    counter: dict[str, int] = {}
    for m in PLACEHOLDER.finditer(text):
        counter[m.group(1)] = max(counter.get(m.group(1), 0), int(m.group(2)))
    out, pos = [], 0
    for s in spans:
        key = (s.type, s.text(text))
        if key not in by_value:
            counter[s.type] = counter.get(s.type, 0) + 1
            by_value[key] = f"[{s.type}_{counter[s.type]}]"
            mapping[by_value[key]] = key[1]
        out += [text[pos:s.start], by_value[key]]
        pos = s.end
    out.append(text[pos:])
    return Masked("".join(out), mapping, spans)


def restore(answer: str, mapping: dict[str, str]) -> str:
    """Placeholders the model echoed come back as the originals; unknown ones stay as they are."""
    return PLACEHOLDER.sub(lambda m: mapping.get(m.group(), m.group()), answer)


def main() -> None:
    ap = argparse.ArgumentParser(description="Mask personal data in German text read from stdin.")
    ap.add_argument("--llm", action="store_true", help="add the local-model detector (needs Ollama)")
    args = ap.parse_args()
    detectors: list[Detector] = [patterns.detect]
    if args.llm:
        from .llm import OllamaDetector
        detectors.append(OllamaDetector())
    print(gate(sys.stdin.read(), detectors).text, end="")
