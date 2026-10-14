"""E-026b stage C: practical-decoder weight-5 kernel coefficient D5 per noise model (E-026 kernel2 + structural,
re-done with the model's priors).
For each (circ, basis): enumerate the exact family at R = 2, 3 with (column, mask) keys (lead.enumerate_keys; fig12 W11
complete, p18 W12 type (b)); for each model:
  S5(model)   = per-round (R3 - R2) sum over logicals and 5-subsets of the product of the model's term priors at PE;
  kernel      = n samples (uniform logical of the R3 family, uniform 5-subset S), syndrome = XOR of term detectors,
                decoded on the R3 DEM of the SAME model with priors at P_DEC = 2e-3 (BP-OSD IBM, Relay-BP relay5);
                failure fraction weighted by prod(prior of S) (as E-026 structural.py);
  D5(dec)     = S5 x weighted failure fraction  (per round, Z+X after summing bases), coefficient = D5 / PE^5.
For t = 5 < W - t the ideal decoder is correct (it fails only via the 6|5 split where 6 faults are more likely, recorded
as 'ideal'), so these failures are the decoders' own.  Single process.
  PYTHONPATH=.:tests uv run python -m search.experiments.e026b.kernel_lam --models lam0,lam0.1,lam0.3,lam1 --n 600"""
import argparse, itertools, json, time
import numpy as np

import search.experiments.e026.lift_enum as LE
import search.experiments.e026.dem as DM
from search.experiments.e026.fw import decoders, P_DEC
from search.experiments.e026b.common import OUT, noisy as noisy_b
from search.experiments.e026b.lead import enumerate_keys, set_model

PE = 1e-3
FAM = {"fig12": "w11", "p18": "w11z"}


def S_t(arr, lq, t):
    comb = np.array(list(itertools.combinations(range(arr.shape[1]), t))); tot = 0.0
    for i in range(0, len(arr), 2000):
        tot += np.exp(lq[arr[i:i + 2000]][:, comb].sum(2)).sum()
    return float(tot)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="lam0,lam0.1,lam0.3,lam1"); ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--circs", default="p18,fig12"); ap.add_argument("--seed", type=int, default=26601)
    a = ap.parse_args()
    od = OUT / "kernel"; od.mkdir(parents=True, exist_ok=True)
    t0 = time.process_time()
    for circ in a.circs.split(","):
        mode = FAM[circ]
        for basis in "ZX":
            enum = {R: enumerate_keys(circ, basis, mode, R) for R in (2, 3)}
            key_idx = enum[3][2]
            for m in a.models.split(","):
                out = od / f"{circ}_{basis}_{m}_s{a.seed}_n{a.n}.json"
                if out.exists():
                    continue
                set_model(m)
                S5 = {}
                for R in (2, 3):
                    arr, keys, _ = enum[R]
                    G, Z, ndet = LE.groups(circ, basis, R, key_idx)
                    obs = dict(LE.OBS)
                    pr = np.array([(Z.get(mk, 0.0) if col == -1 else G.get(col, {}).get(mk, 0.0)) for col, mk in keys])
                    with np.errstate(divide="ignore"):
                        lq = np.log(pr)
                    alive = (pr[arr] > 0).all(1)
                    S5[R] = S_t(arr[alive], lq, 5)
                # kernel on R3
                arr, keys, _ = enum[3]
                arr = arr[alive]
                DM.noisy = lambda c, b, R, p, _m=m: noisy_b(c, b, R, p, _m)
                D = DM.Dem(circ, basis, 3, P_DEC); decs = decoders(D)
                assert D.ndet == ndet
                tdet = [[b for b in range(mk.bit_length()) if (mk >> b) & 1] for col, mk in keys]
                tob = [0 if col == -1 else obs[(col, mk)] for col, mk in keys]
                rng = np.random.default_rng([a.seed, ["p18", "fig12"].index(circ), "ZX".index(basis), int(1000 * float(m[3:]))])
                ws, fl = [], {nm: [] for nm in decs}
                wsum = 0.0; wideal = 0.0; wfail = {nm: 0.0 for nm in decs}; fails = {nm: 0 for nm in decs}
                for _ in range(a.n):
                    L = arr[rng.integers(len(arr))]
                    S = rng.choice(L, 5, replace=False); C = np.setdiff1d(L, S)
                    syn = np.zeros(D.ndet, np.uint8); ob = 0
                    for x in S:
                        syn[tdet[x]] ^= 1; ob ^= int(tob[x])
                    tr = np.array([(ob >> k) & 1 for k in range(D.Lr.shape[0])], np.uint8)
                    sS, sC = lq[S].sum(), lq[C].sum()
                    fi = 1 if sC > sS + 1e-12 else (0.5 if abs(sC - sS) <= 1e-12 else 0)
                    wS = float(np.exp(sS)); wsum += wS; wideal += fi * wS; ws.append(wS)
                    for nm, f in decs.items():
                        bad = bool(((D.Lr @ f(syn)) % 2 != tr).any()); fl[nm].append(bad)
                        if bad:
                            fails[nm] += 1; wfail[nm] += wS
                s5 = S5[3] - S5[2]
                r = dict(circ=circ, basis=basis, model=m, n=a.n, S5_per_round=s5, fails=fails,
                         frac_w={nm: wfail[nm] / wsum for nm in decs}, frac_ideal_w=wideal / wsum,
                         D5_per_round={nm: s5 * wfail[nm] / wsum for nm in decs}, cpu=time.process_time() - t0)
                out.write_text(json.dumps(r, indent=1))
                np.savez(out.with_suffix('.npz'), w=np.array(ws), S5=s5, **{nm: np.array(v) for nm, v in fl.items()})
                print(json.dumps(r), flush=True)


if __name__ == "__main__":
    main()
