"""Auditor (E-026b) claim 5: how far is 'si1000cx' from a standard SI1000 run of the same schedule?
Compile CX(c,t) -> H(t) CZ(c,t) H(t), merging the H layers between consecutive CX layers (H.H = I cancels),
then noise with the evaluator's standard si1000 (CZ native).  Compare per-round DEM mass at p = 1e-3 (R12 - R6)/6,
layers per round and idle slots per round with si1000cx (experimenter's implementation).
RX/MX are kept as native in both (evaluator si1000 accepts them).
  PYTHONPATH=.:tests uv run python research/audits/2026-10-15-E-026b-scripts/si1000_check.py"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import stim
from mynoise import noiseless, build_dem, ROOT, ANN
from evaluators.noise import add_noise
from search.experiments.e026b.common import si1000cx


def compile_cz(nl):
    layers = [[]]
    for i in nl.flattened():
        if i.name == "TICK": layers.append([])
        else: layers[-1].append(i)
    out_layers = []
    pending = set()  # H still to apply after previous CX layer
    for L in layers:
        cx = [i for i in L if i.name == "CX"]
        if cx:
            tg = set()
            for i in cx:
                ts = [t.value for t in i.targets_copy()]
                tg |= set(ts[1::2])
            h = pending ^ tg
            if h: out_layers.append([("H", sorted(h))])
            out_layers.append([("CZ", i) for i in cx] + [("raw", i) for i in L if i.name != "CX"])
            pending = tg
        else:
            if pending:
                out_layers.append([("H", sorted(pending))]); pending = set()
            out_layers.append([("raw", i) for i in L])
    c = stim.Circuit()
    for k, L in enumerate(out_layers):
        if k: c.append("TICK")
        for kind, x in L:
            if kind == "H": c.append("H", x)
            elif kind == "CZ": c.append("CZ", [t.value for t in x.targets_copy()])
            else: c.append(x)
    return c, len(out_layers)


res = {}
for circ in ("p18", "fig12", "ibm"):
    r = {}
    for name, fn in (("si1000cx", lambda nl: si1000cx(nl, 1e-3)),
                     ("si1000_compiled", lambda nl: add_noise(compile_cz(nl)[0], "si1000", 1e-3))):
        t = {}
        for R in (6, 12):
            nl = noiseless(circ, "Z", R)
            c = fn(nl)
            _, _, _, q, _ = build_dem(c)
            nlay = sum(1 for i in c.flattened() if i.name == "TICK") + 1
            t[R] = (q.sum(), nlay)
        r[name] = dict(mass_per_round=(t[12][0] - t[6][0]) / 6, layers_per_round=(t[12][1] - t[6][1]) / 6)
    r["mass_ratio_compiled_over_cx"] = r["si1000_compiled"]["mass_per_round"] / r["si1000cx"]["mass_per_round"]
    res[circ] = r
    print(circ, r, flush=True)
for a in ("p18",):
    for b in ("fig12", "ibm"):
        res[f"mass_ratio_{a}_{b}"] = {k: res[a][k]["mass_per_round"] / res[b][k]["mass_per_round"] for k in ("si1000cx", "si1000_compiled")}
print(json.dumps({k: v for k, v in res.items() if k.startswith("mass_ratio")}, indent=1))
(ROOT / "results/E-026b-audit/si1000_check.json").write_text(json.dumps(res, indent=1))
