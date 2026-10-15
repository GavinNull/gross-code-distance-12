"""Audit rev-g (3): do the Fig. 12 retiming obstructions (Table S3 / tab:fig12) need logicals other than
"ten data + one length-2 residual"?  Re-run the shipped CEGAR encoders (release/zenodo/code/sat, --pin-fig12) with the
frame model restricted to the 360 (per basis) logicals of that form, whose model->circuit direction is the one proven
in SM S9.  UNSAT  => the obstruction rests only on the proven direction.  CANDIDATE => it relies on other logicals.
Also: with the UNRESTRICTED list, record which logical types produce the nogoods of the shipped certificates.
    uv run python research/audits/2026-10-14-revg-scripts/g4_len2only.py   (from the project root)
"""
import json, sys, time
from collections import Counter
sys.path.insert(0, "release/zenodo/code")
from sat import frame, enc_primary, enc_second
from sat.common import fig12_labels, table

T = table(); F12 = fig12_labels()
orig_prepare = frame.prepare
MODE = {"filter": False}
STATS = {}


def ltype(F, r):
    hs = [e for e in r["evs"] if e[0] == "h"]
    if not hs:
        return "data_only"
    if len(hs) > 1:
        return f"{len(hs)}res"
    _, a, V = hs[0]
    o = F12[r["kind"]][a]
    last2 = {int(T[r["kind"]][a][o[4]]), int(T[r["kind"]][a][o[5]])}
    if set(V) == last2:
        return "1res_len2"
    return f"1res_|V|={len(V)}"


def prepare(F, kind_data, kinds="XZ"):
    recs, skipped = orig_prepare(F, kind_data, kinds)
    STATS["types_all"] = dict(Counter(ltype(F, r) for r in recs))
    if MODE["filter"]:
        recs = [r for r in recs if ltype(F, r) == "1res_len2"]
    STATS["kept"] = len(recs)
    return recs, skipped


frame.prepare = prepare
orig_eval = frame.evaluate
NOG = Counter()


def evaluate(F, recs, feasible):
    out = orig_eval(F, recs, feasible)
    for r, _, _ in out:
        NOG[ltype(F, r)] += 1
    return out


frame.evaluate = evaluate

FAM = [("primary", dict(P=P), f"primary_P{P:02d}_pipelined") for P in range(8, 13)]
FAM += [("primary", dict(P=38, nowrap=1), "primary_P38_common_frame"),
        ("primary", dict(P=16, nowrap=1, sub="0,0"), "primary_P16_common_frame_nosym")]
FAM += [("second", dict(P=P), f"second_P{P:02d}_sym24") for P in range(8, 13)]
FAM += [("second", dict(P=9, sub=s), f"second_P09_subgroup_{s}") for s in
        ("1,2", "1,5", "0,3;2,1", "2,1", "2,4", "4,5", "0,3;3,0", "0,3;6,0", "3,3", "4,2")]
FAM += [("second", dict(P=10, sub=s), f"second_P10_subgroup_{s}") for s in ("1,2", "0,3;3,0", "2,4")]
only = sys.argv[1:] or None
OUTF = "research/audits/2026-10-14-revg-scripts/g4_len2only" + ("_" + "_".join(only) if only else "") + ".json"
res = {}
quiet = lambda *a, **k: None
for enc, kw, name in FAM:
    if only and not any(o in name for o in only):
        continue
    for filt in (False, True):
        MODE["filter"] = filt; NOG.clear(); t0 = time.time()
        mod = enc_primary if enc == "primary" else enc_second
        st, M, info = mod.run(pin=True, max_sec=900, log=quiet, **kw)
        key = f"{name}|{'len2only' if filt else 'all'}"
        res[key] = dict(status=st, info=info, rec_types=STATS.get("types_all"), kept=STATS.get("kept"),
                        nogood_types=dict(NOG), sec=round(time.time() - t0, 1))
        print(key, json.dumps(res[key]), flush=True)
        json.dump(res, open(OUTF, "w"), indent=1)
