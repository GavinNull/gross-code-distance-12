"""E-025 step 1b: transfer a colour-symmetric core (set of logical orbit reps) to the PER-CHECK-FREE family: keep only
the G24 translates of the core reps (sound for UNSAT: fewer logicals = easier blocking), apply the same window limit
to every check of the limited colour units, and run the nogood CEGAR.
UNSAT  => even with per-check freedom, those checks cannot all have the short window (at this P).
MODEL_SAT => per-check freedom breaks this core (the symmetric obstruction relied on the translates sharing times).

    PYTHONPATH=.:tests uv run python -m search.experiments.e025.core_percheck results/.../core_P24_w14X0.json --P 24
"""
import argparse
import json
import time
from pathlib import Path

import search.experiments.e021.nwfull as NF
from search.experiments.e021.extgen import ext_general
from search.experiments.e021.mono import fig12_labels
from search.experiments.e025.cegar_lib import Cegar
from search.experiments.e025.exact_cp import make_family

OUT = Path("results/E-025-gross12-perchk-period")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("core")
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--maxwin", type=int, default=None)
    ap.add_argument("--winunits", default="", help="colour units, e.g. X0,Z2 (all their checks get the limit)")
    ap.add_argument("--sub", default="", help="family for the transfer ('' = per-check free)")
    ap.add_argument("--max_sec", type=float, default=3600)
    ap.add_argument("--tag", required=True)
    a = ap.parse_args()
    core = json.load(open(a.core))
    Fs = make_family("1,2;0,3")
    F = make_family(a.sub)
    f12 = fig12_labels()
    orbit = {"X": set(), "Z": set()}
    for r in core["recs"]:
        kind = r["kind"]
        E = ext_general(kind, f12[kind])
        for g, Pm in zip(E["group"], E["perms"]):
            orbit[kind].add(tuple(sorted(int(Pm[j]) for j in r["S"])))
    recs, sk = NF.prepare_full(F, "XZ")
    keep = [r for r in recs if tuple(sorted(r["S"])) in orbit[r["kind"]]]
    # the family's orbit reps under its own H: keep reps whose orbit meets the core orbit (orbit closed under G24)
    print(f"core reps {len(core['recs'])}, translates {sum(len(v) for v in orbit.values())}, kept recs {len(keep)} "
          f"(family |H|={len(F.Hs)})", flush=True)
    wu = None
    if a.winunits:
        from search.experiments.e024a.cegar import adapt
        adapt(F)
        wl = {(x[0], int(x[1:])) for x in a.winunits.split(",")}
        wu = set()
        for u in F.units:
            row = F.unit_rep[u]
            if (u[0], Fs.cls[row]) in wl:
                wu.add(u)
        print("window-limited units:", len(wu), flush=True)
    C = Cegar(F, a.P, keep, maxwin=a.maxwin, winunits=wu)
    t0 = time.time()
    st, t, info = C.run(a.max_sec, verbose=True)
    print(f"STATUS {st} {info} {time.time() - t0:.0f}s", flush=True)
    (OUT / f"{a.tag}.json").write_text(json.dumps({"status": st, "info": info, "kept": len(keep), "P": a.P,
                                                   "maxwin": a.maxwin, "winunits": a.winunits, "sub": a.sub,
                                                   "t": t}))


if __name__ == "__main__":
    main()
