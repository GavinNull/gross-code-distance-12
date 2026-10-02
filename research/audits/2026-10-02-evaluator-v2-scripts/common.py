"""v2 审计共用工具（只读调用 evaluators/，不修改）。"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import numpy as np  # noqa: E402

from evaluators import candidate as cand  # noqa: E402
from evaluators import tasks as T  # noqa: E402
from evaluators.l2 import circuit_hash  # noqa: E402


def surface(d=3):
    from schedule_helpers import surface_schedule
    return surface_schedule(d)


def random_free_schedule(code, D, rng: random.Random, max_tries=2000):
    """逐检查自由的随机调度：每个校验自己的 prep、窗口长度、CNOT 时间（模 D），满足模板约束（数据比特每步至多一个 CNOT）。
    不保证确定性（由调用方用 stim 判定）。"""
    for _ in range(max_tries):
        used = set()      # (t, col)
        x, z = [], []
        ok = True
        for typ, H, out in (("X", code.HX, x), ("Z", code.HZ, z)):
            for i in range(H.shape[0]):
                supp = [int(c) for c in np.flatnonzero(H[i])]
                w = len(supp)
                if w + 2 > D:
                    return None
                placed = False
                for _ in range(200):
                    prep = rng.randrange(D)
                    dm = rng.randint(w + 1, D - 1)
                    offs = rng.sample(range(1, dm), w)
                    cols = supp[:]
                    rng.shuffle(cols)
                    ts = [(prep + o) % D for o in offs]
                    if any((t, c) in used for t, c in zip(ts, cols)):
                        continue
                    for t, c in zip(ts, cols):
                        used.add((t, c))
                    out.append(cand.CheckTiming(prep, (prep + dm) % D, tuple(sorted(zip(cols, ts)))))
                    placed = True
                    break
                if not placed:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            return cand.ScheduleSpec(D, tuple(x), tuple(z))
    return None


def deterministic(spec, code, rounds=2):
    try:
        for b in "ZX":
            cand.memory_circuit(spec, code, b, rounds).detector_error_model(allow_gauge_detectors=False)
        return True
    except ValueError:
        return False


def dump(obj, path):
    Path(path).write_text(json.dumps(obj, indent=1, default=str))
