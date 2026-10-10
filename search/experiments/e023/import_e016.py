"""E-023: import E-016's symmetry-closed low-weight logicals of BB108 (results/E-016-bb108-ler/lowweight/
{ibm,twocolour}_{Z,X}_logicals.json, key 'closure' = merged weighted+unweighted closure, sector column indices of the
E-016 10-round model at p = 1e-3) into the E-023 format.  E-023's bb108 sectors are built by the same construction;
every imported set is re-verified here (zero sector syndrome, nontrivial logical) -- a mismatch of column order would
fail this check.

    PYTHONPATH=. uv run python -m search.experiments.e023.import_e016
"""
from __future__ import annotations

import json

import numpy as np

from search.experiments.e023.common import OUT, P_DEC, ROOT, sectors

SRC = ROOT / "results" / "E-016-bb108-ler" / "lowweight"


def main():
    for circ in ("ibm", "twocolour"):
        prob = f"bb108_{circ}"
        secs = sectors(prob, "sd6", P_DEC)
        D = {"sectors": {}, "runs": [{"imported_from": str(SRC)}]}
        for sec in secs:
            src = json.loads((SRC / f"{circ}_{sec.label}_logicals.json").read_text())
            cl = src["closure"]
            sets = cl if isinstance(cl, list) else [x for v in cl.values() for x in v]
            H = sec.H.tocsc()
            ok = 0
            for S in sets:
                e = np.zeros(sec.ncol, np.uint8)
                e[list(S)] = 1
                assert not ((H @ e) % 2).any() and ((sec.L @ e) % 2).any(), (prob, sec.label, S)
                ok += 1
            ws = {}
            for S in sets:
                ws[len(S)] = ws.get(len(S), 0) + 1
            D["sectors"][sec.label] = {"logicals": [], "closed": sorted(map(list, sets), key=lambda s: (len(s), s)),
                                       "keys": [[list(k[0]), list(k[1])] for k in sec.keys],
                                       "closed_count_by_weight": {str(k): v for k, v in sorted(ws.items())}}
            print(prob, sec.label, "verified", ok, D["sectors"][sec.label]["closed_count_by_weight"], flush=True)
        (OUT / "lowweight" / f"{prob}.json").write_text(json.dumps(D))


if __name__ == "__main__":
    main()
