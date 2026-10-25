"""E-036: why d_ext <= 3 for [[18,4,4]]: per-check analysis (forbidden hook sets lying inside one check)."""
import itertools, json
import numpy as np
from search.experiments.e036.common import OUT, TERMS, checks, code, term_col
from search.experiments.e036 import dext as D

def run(variant, side):
    c = code(variant); xs, zs = checks(variant)
    kind, chs = ("X", xs) if side == "X" else ("Z", zs)
    Hsyn, Hstab = (c.HZ, c.HX) if side == "X" else (c.HX, c.HZ)
    rk = D.rank2(Hstab)
    out = {}
    for ch in chs:
        supp = [term_col(kind, ch, t) for t in range(6)]
        alive = []
        why = {}
        for perm in itertools.permutations(range(6)):
            cols = [term_col(kind, ch, t) for t in perm]
            hooks = [cols[4:], cols[3:], cols[2:]]  # residues of length 2,3,4
            bad = None
            # extended logical of weight <= 3 using hooks of this check only + data columns (0, 1 or 2 data)
            for r in range(1, 4):
                for H in itertools.combinations(range(3), r):
                    nd = 3 - r
                    v0 = np.zeros(18, np.uint8)
                    for h in H:
                        v0[hooks[h]] ^= 1
                    for k in range(nd + 1):
                        for S in itertools.combinations(range(18), k):
                            v = v0.copy(); v[list(S)] ^= 1
                            if (Hsyn @ v % 2).any(): continue
                            if D.rank2(np.vstack([Hstab, v])) > rk:
                                bad = ([len(hooks[h]) for h in H], list(S)); break
                        if bad: break
                    if bad: break
                if bad: break
            if bad is None:
                alive.append("".join(TERMS[t] for t in perm))
            else:
                why[str(bad[0])] = why.get(str(bad[0]), 0) + 1
        out[ch] = {"orders_alive": len(alive), "killed_by_hook_lengths": why, "alive_examples": alive[:6]}
    return out

if __name__ == "__main__":
    res = {}
    for v in ("bb18", "full"):
        for s in ("X", "Z"):
            res[f"{v}_{s}"] = run(v, s)
            print(v, s, {ch: r["orders_alive"] for ch, r in res[f"{v}_{s}"].items()}, flush=True)
    (OUT / "dext_core.json").write_text(json.dumps(res, indent=1))
