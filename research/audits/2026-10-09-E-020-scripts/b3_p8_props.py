"""Audit E-020 b3: properties of my 4 P=8 solutions (from p8search): colour-uniformity (colour from strikis meta),
interleaving pattern per data qubit (cyclic X/Z sequence of its 6 CNOT times mod 8), stim determinism at R=2 via
evaluator circuits (DEM build with allow_gauge_detectors=False raises on non-deterministic detectors)."""
import sys, json, collections
sys.path.insert(0, "research/audits/2026-10-09-E-020-scripts")
from b1_p8_instance import checks, spec_of, sched, meta, code
from evaluators.pipeline import circuits_for
from evaluators.noise import add_noise
sols = [list(map(int, l.split()[1:])) for l in open("results/E-020-audit/p8search_fix0.txt") if l.startswith("SOL")]
cc = meta["check_colour"]
colours = [cc[q] for q in sched.x_checks] + [cc[q] for q in sched.z_checks]
s0 = [p for _, p, _ in checks]
for n, s in enumerate(sols):
    d = collections.defaultdict(set)
    for i, (typ, p, cn) in enumerate(checks):
        d[(typ, colours[i])].add((s[i] - s0[i]) % 8)
    uni = all(len(v) == 1 for v in d.values())
    pats = collections.Counter()
    seq = collections.defaultdict(dict)
    for i, (typ, p, cn) in enumerate(checks):
        for q, k in cn.items():
            seq[q][(s[i] + k) % 8] = typ
    nonint = 0
    for q in range(144):
        st = "".join(seq[q].get(t, ".") for t in range(8))
        pats[st] += 1
        ring = [c for c in st + st if c != "."]
        # non-interleaved: exactly 2 type changes around the cycle
        cyc = [c for c in st if c != "."]
        ch = sum(cyc[i] != cyc[(i + 1) % 6] for i in range(6))
        nonint += ch == 2
    dets = []
    for R in (2,):
        cs = circuits_for(spec_of(s).to_dict(), code, R)
        for b in "ZX":
            add_noise(cs[b], "sd6", 1e-3).detector_error_model(decompose_errors=False, allow_gauge_detectors=False)
            dets.append(True)
    print(n, "colour-uniform", uni, {k: sorted(v) for k, v in sorted(d.items())}, "non-interleaved qubits", nonint,
          "deterministic", all(dets), dict(pats))
