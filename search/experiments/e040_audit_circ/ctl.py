"""Control schedules with the same per-check CNOT orders but separable timing (X block, then Z block, period 16):
by theory-B Prop. 3 every extended logical lifts in the bulk, so the lift solver must report all of them.

  uv run python -m search.experiments.e040_audit_circ.ctl g10
"""
import json
import sys

from search.experiments.e040_audit_circ.common import OUT, gross, load


def seg(sd):
    P = int(sd["period"])

    def re(ch, base):
        p = int(ch["prep"]) % P
        ev = sorted(((int(t) - p) % P, int(q)) for q, t in ch["cnots"])
        return {"prep": base, "meas": base + 7, "cnots": [[q, base + 1 + i] for i, (_, q) in enumerate(ev)]}
    return {"format": "qec-schedule/v1", "period": 16, "x_checks": [re(c, 0) for c in sd["x_checks"]],
            "z_checks": [re(c, 8) for c in sd["z_checks"]]}


if __name__ == "__main__":
    from evaluators import candidate as cand
    name = sys.argv[1]
    s = seg(load(name))
    print(cand.validate_schedule(cand.parse_schedule(s), gross()))
    p = OUT / f"segctl_{name}.json"
    p.write_text(json.dumps(s))
    print(p)
