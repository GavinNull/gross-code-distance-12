"""Cheap screening of a single code: n, k, constraints, distance (exact or upper bound), figures of merit."""
from __future__ import annotations

import time

from search.codes.constraints import check_constraints
from search.codes.distance import distance_exact_milp, distance_upper_bound_bposd
from search.codes.equivalence import canonical_key


def merits(n: int, k: int, d: int | None) -> dict:
    if not d or k == 0:
        return {"kd2_n": 0.0, "kd_n": 0.0, "rate": k / n if n else 0.0}
    return {"kd2_n": k * d * d / n, "kd_n": k * d / n, "rate": k / n,
            # IBM "net encoding rate" counts check qubits too (BB: n data + n checks)
            "net_rate": k / (2 * n)}


def screen_code(code, bposd_trials: int = 200, bposd_budget: float = 30.0, exact_max_n: int = 100,
                milp_time: float = 300.0, thickness: bool = True, seed: int = 0,
                max_weight: int = 6) -> dict:
    """Full single-code screen.  d_kind = "exact" only when the MILP proved optimality."""
    t0 = time.time()
    rec = {"name": code.name, **code.to_dict(), "k": code.k, "key": str(canonical_key(code))}
    rec.update(check_constraints(code, max_weight=max_weight, thickness=thickness))
    if rec["k"] == 0:
        rec.update({"d": None, "d_kind": "n/a", "d_lower": None, **merits(code.n, 0, None)})
        rec["seconds"] = time.time() - t0
        return rec
    css = code.to_css()
    sym = code.is_abelian
    ub = distance_upper_bound_bposd(css, trials=bposd_trials, time_budget=bposd_budget, seed=seed,
                                    symmetric=sym)
    rec["d_ub_bposd"] = ub["d_ub"]
    rec["bposd_trials"] = ub.get("Z_trials", 0) + ub.get("X_trials", 0)
    rec["d"], rec["d_kind"], rec["d_lower"] = ub["d_ub"], "upper", None
    if code.n <= exact_max_n:
        ex = distance_exact_milp(css, time_limit=milp_time, upper=ub["d_ub"], symmetric=sym,
                                 translation_n2=code.n2 if sym else None)
        rec["d_lower"] = ex["d_lower"]
        rec["d"] = ex["d_upper"]
        rec["d_kind"] = "exact" if ex["exact"] else "upper"
        rec["milp_seconds"] = round(ex["seconds"], 2)
    rec.update(merits(code.n, rec["k"], rec["d"]))
    rec["seconds"] = round(time.time() - t0, 2)
    return rec
