"""Item 4: Lemma 3 witnesses replayed in stim on a random sample of legal T(8) timing vectors.
For each sampled vector (own sampler + own legality conditions, then the evaluator's validate/unroll and a
deterministic noiseless circuit) and each basis: for both pair hooks of the writer order (suffix of length 2 = last
pair; suffix of length 4 = first pair modulo the check), a weight-d logical L containing that pair at check 0
(CP-SAT, own code), the hook fault at instance j and single-qubit errors on L minus the pair placed in one inter-round
gap n.  Only interior hook instances (2..R-3) and interior gaps (after rounds 0..R-2) are
scanned, so boundary effects cannot produce the witness.  Scan j, n; success = no detector fires and an observable flips (weight d-1 undetected logical).
  PYTHONPATH=.:tests uv run python search/experiments/paperP_audit/item4_lemma3_stim.py <gross|bb90> <n_vectors> <seed> [R]
"""
import json, random, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from item3_triples import CODES, build, gf2_kernel, solve
from inject import Injector
from search.theory.B_audit.common import get_code
from ortools.sat.python import cp_model

LAB = ["A1", "A2", "A3", "B1", "B2", "B3"]
P = 8


def sample_vector(rng):
    while True:
        piX = rng.sample(LAB, 6); piZ = rng.sample(LAB, 6); z0 = rng.randrange(-P, P)
        tx = {t: i for i, t in enumerate(piX)}; tz = {t: z0 + i for i, t in enumerate(piZ)}
        left = [tx[a] % P for a in ("A1", "A2", "A3")] + [tz[b] % P for b in ("B1", "B2", "B3")]
        right = [tx[b] % P for b in ("B1", "B2", "B3")] + [tz[a] % P for a in ("A1", "A2", "A3")]
        if len(set(left)) < 6 or len(set(right)) < 6:
            continue
        GL = [[(tx[f"A{i}"] - tz[f"B{j}"]) // P for j in (1, 2, 3)] for i in (1, 2, 3)]
        GR = [[(tx[f"B{j}"] - tz[f"A{i}"]) // P for j in (1, 2, 3)] for i in (1, 2, 3)]
        if GL == GR:
            return piX, piZ, tx, tz


def make_spec(c, tx, tz):
    L, M = c["L"], c["M"]; m = L * M
    idx = lambda a, b: M * (a % L) + (b % M)
    zmin, zmax = min(tz.values()), max(tz.values())
    xs, zs = [], []
    for r in range(m):
        a, b = divmod(r, M)
        qX = {f"A{i+1}": idx(a + t[0], b + t[1]) for i, t in enumerate(c["A"])} | \
             {f"B{j+1}": m + idx(a + t[0], b + t[1]) for j, t in enumerate(c["B"])}
        qZ = {f"B{j+1}": idx(a - t[0], b - t[1]) for j, t in enumerate(c["B"])} | \
             {f"A{i+1}": m + idx(a - t[0], b - t[1]) for i, t in enumerate(c["A"])}
        xs.append({"prep": 0, "meas": max(tx.values()) + 2, "cnots": [[qX[n], tx[n] + 1] for n in LAB]})
        zs.append({"prep": zmin % P, "meas": (zmax + 2) % P, "cnots": [[qZ[n], (tz[n] + 1) % P] for n in LAB]})
    return {"format": "qec-schedule/v1", "period": P, "x_checks": xs, "z_checks": zs}


def main():
    name, nv, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]); R = int(sys.argv[4]) if len(sys.argv) > 4 else 7
    rng = random.Random(seed); c = CODES[name]; HX, HZ, labX, labZ = build(c); code = get_code(name)
    cache = {}

    def logical(side, pair):
        k = (side, pair)
        if k not in cache:
            Hdet, stab, lab = (HZ, HX, labX) if side == "X" else (HX, HZ, labZ)
            K, _ = gf2_kernel(stab)
            n = Hdet.shape[1]; md = cp_model.CpModel(); x = [md.NewBoolVar("") for _ in range(n)]; one = md.NewConstant(1)
            for row in Hdet:
                md.AddBoolXOr([x[i] for i in np.flatnonzero(row)] + [one])
            bs = []
            for kv in K:
                b = md.NewBoolVar(""); md.AddBoolXOr([x[i] for i in np.flatnonzero(kv)] + [b.Not()]); bs.append(b)
            md.AddBoolOr(bs); md.Add(sum(x) == c["d"])
            for nm in pair:
                md.Add(x[lab[nm]] == 1)
            s = cp_model.CpSolver(); s.parameters.num_workers = 1; s.parameters.max_time_in_seconds = 600
            st = s.Solve(md)
            cache[k] = [i for i in range(n) if s.Value(x[i])] if st in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None
        return cache[k]

    results = []
    for v in range(nv):
        piX, piZ, tx, tz = sample_vector(rng)
        spec = make_spec(c, tx, tz)
        rec = {"piX": "".join(piX), "piZ": "".join(piZ), "tz0": min(tz.values()), "witness": []}
        for basis in ("Z", "X"):
            inj = Injector(spec, code, basis, R)
            wtyp, pi = ("X", piX) if basis == "Z" else ("Z", piZ)
            lab = labX if wtyp == "X" else labZ
            rtyp = "Z" if basis == "Z" else "X"
            gaps = [inj.meas_layer(rtyp, j) for j in range(R - 1)]   # interior inter-round gaps only (bulk test)
            for k, pair in ((4, tuple(pi[4:])), (2, tuple(pi[:2]))):
                Lq = logical(wtyp, pair)
                if Lq is None:
                    continue
                data = [q for q in Lq if q not in (lab[pair[0]], lab[pair[1]])]
                # sanity: the hook suffix of check 0 is what we think
                _, _, suf = inj.anc_layer(wtyp, 0, 0, k)
                assert sorted(suf) == sorted(lab[n] for n in pi[k:]), (suf, pi, k)
                hit = None
                for j in range(2, R - 2):            # interior hook instances only
                    for g in gaps:
                        fired, obs = inj.run([("anc", wtyp, 0, j, k)] + [("data", q, g) for q in data])
                        if not fired and obs.any():
                            hit = (j, g); break
                    if hit:
                        break
                if hit:
                    rec["witness"].append({"basis": basis, "hook_after_cnot": k, "pair": "".join(pair),
                                           "weight": 1 + len(data), "instance": hit[0], "gap_layer": hit[1]})
        rec["ok"] = bool(rec["witness"])
        results.append(rec)
        print(json.dumps(rec), flush=True)
    print(json.dumps({"code": name, "R": R, "seed": seed, "vectors": nv, "with_witness": sum(r["ok"] for r in results),
                      "weights": sorted({w["weight"] for r in results for w in r["witness"]})}), flush=True)


if __name__ == "__main__":
    main()
