"""E-026 stage B2: leading-order (most-likely-error, 'ideal') per-round LER from the enumerated bulk logicals.
For each found bulk logical of weight W (per-round set: min detector round == J0) and each t-subset S with
t = ceil(W/2): S 'fails' if its complement is strictly more likely (tie: 1/2).  Distinct S are deduplicated (a subset
fails if ANY complement found beats it).  A(p) = sum_fail prod_{i in S} q_i(p), q from the RE-round DEM at PE,
scaled as q ∝ p.  NOT a bound (E-023 audit): only the enumerated logicals, only the leading split order.
  uv run python -m search.experiments.e026.lead"""
import itertools, json, math
import numpy as np
from search.experiments.e026.common import OUT, CIRCS, DCIRC
from search.experiments.e026.enum import RE, PE, ENUM
from search.experiments.e026.dem import get

res = {}
for c in CIRCS:
    for b in "ZX":
        f = ENUM / f"bulk_{c}_{b}.json"
        if not f.exists():
            continue
        D = get(c, b, RE, PE)
        lq = np.log(D.q)
        logs = [tuple(x) for x in json.loads(f.read_text())]
        byw = {}
        for L in logs:
            byw.setdefault(len(L), []).append(L)
        out = {"counts_per_round": {int(w): len(v) for w, v in sorted(byw.items())}}
        for t in sorted({math.ceil(w / 2) for w in byw}):
            best = {}   # S -> (logP_S, best complement logP)
            for W, Ls in byw.items():
                if math.ceil(W / 2) != t:
                    continue
                for L in Ls:
                    a = np.array(L); tot = lq[a].sum()
                    for S in itertools.combinations(L, t):
                        s = lq[list(S)].sum(); comp = tot - s
                        pr = best.get(S)
                        if pr is None or comp > pr[1]:
                            best[S] = (s, comp)
            A = 0.0; nfail = 0; nties = 0
            for S, (s, comp) in best.items():
                if comp > s + 1e-9:
                    A += math.exp(s); nfail += 1
                elif abs(comp - s) <= 1e-9:
                    A += 0.5 * math.exp(s); nties += 1
            out[f"t{t}"] = {"A_at_PE": A, "coef_per_p^t": A / PE ** t, "n_subsets": len(best), "n_fail": nfail,
                            "n_tie": nties, "Ws": sorted(int(W) for W in byw if math.ceil(W / 2) == t)}
        res[f"{c}_{b}"] = out
        print(c, b, json.dumps(out), flush=True)
(OUT / "lead.json").write_text(json.dumps(res, indent=1))
