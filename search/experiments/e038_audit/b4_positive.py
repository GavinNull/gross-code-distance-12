"""E-038 audit: positive control for pattern soundness.  A sound pattern can never cancel in a schedule whose circuit
distance is 4 (I certified bb18_n8_d4 with my own stim code, b1_certify).  Evaluate EVERY non-wrapping pattern file
of E-038 (N6, N7 shards, final N7, N8) with my semantics on the N8 schedule (and, as a sanity contrast, on the Kunlun
circuit with S = 7 and on E-036's bb18_p8_d3 with S = 6, where cancelling patterns must exist and be physical).
usage: uv run python -m search.experiments.e038_audit.b4_positive"""
import glob
import json

from search.experiments.e038_audit import acore as C
from search.experiments.e038_audit import npat
from search.experiments.e038_audit.b1_certify import kunlun_spec


def tau_of(spec):
    P, sch = C.parse_spec(spec)
    assert all(r["prep"] == 0 and r["meas"] == P - 1 for r in sch.values())
    return P - 2, {(k, q): t for k, r in sch.items() for q, t in r["cx"].items()}


def main():
    files = sorted(set(glob.glob("results/E-038-bb18-d4/*N6*_patterns.json") + glob.glob("results/E-038-bb18-d4/*N7*_patterns.json")
                       + glob.glob("results/E-038-bb18-d4/*N8*_patterns.json") + ["results/E-038-bb18-d4/seed_N7_patterns.json"]))
    files = [f for f in files if "full" not in f]
    pats = {}
    for f in files:
        for p in json.load(open(f)):
            pats[json.dumps(p)] = p
    pats = [npat.norm_pattern(p) for p in pats.values()]
    out = {"files": files, "n_patterns": len(pats)}
    for name, spec in (("n8", "search/experiments/e038/bb18_n8_d4_spec.json"), ("kunlun", kunlun_spec()),
                       ("bb18_p8_d3", "search/experiments/e036/bb18_p8_d3_spec.json")):
        S, tau = tau_of(spec)
        sem = npat.NSem(S)
        canc = [(i, ch) for i, p in enumerate(pats) for ch in sem.cancels(p, tau)]
        phys = [npat.physical(pats[i], ch, tau, S) for i, ch in canc[:50]]
        out[name] = {"S": S, "cancelling_instances": len(canc),
                     "physical_ok_of_first50": sum(1 for d, o in phys if d == 0 and o > 0), "checked": len(phys)}
        print(name, out[name], flush=True)
    json.dump(out, open("results/E-038-audit/b4_positive.json", "w"), indent=1)


if __name__ == "__main__":
    main()
