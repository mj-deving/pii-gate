"""Run a set through the gate with each detector mix and write results/<set>.json.

The number that matters is the leak rate: labelled personal-data spans that reach the hosted model unmasked.
"""

import argparse
import json
import math
import os
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from . import patterns
from .data import Case, load
from .gate import Detector, gate
from .spans import TYPES, Span

RESULTS = Path(__file__).resolve().parents[2] / "results"
LOCK = Path(os.environ.get("GPU_LOCK", Path(tempfile.gettempdir()) / "gpu-eval.lock"))


def wilson_ci(hits: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95 % Wilson score interval; sensible for 0 and for a handful of hits."""
    if not n:
        return (0.0, 0.0)
    p = hits / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4))


def leaked(label: Span, masked: list[Span]) -> bool:
    """A label leaks if any of its characters stays outside every masked span."""
    covered = set()
    for m in masked:
        covered.update(range(max(m.start, label.start), min(m.end, label.end)))
    return len(covered) < label.end - label.start


def score(runs: list[list[list[Span]]], cases: list[Case]) -> dict:
    """runs[r][i] = masked spans of case i in run r. A label leaks if it leaks in any run."""
    per_type: dict[str, list[bool]] = {t: [] for t in TYPES}
    leaks = []
    for i, c in enumerate(cases):
        for lab in c.spans:
            hit = any(leaked(lab, run[i]) for run in runs)
            per_type[lab.type].append(hit)
            if hit:
                leaks.append({"case": c.id, "type": lab.type})
    extra = sum(1 for i, c in enumerate(cases) for m in runs[0][i]
                if not any(m.start < lab.end and lab.start < m.end for lab in c.spans))
    total = [h for v in per_type.values() for h in v]
    return {
        "labels": len(total),
        "leaked": sum(total),
        "leak_rate": round(sum(total) / len(total), 4) if total else 0.0,
        "leak_ci95": wilson_ci(sum(total), len(total)),
        "per_type": {t: {"n": len(v), "leaked": sum(v), "leak_ci95": wilson_ci(sum(v), len(v))}
                     for t, v in per_type.items() if v},
        "over_masked_spans": extra,
        "leaks": leaks,  # case id and type only: the leaked text itself is personal data
    }


def run(cases: list[Case], detectors: list[Detector], k: int) -> list[list[list[Span]]]:
    return [[gate(c.text, detectors).spans for c in cases] for _ in range(k)]


@contextmanager
def gpu_lock(poll: int = 30) -> Iterator[None]:
    while True:
        try:
            LOCK.mkdir()
            break
        except FileExistsError:
            print(f"waiting for {LOCK}")
            time.sleep(poll)
    try:
        yield
    finally:
        LOCK.rmdir()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="golden")
    ap.add_argument("-k", type=int, default=3)
    ap.add_argument("--modes", default="regex,llm,both")
    args = ap.parse_args()
    cases = load(args.set)
    result: dict = {"set": args.set, "texts": len(cases), "k": args.k}
    for mode in args.modes.split(","):
        detectors: list[Detector] = []
        if mode in ("regex", "both"):
            detectors.append(patterns.detect)
        llm = None
        if mode in ("llm", "both"):
            from .llm import OllamaDetector
            llm = OllamaDetector()
            detectors.append(llm)
        k = 1 if llm is None else args.k  # the pattern detector is deterministic
        t0 = time.time()
        if llm is None:
            runs = run(cases, detectors, k)
        else:
            with gpu_lock():
                runs = run(cases, detectors, k)
        result[mode] = score(runs, cases) | {
            "k": k, "seconds_per_text": round((time.time() - t0) / (len(cases) * k), 2),
            "model": getattr(llm, "served_model", None)}
        r = result[mode]
        print(mode, {t: f"{v['leaked']}/{v['n']}" for t, v in r["per_type"].items()},
              "total", f"{r['leaked']}/{r['labels']}", "over", r["over_masked_spans"])
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"{args.set}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n")
