"""[[90,8,10]], circuit c16: d_ext = 8 and the complete lists of weight-8 (585) and weight-9 (16830) extended logicals.

The extended code is recomputed from the CNOT orders of c16 (both memory bases) and must equal the data file; the 45
translations act on its 225 columns (5 orbits).  For every weight w = 1..WMAX and every orbit k, mitm.c enumerates
all extended logicals of weight w that contain the representative of orbit k and no column of an orbit < k
(every logical can be translated into exactly this form for its lowest orbit); the results are expanded by the
45 translations, deduplicated and re-verified.  Expected: none of weight <= 7 (d_ext = 8), and for w = 8, 9 exactly
the sets of data/logicals/bb90_weight{8,9}_logicals_*_memory.json.  A complete enumeration of all sets (not only
syndrome-minimal ones).

    python code/bb90/lists.py --wmax 9      # about 9 CPU minutes (WMAX = 8: about 1.5 minutes)
Needs a C compiler (cc).
"""
import argparse
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common_cli import Verdict                      # noqa: E402
from bb90 import bbcode, ext as E                   # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--wmax", type=int, default=9)
ap.add_argument("--basis", nargs="+", default=["Z", "X"])
a = ap.parse_args()
code = bbcode.load_code()
V = Verdict()
tmp = Path(tempfile.mkdtemp(prefix="bb90mitm"))
binp = tmp / "mitm"
subprocess.run(["cc", "-O3", "-o", str(binp), str(Path(__file__).resolve().parent / "mitm.c")], check=True)
spec = E.circuit("c16")
G = E.order_group(spec)
assert len(G) == 45
for basis in a.basis:
    keys = E.ext_keys_from_file(code, basis)
    kc, sups, supkey = E.ext_columns(code, basis, spec)
    assert kc == keys, "extended code of c16 differs from the data file"
    perms = E.column_perms(code, basis, keys, sups, supkey, G)
    orbs = E.orbits(perms, len(keys))
    orb = {j: o for o, cl in enumerate(orbs) for j in cl}
    n = len(keys)
    H, L = E.hl(code, basis)
    nh = H.shape[0]
    Hm, Lm = E.key_matrices(keys, nh)
    ikey = [sum(int(b) << i for i, b in enumerate(Hm[:, j])) | (sum(int(b) << i for i, b in enumerate(Lm[:, j])) << nh)
            for j in range(n)]
    for w in range(1, a.wmax + 1):
        t0 = time.time()
        found = set()
        raw = 0
        for k, cl in enumerate(orbs):
            r = cl[0]
            A = [j for j in range(n) if orb[j] >= k and j != r]
            inp = f"{n} {w} {nh}\n" + " ".join(map(str, ikey)) + f"\n{r} {len(A)} " + " ".join(map(str, A)) + "\n"
            pr = subprocess.run([str(binp)], input=inp, capture_output=True, text=True, check=True)
            for line in pr.stdout.splitlines():
                S = tuple(sorted(int(x) for x in line.split()[1:]))
                assert len(set(S)) == w
                raw += 1
                for p in perms:
                    found.add(tuple(sorted(p[j] for j in S)))
        for S in found:
            x = np.zeros(n, np.uint8); x[list(S)] = 1
            assert not ((Hm @ x) % 2).any() and ((Lm @ x) % 2).any()
        sec = time.time() - t0
        if w <= 7:
            V(not found, f"bb90 {basis}-basis memory: no extended logical of weight {w} ({len(orbs)} orbit cases, "
                         f"{sec:.1f} s)")
        else:
            ref = {tuple(sorted(S)) for S in E.load_list(w, basis)}
            V(found == ref, f"bb90 {basis}-basis memory: weight-{w} extended logicals: {raw} in the orbit cases, "
                            f"{len(found)} after the 45 translations, equal to "
                            f"data/logicals/bb90_weight{w}_logicals_{basis}_memory.json ({len(ref)}) ({sec:.1f} s)")
V.exit()
