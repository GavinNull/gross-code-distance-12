"""E-038 audit: positive control for the WRAPPING pattern files (V8, V9, W8, W9 of E-038): no sound pattern can cancel
in the bulk of the d_circ = 4 N8 schedule (period 10, prep 0, meas 9) under my general semantics gpat.GSem.
Plus a negative control for my legality: flipping one CNOT order to break a parity condition must make stim report a
non-deterministic detector.
usage: uv run python -m search.experiments.e038_audit.b4b_positive_wrap"""
import glob
import json

from search.experiments.e038_audit import acore as C
from search.experiments.e038_audit import gpat, npat


def main():
    P, sch = C.parse_spec("search/experiments/e038/bb18_n8_d4_spec.json")
    tau = {(k, q): t for k, r in sch.items() for q, t in r["cx"].items()}
    pi = {k: 0 for k in sch}
    mu = {k: P - 1 for k in sch}
    files = sorted(f for f in glob.glob("results/E-038-bb18-d4/*_patterns.json")
                   if any(s in f for s in ("_V8_", "_V9_", "_W8_", "_W9_")))
    sem = gpat.GSem(P)
    seen = set()
    canc = 0
    for f in files:
        for p in json.load(open(f)):
            key = json.dumps(p)
            if key in seen:
                continue
            seen.add(key)
            canc += len(sem.cancels(npat.norm_pattern(p), tau))
    out = {"files": files, "patterns": len(seen), "cancelling_on_n8": canc,
           "n8_deterministic": gpat.deterministic(P, pi, mu, tau)[0]}
    # negative control: swap the layers of two CNOTs of X0 that share no data qubit with... (just swap two of X0's
    # CNOTs: changes the X0/Z parity for some pair unless both swapped qubits behave alike)
    k0 = ("X", 0)
    qs = sorted(sch[k0]["cx"])
    res = []
    for a in range(6):
        for b in range(a + 1, 6):
            t2 = dict(tau)
            t2[(k0, qs[a])], t2[(k0, qs[b])] = tau[(k0, qs[b])], tau[(k0, qs[a])]
            leg, why = gpat.legal(P, pi, mu, t2)
            clash = "qubit" in why
            if clash:
                continue
            det, _ = gpat.deterministic(P, pi, mu, t2)
            res.append({"swap": [qs[a], qs[b]], "my_legal": leg, "why": why, "stim_deterministic": det})
    out["swap_controls"] = res
    out["legal_iff_deterministic"] = all(r["my_legal"] == r["stim_deterministic"] for r in res)
    print(json.dumps(out, indent=1))
    json.dump(out, open("results/E-038-audit/b4b_positive_wrap.json", "w"), indent=1)


if __name__ == "__main__":
    main()
