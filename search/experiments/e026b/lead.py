"""E-026b stage B: leading-order (ideal most-likely-error decoder) coefficients of the EXACT E-026 lift families,
re-weighted for each noise model.

E-026's lift_enum (read-only reuse) enumerates, per weight-11 extended logical S (complete E-018 list), all choices of
one fault group (extended column, detector mask) per column of S with detector XOR 0 ("w11": the complete weight-11
circuit logicals of fig12, none for p18) and with one extra zero-image group ("w11z": weight-12 type (b)).
The solution set depends only on WHICH (column, mask) groups exist, not on their probabilities.  For lam > 0 every
group of lam1 exists; for lam = 0 groups made only of idle faults vanish (prob 0) and logicals using them are dropped.
So: enumerate once under lam1 storing each term's (col, mask) key, then look up every term's probability in the
model's own DEM (groups() of lift_enum, evaluated with the model's noisy circuit; the "Table I" assertion re-runs).
A6 = sum over logicals of the less-likely-half 6-subset prior products (lead2.coef, unchanged), per round = R3 - R2
(E-026: per-round values identical for R = 2..6).  Union form, enumerated families only -> estimates, not bounds.
  PYTHONPATH=.:tests uv run python -m search.experiments.e026b.lead"""
import json, time
import numpy as np

import search.experiments.e026.lift_enum as LE
from search.experiments.e026b.common import OUT, noisy_from

PE = 1e-3
GRID = [0.0, 0.01, 0.02, 0.03, 0.05, 0.07, 0.1, 0.15, 0.2, 0.3, 0.5, 0.7, 1.0]
MODELS = [f"lam{x:g}" for x in GRID] + ["si1000cx"]
FAMS = {"fig12": ["w11", "w11z"], "p18": ["w11z"]}
RS = (2, 3)


def set_model(m):
    LE.add_noise = lambda circ, _model, p: noisy_from(circ, m, p)


def coef6(logs, logq):
    """lead2.coef with t = 6 (copied to avoid lead2's module-level run)."""
    import itertools
    W = logs.shape[1]; t = 6
    comb = np.array(list(itertools.combinations(range(W), t)))
    tot = 0.0
    for i in range(0, len(logs), 2000):
        lq = logq[logs[i:i + 2000]]
        allsum = lq.sum(1, keepdims=True)
        s = lq[:, comb].sum(2)
        c = allsum - s
        fail = c > s + 1e-12
        tie = np.abs(c - s) <= 1e-12
        tot += (np.exp(s) * fail).sum() + 0.5 * (np.exp(s) * tie).sum()
    return float(tot)


def enumerate_keys(circ, basis, mode, R):
    kind = LE.KIND[basis]
    E, key_idx, logs = LE.ext_and_logicals(circ, kind)
    set_model("lam1")
    G, Z, _ = LE.groups(circ, basis, R, key_idx)
    terms, keys, out = {}, [], []
    for S in logs:
        gl = [G[j] for j in S] + ([Z] if mode == "w11z" else [])
        cols = list(S) + ([-1] if mode == "w11z" else [])
        sols, _ = LE.enumerate_solutions(gl)
        for sol in sols:
            row = []
            for k in range(len(cols)):
                kk = (cols[k], sol[k])
                if kk not in terms:
                    terms[kk] = len(keys); keys.append(kk)
                row.append(terms[kk])
            out.append(sorted(row))
    W = 11 if mode == "w11" else 12
    arr = np.unique(np.array(out, dtype=np.int32).reshape(-1, W), axis=0)
    return arr, keys, key_idx


def main():
    res = {}
    t0 = time.process_time()
    for circ, modes in FAMS.items():
        for basis in "ZX":
            for R in RS:
                enum = {}
                for mode in modes:
                    enum[mode] = enumerate_keys(circ, basis, mode, R)
                    print(circ, basis, mode, R, "logicals", len(enum[mode][0]), "terms", len(enum[mode][1]),
                          "cpu", round(time.process_time() - t0), flush=True)
                key_idx = enum[modes[0]][2]
                for m in MODELS:
                    set_model(m)
                    G, Z, _ = LE.groups(circ, basis, R, key_idx)
                    for mode in modes:
                        arr, keys, _ = enum[mode]
                        pr = np.array([(Z.get(mk, 0.0) if col == -1 else G.get(col, {}).get(mk, 0.0))
                                       for col, mk in keys])
                        alive = (pr[arr] > 0).all(1)
                        with np.errstate(divide="ignore"):
                            lq = np.log(pr)
                        A6 = coef6(arr[alive], lq) if alive.any() else 0.0
                        res.setdefault(f"{circ}_{basis}_{mode}", {}).setdefault(m, {})[R] = \
                            {"n": int(alive.sum()), "A6_at_PE": A6, "n_dead_terms": int((pr == 0).sum())}
                print(circ, basis, R, "models done cpu", round(time.process_time() - t0), flush=True)
    out = {}
    for fam, d in res.items():
        out[fam] = {m: {"n_per_round": v[RS[1]]["n"] - v[RS[0]]["n"],
                        "A6_per_round_at_PE": v[RS[1]]["A6_at_PE"] - v[RS[0]]["A6_at_PE"],
                        "by_R": v} for m, v in d.items()}
    (OUT / "lead.json").write_text(json.dumps(out, indent=1))
    print("cpu total", round(time.process_time() - t0))


if __name__ == "__main__":
    main()
