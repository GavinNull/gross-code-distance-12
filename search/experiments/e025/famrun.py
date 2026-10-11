"""E-025: run the (audited-type) nogood CEGAR on a family -- subgroup family F(H) or mixed family (only the given
units split into H-orbits, the rest colour-symmetric) -- at period P, with exact-lift screening of model candidates
(e021.liftscreen R = 1..rmax both bases; a lifting candidate's exact timing is excluded and the search continues).
Optional phase guidance from a spec (times mapped to the target period) = 'period squeezing' (method c).

    PYTHONPATH=.:tests uv run python -m search.experiments.e025.famrun --P 17 --sub "0,3;3,0" --split X0,Z2
"""
import argparse
import json
import time
from pathlib import Path

import search.experiments.e021.nwfull as NF
from search.experiments.e024a.cegar import spec_of
from search.experiments.e025.cegar_lib import Cegar
from search.experiments.e025.exact_cp import make_family

OUT = Path("results/E-025-gross12-perchk-period")


def guide_phases(C, F, spec_path, P):
    """phases for the order-encoding literals [t_i >= v] from a spec of another period P0: per check, keep the
    CNOT order and squeeze offsets proportionally to fit window <= P-3; start residue scaled."""
    from search.experiments.e024a.selftest import times_of_spec
    d = json.load(open(spec_path))
    P0 = d["period"]
    t0 = times_of_spec(F, d, P0)
    M = C.M
    t = []
    for i, x in enumerate(t0):
        t.append(min(M.TM, int(round(x * P / P0))))
    ph = []
    for i in range(len(t)):
        for v in range(1, M.TM + 1):
            ph.append(M.ge(i, v) if t[i] >= v else -M.ge(i, v))
    return ph


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--sub", default="1,2;0,3")
    ap.add_argument("--split", default="")
    ap.add_argument("--max_sec", type=float, default=3600)
    ap.add_argument("--maxwin", type=int, default=None)
    ap.add_argument("--winunits", default="")
    ap.add_argument("--guide", default="")
    ap.add_argument("--rmax", type=int, default=6)
    ap.add_argument("--tighten", type=int, default=1)
    ap.add_argument("--tag", required=True)
    a = ap.parse_args()
    t0 = time.time()
    F = make_family(a.sub, a.split)
    recs, skipped = NF.prepare_full(F, "XZ")
    wu = {(x[0], int(x[1:])) for x in a.winunits.split(",")} if a.winunits else None
    C = Cegar(F, a.P, recs, maxwin=a.maxwin, winunits=wu, use_tighten=bool(a.tighten))
    print(f"P={a.P} sub={a.sub} split={a.split} |H|={len(F.Hs)} items={len(F.items)} reps={len(recs)} "
          f"skipped={skipped}", flush=True)
    phases = guide_phases(C, F, a.guide, a.P) if a.guide else None
    log = {"P": a.P, "sub": a.sub, "split": a.split, "H": len(F.Hs), "reps": len(recs), "lift": []}
    from search.experiments.e021.liftscreen import screen
    ncand = [0]

    def on_model(t):
        ncand[0] += 1
        sp = OUT / f"{a.tag}_cand{ncand[0]}.json"
        sp.write_text(json.dumps(spec_of(F, t, a.P)))
        r = screen(str(sp), a.rmax)
        r["it"] = C.it
        print("exact:", r, flush=True)
        log["lift"].append(r)
        if r["status"] == "CERTIFIED":
            log["spec"] = str(sp)
            return True
        C.M.add([-C.M.eq(i, t[i]) for i in range(len(t))])
        return False

    st, t, info = C.run(a.max_sec, on_model=on_model, verbose=True, phases=phases)
    if st == "ACCEPTED":
        st = "CERTIFIED"
    log.update(status=st, sec=round(time.time() - t0, 1), **{k: v for k, v in info.items() if k != "sec"})
    print(f"STATUS P={a.P} sub={a.sub} split={a.split} {st} it={info['it']} best={info.get('best')} "
          f"cands={ncand[0]} {log['sec']}s", flush=True)
    (OUT / f"{a.tag}.json").write_text(json.dumps(log))


if __name__ == "__main__":
    main()
