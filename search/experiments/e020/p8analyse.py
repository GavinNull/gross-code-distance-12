"""E-020 step 1b: inspect the complete P=8 legal set: colour-uniformity, interleaving pattern, determinism (stim);
write evaluator-format candidate JSONs for the exact lift checker.

    PYTHONPATH=.:tests uv run python -m search.experiments.e020.p8analyse
"""
from __future__ import annotations

import json

import numpy as np

from search.experiments.e018.gen import SPEC0, XCOL, ZCOL, deterministic, legal_spec, pattern, spec_of

OUT = "results/E-020-gross-perchk-pipeline"


def main():
    d = json.load(open(f"{OUT}/p8_legal.json"))
    px = np.array([c.prep for c in SPEC0.x_checks]); pz = np.array([c.prep for c in SPEC0.z_checks])
    rows = []
    for n, sv in enumerate(d["sols"]):
        sv = np.array(sv)
        dx, dz = (sv[:72] - px) % 8, (sv[72:] - pz) % 8
        cu = all(len(set(dx[XCOL == k])) == 1 for k in range(3)) and all(len(set(dz[ZCOL == k])) == 1 for k in range(3))
        spec = spec_of(dx, dz, name=f"p8_{n}")
        pat = pattern(dx, dz)
        det = deterministic(spec)
        rows.append({"n": n, "colour_uniform": cu,
                     "dx_by_colour": [sorted(set(dx[XCOL == k].tolist())) for k in range(3)],
                     "dz_by_colour": [sorted(set(dz[ZCOL == k].tolist())) for k in range(3)],
                     "legal": legal_spec(spec), "deterministic": det, "patterns": dict(pat)})
        print(rows[-1], flush=True)
        json.dump(spec.to_dict(), open(f"{OUT}/p8_cand{n}.json", "w"))
    json.dump(rows, open(f"{OUT}/p8_analyse.json", "w"), indent=1)


if __name__ == "__main__":
    main()
