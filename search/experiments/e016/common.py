"""E-016：[[108,8,10]] 两色电路（d_circ = 10）对 IBM 原电路（d_circ <= 8）的逻辑错误率。共享工具。experimenter。

电路（两者完全相同的设置，只差调度）：
  * twocolour：search/noninterleaved/assemble.py 的同一构造（--x 2 14 --z 12 0），build_schedule -> from_baseline。
  * ibm：baselines.schedule.ibm_depth8 -> from_baseline（与 E-006 相同的转换路径）。
  评估器模板电路 candidate.build_circuits，sd6，boundary="paper"，联合 X/Z 电路 l2.build_joint_circuit，轮数 10。
Model 结构与 search/decoders/common.build_model 相同（那里只支持 BB 字典里的码，所以把它的构造逻辑抄到这里，
接受任意 (code, spec)）；只读复用 search/decoders/common 的 Sector/Model/采样函数。
"""
from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parents[3]
for p in (str(ROOT), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from evaluators import candidate as cand  # noqa: E402
from evaluators.l2 import build_joint_circuit, _xor_set  # noqa: E402
from evaluators.tasks import build_code, get_task  # noqa: E402
from search.decoders.common import Model, Sector  # noqa: E402

OUT = ROOT / "results" / "E-016-bb108-ler"
OUT.mkdir(parents=True, exist_ok=True)
TASK = "bb108-dcirc"
ROUNDS = 10
K = 8
CIRCS = ("ibm", "twocolour")
X_BLOCKS, Z_BLOCKS = (2, 14), (12, 0)


@lru_cache(maxsize=None)
def code_and_spec(name: str):
    code, _ = build_code(get_task(TASK), None)
    from schedule_helpers import from_baseline
    if name == "ibm":
        from baselines.bb_code import BBCode
        from baselines.schedule import ibm_depth8
        bb = BBCode(9, 6, ["x^3", "y", "y^2"], ["y^3", "x", "x^2"])
        assert (bb.HX == code.HX).all() and (bb.HZ == code.HZ).all()
        spec = from_baseline(ibm_depth8(bb))
    elif name == "twocolour":
        # 与 assemble.py main() 完全相同的构造
        from search.noninterleaved.colour_search import order_terms
        from search.noninterleaved.schedules import build_schedule
        from search.noninterleaved.two_colour import M, ctx
        cx, cz = ctx("X"), ctx("Z")
        c = cx["code"]
        xb = [cx["ok"][X_BLOCKS[0]], cx["ok"][X_BLOCKS[1]]]
        zb = [cz["ok"][Z_BLOCKS[0]], cz["ok"][Z_BLOCKS[1]]]
        x_spec = [(0, order_terms("X", *xb[(i % M) % 2])) for i in range(c.n2)]
        z_spec = [(4, order_terms("Z", *zb[(i % M) % 2])) for i in range(c.n2)]
        spec = from_baseline(build_schedule(c, x_spec, z_spec, name="bb108_twocolour"))
    else:
        raise ValueError(name)
    probs = cand.validate_schedule(spec, code)
    assert not probs, probs
    return code, spec


def build_model(name: str, p: float, rounds: int = ROUNDS, boundary: str = "paper") -> Model:
    """search.decoders.common.build_model 的逐行拷贝，只把 code_and_schedule 换成本文件的 code_and_spec。"""
    code, spec = code_and_spec(name)
    circs = cand.build_circuits(spec.canonical(), code, rounds)
    lay = cand.layout_for(code)
    jc = build_joint_circuit(code, circs, list(lay.data), noise_model="sd6", p=p, boundary=boundary)
    dem = jc.circuit.detector_error_model(allow_gauge_detectors=False)
    nz, oz = jc.num_detectors_z, jc.num_observables_z
    nd, no = jc.circuit.num_detectors, jc.circuit.num_observables
    pri, keys, jdets = [], {"Z": [], "X": []}, []
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        pr = inst.args_copy()[0]
        parts = {"Z": ([], []), "X": ([], [])}
        dl = []
        for t in inst.targets_copy():
            if t.is_separator():
                continue
            if t.is_relative_detector_id():
                v = t.val
                dl.append(v)
                (parts["Z"] if v < nz else parts["X"])[0].append(v if v < nz else v - nz)
            elif t.is_logical_observable_id():
                v = t.val
                (parts["Z"] if v < oz else parts["X"])[1].append(v if v < oz else v - oz)
        for s in "ZX":
            d, o = parts[s]
            keys[s].append((tuple(sorted(_xor_set(d))), tuple(sorted(_xor_set(o)))))
        pri.append(pr)
        jdets.append(tuple(sorted(dl)))
    pri = np.array(pri)
    sectors = {}
    for s in "ZX":
        ndet = nz if s == "Z" else nd - nz
        nobs = oz if s == "Z" else no - oz
        merged: dict = {}
        order: list = []
        for j, key in enumerate(keys[s]):
            if not key[0] and not key[1]:
                continue
            if key not in merged:
                merged[key] = 0.0
                order.append(key)
            q = merged[key]
            merged[key] = q * (1 - pri[j]) + pri[j] * (1 - q)
        cols = [k for k in order if k[0]]
        cidx = {k: i for i, k in enumerate(cols)}
        j2c = np.full(len(pri), -1, dtype=np.int64)
        j2free = np.zeros(len(pri), dtype=np.int64)
        for j, key in enumerate(keys[s]):
            if key in cidx:
                j2c[j] = cidx[key]
            elif key[1] and not key[0]:
                j2free[j] = sum(1 << o for o in key[1])
        rows, ci, orows, oci = [], [], [], []
        for i, (d, o) in enumerate(cols):
            rows += d; ci += [i] * len(d)
            orows += o; oci += [i] * len(o)
        H = sp.csc_matrix((np.ones(len(rows), np.uint8), (rows, ci)), shape=(ndet, len(cols)))
        L = sp.csr_matrix((np.ones(len(orows), np.uint8), (orows, oci)), shape=(nobs, len(cols)))
        pr_s = np.array([merged[k] for k in cols])
        sectors[s] = Sector(s, H, L, pr_s, np.log((1 - pr_s) / pr_s), j2c, j2free, ndet, nobs)
    return Model(name, p, rounds, jc.circuit, dem, pri, sectors, nz, oz, jdets)


def joint_matrices(m: Model):
    """完整联合 DEM（与 search/experiments/e009/joint.joint_matrices 相同）：只保留至少触发一个探测器的机制。
    返回 H (csr), L (csr), priors, jmap（联合机制下标 -> 列，-1 = 无探测器），free（无探测器机制的 observable 翻转位掩码）。"""
    rows, cols, orows, ocols, pri = [], [], [], [], []
    jmap, free = [], []
    j = 0
    for inst in m.dem.flattened():
        if inst.type != "error":
            continue
        d, o = set(), set()
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                d ^= {t.val}
            elif t.is_logical_observable_id():
                o ^= {t.val}
        if not d:
            jmap.append(-1)
            free.append(sum(1 << v for v in o))
            continue
        rows += sorted(d); cols += [j] * len(d)
        orows += sorted(o); ocols += [j] * len(o)
        pri.append(inst.args_copy()[0])
        jmap.append(j)
        free.append(0)
        j += 1
    H = sp.csc_matrix((np.ones(len(rows), np.uint8), (rows, cols)), shape=(m.circuit.num_detectors, j))
    L = sp.csr_matrix((np.ones(len(orows), np.uint8), (orows, ocols)), shape=(m.circuit.num_observables, j))
    return H.tocsr(), L, np.array(pri), np.array(jmap), np.array(free, dtype=np.int64)


def per_round_per_logical(P_any: float, rounds: int = ROUNDS, k: int = K) -> float:
    """每轮每逻辑比特 LER：B = (1 - (1 - P_any)^(1/R)) / k（E-004 的 B_paper 口径）。"""
    return (1 - (1 - P_any) ** (1 / rounds)) / k
