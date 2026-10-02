"""S1c：S1 的平移依赖在真实调度上是否出现（IBM depth-8、Strikis Fig.12 的 gross 调度；BB72 自由窗口变体）。
用法：uv run python s1c_canonical_real_schedules.py
"""
import random

from common import cand, circuit_hash
from evaluators.tasks import build_code, get_task
from s1_canonical_hash import shifted
import s8_free_schedules_false_reject as s8


def n_distinct(spec, code, R=2):
    return len({circuit_hash(cand.build_circuits(shifted(spec, s), code, R)) for s in range(spec.period)})


def main():
    from baselines.bb_code import BBCode
    from baselines.gross import parse_poly
    from baselines.schedule import ibm_depth8
    from baselines.strikis import strikis_fig12
    from schedule_helpers import from_baseline
    code, _ = build_code(get_task("gross-sd6-p4e-3"), None)
    bb = BBCode(12, 6, parse_poly(["x^3", "y", "y^2"]), parse_poly(["y^3", "x", "x^2"]))
    for name, sch in (("IBM depth-8", ibm_depth8(bb)), ("Strikis Fig.12", strikis_fig12(bb)[0])):
        spec = from_baseline(sch)
        print(f"gross {name}: distinct circuits over {spec.period} global shifts = {n_distinct(spec, code)}; "
              f"submitted == canonical circuit: "
              f"{circuit_hash(cand.build_circuits(spec, code, 2)) == circuit_hash(cand.build_circuits(spec.canonical(), code, 2))}")
    rng = random.Random(5)
    bbc = s8.bb72()
    tot = dep = 0
    while tot < 20:
        s = s8.bb_free(rng, rng.randint(10, 14))
        if s is None or cand.validate_schedule(s, bbc):
            continue
        tot += 1
        dep += n_distinct(s, bbc) > 1
    print(f"BB72 free-window variants: {dep}/{tot} have shift-dependent circuits (same hash, different circuits)")


if __name__ == "__main__":
    main()
