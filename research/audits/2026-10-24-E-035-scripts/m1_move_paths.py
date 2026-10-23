"""Auditor E-035 m1: does "12 rigid moves per round" hide different move DISTANCES?  For each translation-invariant
schedule, the order in which the X (Z) ancilla array visits its 6 BB monomials within one check, and the 5 inter-term
displacements on the l x m torus (minimal image; R-block data offset by (0.5, 0.5) lattice units, a layout
assumption).  Move cost per qSIEVE (2311.16980) / Xu (2308.08648): t ~ sqrt(dx) + sqrt(dy) (Manhattan, constant
acceleration); reported in arbitrary units.  Layout-dependent: an indicator only.
    uv run python research/audits/2026-10-24-E-035-scripts/m1_move_paths.py"""
import sys, json, math
sys.path.insert(0, "/Users/ephemeral/Desktop/qec-ai-search/research/audits/2026-10-24-E-035-scripts")
import na_mine as nm


def mi(x, n):
    x = x % n
    return min(x, n - x) if isinstance(x, int) else min(x, n - x)


res = {}
for name in ("u11", "ibm", "c11", "ibm90"):
    fam, d = nm.spec(name)
    lib = nm.LIB[fam]
    P = d["period"]
    out = {}
    for typ, key in (("X", "x_checks"), ("Z", "z_checks")):
        ch = d[key][0]
        seq = sorted(((t - ch["prep"]) % P, nm.group_of(lib, typ, 0, col)) for col, t in ch["cnots"])
        pos = [((g[2] + 0.5 * g[1]) % lib.L_, (g[3] + 0.5 * g[1]) % lib.M_) for _, g in seq]
        cost = 0.0
        steps = []
        for a, b in zip(pos, pos[1:]):
            dx = mi(b[0] - a[0], lib.L_); dy = mi(b[1] - a[1], lib.M_)
            steps.append((round(dx, 2), round(dy, 2)))
            cost += math.sqrt(dx) + math.sqrt(dy)
        out[typ] = dict(order=[(o, g[1:]) for o, g in seq], steps=steps, cost=round(cost, 3),
                        span_layers=(ch["meas"] - ch["prep"]) % P)
    res[name] = out
    print(name, json.dumps(out))
json.dump(res, open("/Users/ephemeral/Desktop/qec-ai-search/results/E-035-audit/m1_move_paths.json", "w"), indent=1)
