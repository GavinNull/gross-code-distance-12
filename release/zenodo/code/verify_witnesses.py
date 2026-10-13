"""Weight-11 witnesses for Fig. 12 and its period-8 retimings (SM S9; Corollary 1 upper bound d_circ <= 11).

Each file witnesses/weight11_<circuit>.json.gz lists, for a circuit, a basis and a number of rounds R, sets of eleven
explicit circuit faults (format in code/gross12/faults.py).  For each set this script rebuilds the SD6 circuit,
injects the eleven faults with probability 1 and checks: no detector fires, some logical observable flips, the
eleven faults belong to eleven distinct detector-error-model mechanisms (distinct detector/observable signatures
when injected alone), and their images (augmented with the H and L rows) are the eleven columns of the listed
weight-11 extended logical.

    python code/verify_witnesses.py                    # all files in witnesses/
    python code/verify_witnesses.py --max-per-case 5   # quick: first 5 witnesses of every (circuit, basis, R)
"""
import argparse
import gzip
import json

import numpy as np
import stim

from common_cli import Verdict, circuit, load_code
from gross12 import ext as E
from gross12.faults import inject, outcome
from gross12.paths import WITNESSES

ap = argparse.ArgumentParser()
ap.add_argument("--max-per-case", type=int, default=0)
ap.add_argument("files", nargs="*")
a = ap.parse_args()
code = load_code()
V = Verdict()
files = a.files or sorted(str(p) for p in WITNESSES.glob("weight11_*.json.gz"))
for fn in files:
    D = json.load(gzip.open(fn))
    for case in D["cases"]:
        name, basis, R = case["circuit"], case["basis"], case["R"]
        spec = circuit(name)
        noisy = E.noisy_circuit(spec, code, R, basis)
        H, L = E.hl(code, basis)
        n = code.n
        aug = noisy.copy()
        k0 = noisy.num_observables
        for r, row in enumerate(list(H) + list(L)):
            aug.append("OBSERVABLE_INCLUDE", [stim.target_rec(int(q) - n) for q in np.nonzero(row)[0]], k0 + r)
        keys = E.ext_keys_from_file(code, basis)
        lists = E.load_w11(basis)
        ws = case["witnesses"][: a.max_per_case or None]
        ok_n = 0
        cache = {}
        for w in ws:
            faults = w["faults"]
            dets, obs = outcome(inject(noisy, faults))
            sigs, imgs = set(), set()
            for f in faults:
                fk = (f["op"], tuple(f["paulis"]))
                if fk not in cache:
                    cache[fk] = outcome(inject(aug, [f]))
                d1, o1 = cache[fk]
                sigs.add((tuple(d1), tuple(o for o in o1 if o < k0)))
                hb = np.zeros(H.shape[0], np.uint8); lb = np.zeros(L.shape[0], np.uint8)
                for o in o1:
                    if k0 <= o < k0 + H.shape[0]:
                        hb[o - k0] = 1
                    elif o >= k0 + H.shape[0]:
                        lb[o - k0 - H.shape[0]] = 1
                imgs.add(hb.tobytes() + lb.tobytes())
            want = {keys[j] for j in lists[w["logical"]]}
            ok = (not dets) and bool(obs) and len(faults) == 11 and len(sigs) == 11 and imgs == want
            ok_n += ok
            if not ok:
                print("  failed:", name, basis, R, w["logical"], dets[:5], obs, len(sigs), imgs == want)
        V(ok_n == len(ws), f"[{name}] {basis} basis R={R}: {ok_n}/{len(ws)} weight-11 fault sets injected: no detector, "
                           f"observable flipped, 11 distinct mechanisms, images = the listed extended logical")
V.exit()
