"""E-040 impossibility audit: class definition vs the frozen evaluator.  Random canonical legal T(P) schedules must
pass evaluators.candidate.validate_schedule and give deterministic detectors (noiseless DEM builds); schedules that
satisfy every condition except determinism must be rejected or give a non-deterministic detector.
   PYTHONPATH=.:tests uv run python -m search.experiments.e040_audit_imp.legal_eval"""
import itertools
import json
import random

import numpy as np

from evaluators.candidate import memory_circuit, parse_schedule, validate_schedule
from search.experiments.e040_audit_imp.codes_a import code
from search.experiments.e040_audit_imp.enum_a import side
from search.experiments.e040_audit_imp.inject_a import spec


def det_ok(C, sp):
    try:
        for b in "XZ":
            memory_circuit(sp, C["css"], b, 3).detector_error_model()
        return True
    except Exception:
        return False


def main():
    rng = random.Random(3)
    out = {}
    for name in ("bb90", "gross"):
        C = code(name)
        for P in (8, 9):
            z = np.load(f"results/E-040-audit-imp/canon_P{P}.npz")
            good = 0
            for i in rng.sample(range(len(z["TX"])), 15):
                sp = parse_schedule(spec(C, z["TX"][i].tolist(), z["TZ"][i].tolist(), P))
                good += (not validate_schedule(sp, C["css"])) and det_ok(C, sp)
            S = side(P)
            nd = rej = 0
            while nd + rej < 15:
                tx, tz = S[rng.randrange(len(S))], S[rng.randrange(len(S))] + rng.randrange(-P, P)
                mod_ok = all((tx[i] - tz[3 + j]) % P and (tx[3 + j] - tz[i]) % P for i in range(3) for j in range(3))
                det = all((tx[i] - tz[3 + j]) // P == (tx[3 + j] - tz[i]) // P for i in range(3) for j in range(3))
                if not mod_ok or det:
                    continue
                sp = parse_schedule(spec(C, tx.tolist(), tz.tolist(), P))
                if validate_schedule(sp, C["css"]):
                    rej += 1
                elif not det_ok(C, sp):
                    nd += 1
            out[f"{name}_P{P}"] = {"legal_pass": f"{good}/15", "nondet_rejected": rej, "nondet_detected_by_stim": nd}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
