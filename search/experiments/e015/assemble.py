"""Assemble a two-colour LRC (X side and Z side blocks per colour) into a depth-8 schedule, check legality and
non-interleaving, and get the evaluator's circuit-distance upper bound.

  registered task:  pipeline.screen(task, None, spec)  (task budget, derived seed)
  other codes:      evaluators.distance.upper_bound on build_circuits(spec, CSSCode, R=3) + sd6 noise

    PYTHONPATH=.:tests uv run python search/experiments/e015/assemble.py --code bb72 --hom 01 --x 0 0 --z 0 0 --task bb72-dcirc
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, "tests")
import numpy as np  # noqa: E402

from common import BLOCKS, OUT, get_code, homs_to_Zp, proper  # noqa: E402
from search.noninterleaved.colour_search import order_terms  # noqa: E402
from search.noninterleaved.schedules import build_schedule, interleaving, layer_conflict_free  # noqa: E402


def build(codekey, hk, xs, zs, colour=None):
    code = get_code(codekey)
    if colour is None:
        colour = [h for h in homs_to_Zp(code, 2) if f"{h['u']}{h['v']}" == hk][0]["colour"]
    xb = {c: BLOCKS[b] for c, b in enumerate(xs)}
    zb = {c: BLOCKS[b] for c, b in enumerate(zs)}
    assert proper(code, "X", colour, xb) and proper(code, "Z", colour, zb)
    x_spec = [(0, order_terms("X", *xb[colour[i]])) for i in range(code.n2)]
    z_spec = [(4, order_terms("Z", *zb[colour[i]])) for i in range(code.n2)]
    return code, build_schedule(code, x_spec, z_spec, name=f"{codekey}_h{hk}_x{xs}_z{zs}"), xb, zb


def evaluate(codekey, sched, task=None, seed=0, trials=1500, lns=96, workers=3, R=3):
    from schedule_helpers import from_baseline
    from evaluators.candidate import build_circuits, parse_schedule, validate_schedule
    from evaluators.codes import CSSCode
    spec = from_baseline(sched)
    code = get_code(codekey)
    t0 = time.time()
    if task:
        from evaluators.pipeline import screen
        from evaluators.tasks import build_code, get_task
        css, _ = build_code(get_task(task), None)
        assert (np.asarray(css.HX) == code.HX).all() and (np.asarray(css.HZ) == code.HZ).all()
        rep = screen(task, None, spec)
        return {"mode": f"screen({task})", "seconds": round(time.time() - t0), "report": rep.to_text(),
                "spec": parse_schedule(spec).to_dict()}
    from evaluators.distance import upper_bound
    from evaluators.noise import add_noise
    css = CSSCode.from_checks(code.HX, code.HZ, name=code.name)
    canon = parse_schedule(spec).canonical()
    probs = validate_schedule(canon, css)
    out = {"mode": "upper_bound", "validate_problems": probs[:5], "per_basis": {}, "spec": canon.to_dict()}
    for b in "ZX":
        circ = add_noise(build_circuits(canon, css, R)[b], "sd6", 1e-3)
        r = upper_bound(circ, seed=seed, methods=("graphlike", "bposd"), bposd_trials=trials, lns_starts=lns,
                        num_workers=workers)
        out["per_basis"][b] = {"summary": r.summary(), "weight": r.to_dict().get("weight")}
        print(b, r.summary(), flush=True)
    out["seconds"] = round(time.time() - t0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--hom", required=True)
    ap.add_argument("--x", type=int, nargs=2, required=True)
    ap.add_argument("--z", type=int, nargs=2, required=True)
    ap.add_argument("--task", default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--trials", type=int, default=1500)
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    code, sched, xb, zb = build(a.code, a.hom, a.x, a.z)
    inter = interleaving(sched)
    lcf = layer_conflict_free(sched)
    print("blocks X:", xb, "Z:", zb, "layer conflict free:", lcf, "interleaving:", inter, flush=True)
    ev = evaluate(a.code, sched, a.task, a.seed, a.trials, workers=a.workers)
    print(ev.get("report", "")[:3000] or json.dumps(ev["per_basis"]), flush=True)
    term = {k: {c: list(order_terms(k, *b)) for c, b in bl.items()} for k, bl in (("X", xb), ("Z", zb))}
    (OUT / f"assembled_{a.code}_h{a.hom}_x{a.x[0]}_{a.x[1]}_z{a.z[0]}_{a.z[1]}.json").write_text(json.dumps(
        {"code": a.code, "hom": a.hom, "x_blocks": xb, "z_blocks": zb, "term_orders": term,
         "layer_conflict_free": lcf, "interleaving": inter, "eval": ev}, indent=1, default=str))


if __name__ == "__main__":
    main()
