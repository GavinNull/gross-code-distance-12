"""E-045 audit: the four R = 1 IBM-model witnesses (fault lists from results/E-045-crocker/partB/persist.jsonl) placed in
cycle 0, floor(R/2) or R-1 of MY (R + 2)-cycle model (ibm_audit.sim), R = 1, 2, 7, 13, 25: XOR of detector columns
empty, same observables; removing any one fault leaves detectors.  auditor.

  uv run python -m search.experiments.e045_audit.persist_audit
"""
import json
from pathlib import Path

import numpy as np

from search.experiments.e045_audit import ibm_audit as ia

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "results/E-045-audit/partB/persist_audit.jsonl"


def main():
    W = [json.loads(l) for l in (ROOT / "results/E-045-crocker/partB/persist.jsonl").read_text().splitlines() if l.strip()]
    seen, res = set(), []
    for w in W:
        key = (w["code"], w["typ"])
        if key in seen or "faults" not in w:
            continue
        seen.add(key)
        code = ia.mydem.BB(w["code"])
        cyc = code.cycle()
        for R in (1, 2, 7, 13, 25):
            S = ia.sim(code, w["typ"], R, 2)
            idx = {}
            for f, (c, gi, b, qs, g, rnd) in enumerate(S["sites"]):
                idx.setdefault((c, rnd, tuple(cyc[gi]), tuple(qs)), f)
            for place in sorted({0, R // 2, R - 1}):
                fs = []
                for c0, rnd, gate, qs in w["faults"]:
                    assert c0 == 0
                    fs.append(idx[(place, rnd, tuple(gate), tuple(qs))])
                d = S["D"][:, fs].sum(axis=1) % 2
                o = S["L"][:, fs].sum(axis=1) % 2
                drops = [int((S["D"][:, fs[:k] + fs[k + 1:]].sum(axis=1) % 2).sum()) for k in range(len(fs))]
                r = dict(code=w["code"], typ=w["typ"], W=len(fs), R=R, cycle=place, det=int(d.sum()),
                         obs=np.flatnonzero(o).tolist(), drop_min=min(drops))
                res.append(r)
                print(json.dumps(r), flush=True)
    OUT.write_text("".join(json.dumps(r) + "\n" for r in res))


if __name__ == "__main__":
    main()
