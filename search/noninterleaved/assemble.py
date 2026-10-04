"""E-013：把 X 侧与 Z 侧的 y 奇偶两色块顺序组装成完整的深度 8 电路，交评估器做电路级距离检查。lead。

    PYTHONPATH=.:tests uv run python -m search.noninterleaved.assemble --x 2 14 --z 12 0
"""
import argparse
import json
import sys
import time

from search.noninterleaved.colour_search import order_terms
from search.noninterleaved.schedules import build_schedule, interleaving, layer_conflict_free
from search.noninterleaved.run import OUT
from search.noninterleaved.two_colour import M, ctx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--x", type=int, nargs=2, required=True, help="X 侧 (偶行, 奇行) 块顺序编号")
    ap.add_argument("--z", type=int, nargs=2, required=True, help="Z 侧 (偶行, 奇行) 块顺序编号")
    a = ap.parse_args()
    cx, cz = ctx("X"), ctx("Z")
    code = cx["code"]
    xb = [cx["ok"][a.x[0]], cx["ok"][a.x[1]]]
    zb = [cz["ok"][a.z[0]], cz["ok"][a.z[1]]]
    x_spec = [(0, order_terms("X", *xb[(i % M) % 2])) for i in range(code.n2)]
    z_spec = [(4, order_terms("Z", *zb[(i % M) % 2])) for i in range(code.n2)]
    sched = build_schedule(code, x_spec, z_spec, name=f"bb108_twocolour_x{a.x}_z{a.z}")
    inter = interleaving(sched)
    print("blocks X even/odd:", xb, " Z even/odd:", zb)
    print("layer conflict free:", layer_conflict_free(sched))
    print("non-interleaving check:", {k: v for k, v in inter.items() if k != "pairs"} if isinstance(inter, dict) else inter)
    sys.path.insert(0, "tests")
    from schedule_helpers import from_baseline

    from evaluators.pipeline import screen
    spec = from_baseline(sched)
    t0 = time.time()
    rep = screen("bb108-dcirc", None, spec)
    print(f"evaluator screen ({time.time() - t0:.0f}s):")
    print(rep.to_text()[:4000])
    out = OUT / f"e013_assembled_x{a.x[0]}_{a.x[1]}_z{a.z[0]}_{a.z[1]}.json"
    out.write_text(json.dumps({"x_blocks": xb, "z_blocks": zb, "spec": spec if isinstance(spec, dict) else str(spec),
                               "report": rep.to_text()}, default=str, indent=1))


if __name__ == "__main__":
    main()
