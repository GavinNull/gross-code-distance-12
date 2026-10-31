"""c2: exact weight <= 3 search on my own circuits (period 9 as given, and the period-10 non-wrapping stretch),
reset and no-reset, plus DEM mechanism-set equality P9 vs P10; controls Kunlun (expect 3) and E-038 n8 (expect none).
usage: uv run python -m search.experiments.e041_audit.c2_dist <basis> <Rreset_max> <Rnoreset_max> [circuit]"""
import json
import sys
import time

from search.experiments.e039_audit import fcore as F
from search.experiments.e041_audit import core as C

OUT = "results/E-041-audit"
SPECS = {"w9": "search/experiments/e041/bb18_w9_d4_spec.json", "kunlun": f"{OUT}/kunlun_spec.json",
         "n8": "search/experiments/e038/bb18_n8_d4_spec.json"}


def main():
    basis, Rr, Rn = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    name = sys.argv[4] if len(sys.argv) > 4 else "w9"
    S = C.load(SPECS[name])
    for reset, Rmax in ((True, Rr), (False, Rn)):
        for R in range(1, Rmax + 1):
            t0 = time.time()
            m9 = C.mechs(S, basis, R, reset=reset)
            w9 = F.min_weight3(m9)
            row = dict(circuit=name, basis=basis, reset=reset, R=R, mechs_P=len(m9), minw_le3_P=w9)
            if name == "w9":
                m10 = C.mechs(S, basis, R, reset=reset, Pst=S["P"] + 1)
                row.update(mechs_P10=len(m10), mechsets_equal=(set(m9) == set(m10)))
                if set(m9) != set(m10):
                    row["minw_le3_P10"] = F.min_weight3(m10)
                if w9 is None and R <= 2:
                    row["has_w4"] = C.has_w4(m9)
            row["sec"] = round(time.time() - t0, 1)
            print(json.dumps(row), flush=True)
            with open(f"{OUT}/c2_dist.jsonl", "a") as f:
                f.write(json.dumps(row) + "\n")


if __name__ == "__main__":
    main()
