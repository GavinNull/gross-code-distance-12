"""E-026 stage B2: leading-order (most-likely-error) structural LER coefficients from the exact lift families.
For each logical L (terms with SD6 priors q at PE = 1e-3) and t = ceil(W/2): a t-subset S fails if its complement
is strictly more likely (tie: 1/2).  W11: all 6|5 splits fail on the 6-side.  W12: each 6|6 pair contributes the less
likely half.  Sum over logicals WITHOUT de-duplicating subsets shared by several logicals (union-bound form; the
duplicate fraction is measured on a sample).  Per-round = A(R+1) - A(R).  q ∝ p is used to scale: A(p) = A(PE) (p/PE)^t.
  uv run python -m search.experiments.e026.lead2"""
import glob, itertools, json, math, re
import numpy as np
from search.experiments.e026.common import OUT

PE = 1e-3


def coef(logs, logq, t):
    W = logs.shape[1]
    comb = np.array(list(itertools.combinations(range(W), t)))
    tot = 0.0; tot_tie = 0
    for i in range(0, len(logs), 2000):
        lq = logq[logs[i:i + 2000]]                       # (n, W)
        allsum = lq.sum(1, keepdims=True)
        s = lq[:, comb].sum(2)                            # (n, C)
        c = allsum - s
        fail = c > s + 1e-12
        tie = np.abs(c - s) <= 1e-12
        tot += (np.exp(s) * fail).sum() + 0.5 * (np.exp(s) * tie).sum()
        tot_tie += int(tie.sum())
    return tot, tot_tie


def dup_fraction(logs, t, nsample=3000, rng=np.random.default_rng(0)):
    """fraction of t-subsets of sampled logicals that also occur in another logical (exact check on the full set)."""
    from collections import Counter
    W = logs.shape[1]
    comb = list(itertools.combinations(range(W), t))
    idx = rng.choice(len(logs), min(nsample, len(logs)), replace=False)
    want = set()
    for i in idx:
        L = logs[i]
        for cb in comb:
            want.add(tuple(L[list(cb)]))
    cnt = Counter()
    for L in logs:
        for cb in comb:
            k = tuple(L[list(cb)])
            if k in want:
                cnt[k] += 1
    return sum(1 for k in want if cnt[k] > 1) / len(want)


res = {}
for f in sorted(glob.glob(str(OUT / "lift" / "*.npz"))):
    m = re.match(r".*/(\w+)_([ZX])_(w11z?)_R(\d+)\.npz", f)
    circ, basis, mode, R = m.group(1), m.group(2), m.group(3), int(m.group(4))
    d = np.load(f)
    logs, logq = d["logs"], d["logq"]
    W = 11 if mode == "w11" else 12
    t = 6
    A, ties = coef(logs, logq, t) if len(logs) else (0.0, 0)
    res.setdefault(f"{circ}_{basis}_{mode}", {})[R] = {"n": int(len(logs)), "A6_at_PE": A, "ties": ties}
    print(circ, basis, mode, R, len(logs), f"A6(1e-3)={A:.4e}", flush=True)
out = {}
for k, v in res.items():
    Rs = sorted(v)
    pr = [{"R": f"{Rs[i]}->{Rs[i + 1]}", "n_per_round": v[Rs[i + 1]]["n"] - v[Rs[i]]["n"],
           "A6_per_round_at_PE": v[Rs[i + 1]]["A6_at_PE"] - v[Rs[i]]["A6_at_PE"]} for i in range(len(Rs) - 1)]
    out[k] = {"by_R": v, "per_round": pr}
    print(k, json.dumps(pr))
(OUT / "lead2.json").write_text(json.dumps(out, indent=1))
