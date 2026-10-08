"""E-018 stage a: collect the W=11 DFS outputs (lead's runs), check completeness (every job of jobs.txt has exactly
one SUMMARY line; printed FOUND lines == found), expand every solution under the 24-element translation group,
deduplicate, verify each is an extended logical of weight 11, and write w11_all_{X,Z}.pkl.

Truncated runs (printed < found) are replaced by the full reruns full_<kind>_c<case>_s<split>.txt.

    PYTHONPATH=. uv run python -m search.experiments.e018.expand
"""
import json
import pickle
import re

import numpy as np

from search.experiments.e018.common import OUT, ext


def parse(path):
    txt = path.read_text()
    found = [tuple(int(x) for x in l.split("cols:")[1].split()) for l in txt.splitlines() if l.startswith("FOUND")]
    m = re.findall(r"SUMMARY W=(\d+) case=(\d+) split=(\d+)/(\d+) nodes=(\d+) found=(\d+)", txt)
    assert len(m) == 1, f"{path}: {len(m)} SUMMARY lines"
    W, case, si, sm, nodes, nf = map(int, m[0])
    return found, dict(W=W, case=case, split=si, mod=sm, nodes=nodes, found=nf)


def main():
    import sys
    prelim = "--prelim" in sys.argv   # development only: accept truncated outputs, write w11_prelim_*.pkl
    jobs = [l.split() for l in (OUT / "jobs.txt").read_text().splitlines() if l.strip()]
    summary = {}
    for kind in "XZ":
        E = ext(kind)
        He, Le, perms = E["He"].astype(np.int64), E["Le"].astype(np.int64), E["perms"]
        raw, nodes, used = [], 0, []
        for k, case, mod, idx in jobs:
            if k != kind:
                continue
            p = OUT / f"w11_{kind}_c{case}_s{idx}.txt"
            sols, s = parse(p)
            if len(sols) != s["found"] and not prelim:
                p = OUT / f"full_{kind}_c{case}_s{idx}.txt"
                sols, s = parse(p)
            assert prelim or len(sols) == s["found"], p
            assert (s["W"], s["case"], s["split"], s["mod"]) == (11, int(case), int(idx), int(mod)), p
            raw += sols; nodes += s["nodes"]; used.append(p.name)
        allsets = set()
        for S in raw:
            assert len(set(S)) == 11
            for P in perms:
                allsets.add(tuple(sorted(int(P[j]) for j in S)))
        allsets = sorted(allsets)
        for S in allsets:
            x = np.zeros(He.shape[1], np.int64); x[list(S)] = 1
            assert not (He @ x % 2).any() and (Le @ x % 2).any()
        # orbit structure
        orbs = set()
        for S in allsets:
            orbs.add(min(tuple(sorted(int(P[j]) for j in S)) for P in perms))
        sizes = {}
        for o in orbs:
            n = len({tuple(sorted(int(P[j]) for j in o)) for P in perms})
            sizes[n] = sizes.get(n, 0) + 1
        U = sorted({j for S in allsets for j in S})
        print(f"{kind}: jobs {len(used)}, DFS nodes {nodes:.3e}, printed solutions {len(raw)}, "
              f"distinct weight-11 logicals {len(allsets)}, orbits {len(orbs)} (sizes {sizes}), |U| = {len(U)}/{He.shape[1]}")
        pickle.dump(allsets, open(OUT / f"w11_{'prelim' if prelim else 'all'}_{kind}.pkl", "wb"))
        summary[kind] = {"jobs": len(used), "nodes": nodes, "printed": len(raw), "distinct": len(allsets),
                         "orbits": len(orbs), "orbit_sizes": sizes, "U": len(U), "N": int(He.shape[1]),
                         "files": used}
    if not prelim:
        (OUT / "stage_a_summary.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
