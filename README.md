# pii-gate

**Personal data out of German text before a hosted LLM sees it, back into the answer afterwards, and a measured
number for what still slips through, per entity type.**

Python 3.13 · Pydantic · uv · local `qwen3:8b` through Ollama. No API key, no cloud. All people, addresses,
IBANs and tax IDs are synthetic.

## Quickstart

```sh
uv sync
uv run pytest                                   # 58 tests, no model needed
echo "Herr Jan Koch, Tel. 0951/12345" | uv run pii-gate          # patterns only
echo "Herr Jan Koch, Tel. 0951/12345" | uv run pii-gate --llm    # patterns + local model
uv run evaluate --set golden -k 3                                # needs Ollama with qwen3:8b
```

```python
from pii_gate import gate, restore
from pii_gate.llm import OllamaDetector
from pii_gate.patterns import detect

masked = gate(text, [detect, OllamaDetector()])   # masked.text goes to the hosted model
answer = hosted_llm(masked.text)                   # "[PERSON_1] asks about [IBAN_1] …"
print(restore(answer, masked.mapping))             # the mapping never leaves your side
```

## Method

```
text ──► pattern detector ─┐
     └─► local model ──────┴─► merge, propagate ──► [TYPE_n] placeholders ──► hosted model ──► restore
         (verbatim spans       (same value masked
          only)                 everywhere, surname too)
```

- **Patterns** for structured data: email, phone (German formats), IBAN, tax ID, birth date (a date after "geb.",
  "geboren am" …), street with house number, postcode with city, and names after a salutation or under a
  sign-off. An IBAN-shaped string is masked even with a wrong check digit, because a mistyped account number is
  still personal data. An 11-digit number counts as a tax ID only with a valid ISO 7064 check digit or a cue word
  in front, so order numbers pass.
- **The local model** lists personal data with type and text. An item counts only where its text stands in the
  input at token boundaries and looks like its type (a "phone number" needs six digits; the model called
  "10:05" one). Invented items vanish.
- **Merge and propagate.** Overlaps merge to the longest span; a value found once is masked everywhere, and a
  person's surname alone too ("Frau Berger" after "Anna Berger").
- **Restore.** Each placeholder maps to the exact original string; placeholders already in the input (a quoted
  earlier answer) are numbered around, so the round trip is exact. A test checks it on every golden text.

**What is measured: the leak rate.** A labelled span leaks if any of its characters reaches the masked output in
any of k = 3 runs. Leaks are reported per type with a 95 % Wilson interval, for patterns alone, the model alone,
and both. Over-masking (a masked span with no label) is reported too: it costs answer quality, not privacy.

**Data.** The **golden set** (56 texts, seed-reproducible, `uv run make-data`) is built from templates with labels
known by construction, plus decoy-only texts: company names that contain surnames, order and invoice numbers,
non-birth dates, streets without a number, role mailboxes. It was used for tuning. The **held-out set** (20 texts)
was written by a separate agent before any detector code existed, in freer forms: call notes, chat logs,
forwarded threads, hard-wrapped mail, contract excerpts. Its labels are inline (`⟦PERSON|…⟧`); bank and tax data
were placeholders filled by `uv run fill-heldout`. I have not read those texts.

## Results

`qwen3:8b` via Ollama on one MacBook, temperature 0, k = 3. Code frozen before the held-out run (fingerprint
`7f21b797d8b6605e` = first 16 hex of `cat src/pii_gate/*.py | shasum -a 256`); files: [`results/golden-v1.json`](results/golden-v1.json),
[`results/heldout-v1.json`](results/heldout-v1.json).

| set | detectors | labelled spans | **leaked** | leak 95 % interval | over-masked spans | s / text |
|---|---|---|---|---|---|---|
| golden (tuned on) | patterns | 232 | 24 | 7.1 – 14.9 % | 16 | < 0.01 |
| golden | model | 232 | 7 | 1.5 – 6.1 % | 61 | 3.7 |
| golden | **both** | 232 | **0** | 0 – 1.6 % | 61 | 4.3 |
| held-out (run once) | patterns | 116 | 19 | 10.7 – 24.2 % | 6 | < 0.01 |
| held-out | model | 116 | 6 | 2.4 – 10.8 % | 9 | 4.6 |
| held-out | **both** | 116 | **0** | 0 – 3.2 % | 11 | 4.4 |

**The two detectors fail in opposite places.** Patterns alone missed 18 of 40 names on the held-out set (and
one address); by construction they only see names after a salutation, under a sign-off, or repeated from one
of those. The model alone caught most names but dropped two IBANs and a tax ID, which the patterns caught on
both sets. Neither is safe alone; together nothing labelled leaked on either set. Per-type counts and the case
ids of every leak (never the leaked text) are in the JSON files.

Zero leaks is not zero risk. The span interval (0 – 3.2 %) treats the 116 spans as independent; they come from
20 texts, and spans in one text share a style. Counted per text, 0 of 20 texts leaked, with a 95 % upper bound
of 16 %. Most types have only 8 to 13 held-out spans.

## How the patterns got here

Three rounds of independent code review ran before the held-out run, so no fix came after it. Each round found
real leak paths the golden set could not show, because the generator only produced the formats the patterns
were written for: "geb. am" and "Geboren am", "0931 / 12 34 56", "Karl-Marx-Straße 12" and "12A", "Frau de
Vries", "Herr Mehmet Çelik", "97688 Bad Kissingen", "Herr Prof. Müller", a blank line before a signature, two
phone numbers in a row, and a placeholder already present in the input that `restore()` filled with someone
else's name. Each has a regression test.

One caveat: the first review round had the held-out file in its diff. Its pattern suggestions may carry
knowledge of the held-out texts. From round two on, the held-out files were moved out of the repository while a
review ran.

## Limits

- **Pseudonymisation, not anonymisation.** The mapping links placeholders back to people and is itself personal
  data; it must stay on your side. The masked text can still identify someone through context (a rare job, a
  small town, a described event).
- **Recall is measured against labels.** Personal data a label writer missed is not counted as a leak. Some of
  the held-out "over-masked" spans may be exactly that.
- Synthetic text, one model, one machine; German only. The golden set was tuned on; only the held-out row is a
  test, and its per-type counts are small.
- The model detector costs about 4 s per text locally. Patterns alone are instant but leak names.
- If the model's reply does not parse, that text silently falls back to patterns only. The eval counts this as
  leaks, but a production caller gets no signal.
- No chunking and no `num_ctx` setting: the evaluated texts are short, and a long document may be cut off by
  Ollama's context window without an error.
- Known gaps: a phone extension after "/" that starts with 0 is cut off; capitalised nouns right after a name
  ("Frau Berger Bescheid") are over-masked.

## License

Apache-2.0
