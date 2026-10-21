"""E-030: run E-028's exact weight-<=9 lift (e028.lift9.test, unchanged) but write the jsonl into E-030's results
directory (e028.lift9.main appends to results/E-028-bb90-interleaved/lift9.jsonl).  The w8/w9 lists are still READ
from E-028's directory (inputs).
    PYTHONPATH=.:tests uv run python -m search.experiments.e030.lift9_local SPEC.json --R 1 2 ... [--all 1]"""
import argparse
import json
import time

from evaluators.candidate import parse_schedule
from search.experiments.e028.cegar import load_class
from search.experiments.e028.lift import KIND_OF_BASIS
from search.experiments.e028.lift9 import test
from search.experiments.e030.common import OUT

ap = argparse.ArgumentParser()
ap.add_argument("spec"); ap.add_argument("--R", type=int, nargs="+", default=[1]); ap.add_argument("--bases", default="ZX")
ap.add_argument("--xo", default="A1A2A3B2B1B3"); ap.add_argument("--zo", default="A1A2A3B2B1B3"); ap.add_argument("--all", type=int, default=1)
a = ap.parse_args()
spec = parse_schedule(json.load(open(a.spec))).canonical()
lists = {}
for k, o in (("X", a.xo), ("Z", a.zo)):
    l8, cs8 = load_class(k, "all", o, 8); l9, _ = load_class(k, "all", o, 9); lists[k] = (l8, l9, cs8)
for R in a.R:
    for b in a.bases:
        t0 = time.time(); r = test(spec, R, b, *lists[KIND_OF_BASIS[b]], stop_first=not a.all); r["sec"] = round(time.time() - t0, 1)
        print(json.dumps(r), flush=True)
        with open(OUT / "lift9.jsonl", "a") as f:
            f.write(json.dumps({"spec": a.spec, **r}) + "\n")
