"""E-037 audit: compare my DEMs (ibm faithful / ibm reset / ibm stim / sd6) with each other and with E-037's
cols.json files (the column lists their OPB instances were built from).

  uv run python search/experiments/e037_audit/compare_dem.py SRC [SRC ...]
Column identity: detector sets must coincide as a family (every column has a distinct detector set); observables are
compared modulo detectors (span(D, L_mine) == span(D, L_theirs)), since my logical basis is computed independently.
"""
import glob
import json
import sys
from pathlib import Path

import mydem

ROOT = Path(__file__).resolve().parents[3]
RES = ROOT / "results" / "E-037-ibm-cert"


def theirs(src):
    stem = src.replace(":", "_")
    for f in sorted(glob.glob(str(RES / "*" / f"{stem}_W*.cols.json"))):
        if "_p1" in f:
            continue
        return json.loads(Path(f).read_text()), f
    return None, None


def compare(a, b, label):
    da = {tuple(d): j for j, d in enumerate(a["D"])}
    db = {tuple(d): j for j, d in enumerate(b["D"])}
    assert len(da) == len(a["D"]) and len(db) == len(b["D"]), "duplicate detector sets"
    out = dict(pair=label, n=(len(da), len(db)), ndet=(a["ndet"], b["ndet"]))
    if set(da) != set(db) or a["ndet"] != b["ndet"]:
        out.update(same=False, only_a=len(set(da) - set(db)), only_b=len(set(db) - set(da)))
        return out
    order = sorted(da)
    Da = [order[i] for i in range(len(order))]
    Drows = mydem.rows_from(Da, a["ndet"])
    La = mydem.rows_from([a["L"][da[d]] for d in order], a["nobs"])
    Lb = mydem.rows_from([b["L"][db[d]] for d in order], b["nobs"])
    ok, ranks = mydem.same_logicals_mod_det(Drows, La, Lb)
    # identical observable tuples too? (meaningful only when both use the same observables, e.g. sd6 vs sd6)
    ident = all(tuple(a["L"][da[d]]) == tuple(b["L"][db[d]]) for d in order)
    out.update(same=ok, logical_ranks=ranks, identical_L=ident)
    return out


def main():
    res = []
    for src in sys.argv[1:]:
        kind, name, typ, R = src.split(":")
        mine = mydem.load(src)
        t, f = theirs(src)
        if t is not None:
            r = compare(mine, t, f"mine {src} vs E-037 {Path(f).name}")
            res.append(r); print(json.dumps(r), flush=True)
        if kind == "ibm":
            for alt in ("ibmreset", "ibmstim"):
                o = mydem.load(f"{alt}:{name}:{typ}:{R}")
                r = compare(mine, o, f"mine ibm vs mine {alt} {name}:{typ}:{R}")
                res.append(r); print(json.dumps(r), flush=True)
    return res


if __name__ == "__main__":
    main()
