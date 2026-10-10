"""E-023 diagnostic: the lowest-weight decoder failures found by fixed-weight MC (w <= wmax).  For each failing sample:
which columns (fault types via stim explain), does exact MLE (HiGHS MILP, search/decoders/exact.py) decode it correctly,
and does the decoder still fail with priors matched to p = 1e-4 (instead of the fixed P_DEC = 1e-3)?

    PYTHONPATH=. uv run python -m search.experiments.e023.diag_lowfail --prob m54_repo --model sd6 --wmax 2
"""
from __future__ import annotations

import argparse
import glob
import json

import numpy as np

from search.experiments.e023.common import OUT, P_DEC, make_decoder, sectors
from search.experiments.e023.fixedweight import decode_one


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--prob", required=True)
    ap.add_argument("--model", default="sd6")
    ap.add_argument("--wmax", type=int, default=2)
    ap.add_argument("--decoders", default="bposd,relay")
    a = ap.parse_args(argv)
    from search.decoders.exact import MilpMLE
    secs = sectors(a.prob, a.model, P_DEC)
    secs4 = sectors(a.prob, a.model, 1e-4)
    out = []
    for si, sec in enumerate(secs):
        H = sec.H.tocsc()
        mle = MilpMLE(sec.H, np.log((1 - sec.q) / sec.q))
        decs = {nm: make_decoder(sec, nm) for nm in a.decoders.split(",")}
        decs4 = {nm: make_decoder(secs4[si], nm) for nm in a.decoders.split(",")}
        for f in sorted(glob.glob(str(OUT / "fw" / f"{a.prob}_{a.model}_w*_b*.npz"))):
            z = np.load(f)
            w = int(z["w"])
            if w > a.wmax:
                continue
            for nm in decs:
                fl = z[f"{sec.label}_{nm}_f"]
                for i in np.flatnonzero(fl):
                    S = z[f"{sec.label}_sets"][i].tolist()
                    e = np.zeros(sec.ncol, np.uint8)
                    e[S] = 1
                    syn = ((H @ e) % 2).astype(np.uint8)
                    tr = (sec.L @ e) % 2
                    r = mle.decode(syn, time_limit=60)
                    mle_fail = None if r.e is None else bool((((sec.L @ r.e) % 2) != tr).any())
                    eh = decs[nm](syn)
                    wt_dec = int(eh.sum())
                    f4 = bool((decode_one(secs4[si], decs4[nm], syn, nm) != tr).any())
                    row = dict(sector=sec.label, w=w, dec=nm, cols=S, keys=[list(map(list, sec.keys[c])) for c in S],
                               q=[float(sec.q[c]) for c in S], mle_status=r.status, mle_fail=mle_fail,
                               dec_correction_weight=wt_dec, fails_with_priors_p1e4=f4)
                    out.append(row)
                    print(json.dumps({k: v for k, v in row.items() if k != "keys"}), flush=True)
    (OUT / f"diag_lowfail_{a.prob}_{a.model}_w{a.wmax}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
