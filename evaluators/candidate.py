"""候选调度的 JSON 规范，以及评估器用固定模板从调度生成 memory 电路（评估器 v2，2026-10-02）。

候选**只提交调度，不提交电路**。评估器自己生成两个基底、任意轮数的无噪声 memory 电路，噪声由
evaluators/noise.py 按任务加；候选碰不到 detector、observable、轮数、噪声或任何 stim 指令。
伪轮次、轮数造假、多余测量、读出后再测等攻击因此在结构上不可能（L0 仍作为第二道防线运行）。

## 规范（format = "qec-schedule/v1"）

    {
      "format": "qec-schedule/v1",
      "period": 8,                                  # 一个周期的时间步数 D（2..MAX_PERIOD）
      "x_checks": [                                 # 每个 HX 行一项，按行序（含冗余行，一行都不能少）
        {"prep": 0, "meas": 7, "cnots": [[col, t], ...]},   # col = 数据列（码第 col 列），t = 时间步
        ...
      ],
      "z_checks": [ ... 每个 HZ 行一项 ... ],
      "name": "可选，任意字符串，不参与哈希"
    }

- 所有时间步都是**周期内**的整数 0..D-1，按周期循环解释（Strikis 风格的跨周期流水）：从 prep 开始循环读，
  偏移 off(t) = (t - prep) mod D。要求 0 < off(cnot) < off(meas) < D，同一校验的 CNOT 偏移互不相同。
  所以一个校验的窗口（复位 → 与全部数据比特各一次 CNOT → 测量）短于一个周期，第 j 轮的实例在第 j+1 轮实例
  复位之前测量；窗口可以跨越周期边界（IBM 的 Z 校验、Strikis 的电路）。
- cnots 的列集合必须**恰好**等于该行的支撑，每列一次。CNOT 方向与基底由模板固定：
  X 校验 = RX 复位、CX(辅助 → 数据)、MX 测量；Z 校验 = R 复位、CX(数据 → 辅助)、M 测量。
- 同一时间步（模 D）每个数据比特至多参与一个 CNOT；每个辅助比特每步至多一个操作（由偏移互异保证）。
- 不允许任何其他字段（噪声、门、轮数、detector、observable、比特编号……一律拒绝）。

## 模板（`memory_circuit`）

比特布局（由评估器决定）：数据 0..n-1（码第 j 列 = 比特 j），X 辅助比特 n..n+mx-1（HX 行序），
Z 辅助比特 n+mx..n+mx+mz-1（HZ 行序）。展开规则与 baselines.circuit.unroll_schedule 相同（为了与 E-002/E-003
的电路逐机制一致，代码搬进评估器，不 import baselines）：

  - 每个校验 q 的第 j 轮实例：复位在 start_q + D·j，CNOT 在 复位 + off，测量在 复位 + off(meas)，j = 0..rounds-1；
  - 第 0 层复位全部数据比特（basis 基）；数据 CNOT 不得早于第 1 层；
  - 全局平移 σ ∈ 0..D-1，每个校验取满足上面条件的最早起点；取总层数最少的 σ（并列取最小 σ）；
  - 全部辅助比特测量完之后，单独一层做数据比特的最终 basis 基读出（之后没有任何操作）；
  - detector：basis 型校验第 0 轮与确定初值比较、第 j 轮与第 j-1 轮比较、末轮与数据读出比较；
    observable = 码的 k 个 basis 型逻辑算符（评估器从 HX/HZ 计算，候选不能指定）。

每个校验每轮恰好一次“复位 → 全部 CNOT → 测量”，所有行（含冗余行）每轮都测——由构造保证，
不依赖 L0 的推断。CNOT 的先后是否对易（电路是否确定）由 L0 的 determinism 检查判定。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Mapping

import numpy as np
import stim

from evaluators.codes import CSSCode

__all__ = [
    "SCHEDULE_FORMAT",
    "MAX_PERIOD",
    "ScheduleError",
    "CheckTiming",
    "ScheduleSpec",
    "Layout",
    "parse_schedule",
    "validate_schedule",
    "layout_for",
    "unroll",
    "memory_circuit",
    "build_circuits",
    "template_edges",
    "schedule_from_cyclic_layers",
    "Unrolled",
]

SCHEDULE_FORMAT = "qec-schedule/v1"
MAX_PERIOD = 64
_TOP_KEYS = {"format", "period", "x_checks", "z_checks"}
_OPTIONAL_TOP_KEYS = {"name"}
_CHECK_KEYS = {"prep", "meas", "cnots"}


class ScheduleError(ValueError):
    """调度不符合规范或模板约束。`problems` 是逐条可读诊断（可直接喂给 LLM）。"""

    def __init__(self, problems: list[str]):
        self.problems = list(problems)
        shown = self.problems[:20]
        more = f"\n  ... (+{len(self.problems) - 20} more)" if len(self.problems) > 20 else ""
        super().__init__("invalid schedule:\n  - " + "\n  - ".join(shown) + more)


@dataclass(frozen=True)
class CheckTiming:
    prep: int
    meas: int
    cnots: tuple[tuple[int, int], ...]   # (数据列, 时间步)，按列排序

    def offsets(self, period: int) -> tuple[int, tuple[tuple[int, int], ...]]:
        """(测量偏移, ((CNOT 偏移, 数据列), ...) 按偏移排序)。"""
        dm = (self.meas - self.prep) % period
        return dm, tuple(sorted(((t - self.prep) % period, c) for c, t in self.cnots))


@dataclass(frozen=True)
class ScheduleSpec:
    period: int
    x_checks: tuple[CheckTiming, ...]
    z_checks: tuple[CheckTiming, ...]
    name: str = ""

    def to_dict(self) -> dict:
        def ck(c: CheckTiming) -> dict:
            return {"prep": c.prep, "meas": c.meas, "cnots": [[a, t] for a, t in c.cnots]}
        d = {"format": SCHEDULE_FORMAT, "period": self.period,
             "x_checks": [ck(c) for c in self.x_checks], "z_checks": [ck(c) for c in self.z_checks]}
        if self.name:
            d["name"] = self.name
        return d

    def canonical(self) -> "ScheduleSpec":
        """规范形式：全局时间平移不改变生成的电路（展开时会取最优平移），取字典序最小的平移代表。"""
        D = self.period
        best = None
        for s in range(D):
            sh = ScheduleSpec(D, tuple(_shift(c, s, D) for c in self.x_checks),
                              tuple(_shift(c, s, D) for c in self.z_checks))
            key = json.dumps(sh.to_dict(), sort_keys=True, separators=(",", ":"))
            if best is None or key < best[0]:
                best = (key, sh)
        return best[1]

    def canonical_json(self) -> str:
        return json.dumps(self.canonical().to_dict(), sort_keys=True, separators=(",", ":"))

    def hash(self) -> str:
        """评估器对规范化调度计算的 sha256（不含 name）。"""
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


def _shift(c: CheckTiming, s: int, D: int) -> CheckTiming:
    return CheckTiming((c.prep + s) % D, (c.meas + s) % D, tuple((a, (t + s) % D) for a, t in c.cnots))


def _is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


# ---------------------------------------------------------------------------
# 解析（严格）
# ---------------------------------------------------------------------------

def parse_schedule(obj) -> ScheduleSpec:
    """把候选给的 JSON（字符串或 dict）解析成 ScheduleSpec。只做语法检查；与码相关的检查见 validate_schedule。"""
    if isinstance(obj, ScheduleSpec):
        return obj
    if isinstance(obj, (str, bytes)):
        try:
            obj = json.loads(obj)
        except json.JSONDecodeError as e:
            raise ScheduleError([f"not valid JSON: {e}"]) from e
    if not isinstance(obj, Mapping):
        raise ScheduleError([f"schedule must be a JSON object, got {type(obj).__name__}"])
    problems: list[str] = []
    keys = set(obj)
    extra = keys - _TOP_KEYS - _OPTIONAL_TOP_KEYS
    if extra:
        problems.append(f"unknown top-level field(s) {sorted(extra)}: a schedule may only contain "
                        f"{sorted(_TOP_KEYS | _OPTIONAL_TOP_KEYS)} (noise, gates, rounds, detectors and circuits are "
                        f"fixed by the evaluator)")
    missing = _TOP_KEYS - keys
    if missing:
        problems.append(f"missing field(s) {sorted(missing)}")
    if problems:
        raise ScheduleError(problems)
    if obj["format"] != SCHEDULE_FORMAT:
        problems.append(f"format must be {SCHEDULE_FORMAT!r}, got {obj['format']!r}")
    D = obj["period"]
    if not _is_int(D) or not 2 <= D <= MAX_PERIOD:
        problems.append(f"period must be an integer in 2..{MAX_PERIOD}, got {D!r}")
        raise ScheduleError(problems)
    name = obj.get("name", "")
    if not isinstance(name, str) or len(name) > 200:
        problems.append("name must be a string of at most 200 characters")
    out = {}
    for typ in ("x_checks", "z_checks"):
        lst = obj[typ]
        if not isinstance(lst, list):
            problems.append(f"{typ} must be a list")
            continue
        checks = []
        for i, c in enumerate(lst):
            where = f"{typ[0].upper()}-check #{i}"
            if not isinstance(c, Mapping):
                problems.append(f"{where}: must be an object with fields {sorted(_CHECK_KEYS)}")
                continue
            if set(c) != _CHECK_KEYS:
                problems.append(f"{where}: fields must be exactly {sorted(_CHECK_KEYS)}, got {sorted(c)}")
                continue
            ok = True
            for f in ("prep", "meas"):
                if not _is_int(c[f]) or not 0 <= c[f] < D:
                    problems.append(f"{where}: {f} must be an integer time step in 0..{D - 1}, got {c[f]!r}")
                    ok = False
            cn = c["cnots"]
            if not isinstance(cn, list):
                problems.append(f"{where}: cnots must be a list of [data_column, time_step] pairs")
                continue
            pairs = []
            for e in cn:
                if (not isinstance(e, (list, tuple)) or len(e) != 2 or not all(_is_int(x) for x in e)
                        or e[0] < 0 or not 0 <= e[1] < D):
                    problems.append(f"{where}: bad CNOT entry {e!r} (need [data_column >= 0, time_step in 0..{D - 1}])")
                    ok = False
                    continue
                pairs.append((int(e[0]), int(e[1])))
            if ok:
                checks.append(CheckTiming(int(c["prep"]), int(c["meas"]), tuple(sorted(pairs))))
        out[typ] = tuple(checks)
    if problems:
        raise ScheduleError(problems)
    return ScheduleSpec(D, out["x_checks"], out["z_checks"], name)


# ---------------------------------------------------------------------------
# 模板约束
# ---------------------------------------------------------------------------

def validate_schedule(spec: ScheduleSpec, code: CSSCode) -> list[str]:
    """返回违反模板约束的逐条诊断（空 = 合法）。"""
    problems: list[str] = []
    D = spec.period
    for typ, H, checks in (("X", code.HX, spec.x_checks), ("Z", code.HZ, spec.z_checks)):
        if len(checks) != H.shape[0]:
            problems.append(f"{typ}-checks: the schedule lists {len(checks)} checks but H{typ} has {H.shape[0]} rows; "
                            f"every row (including redundant rows) must be measured every round")
            continue
        for i, c in enumerate(checks):
            where = f"{typ}-check #{i}"
            supp = set(np.flatnonzero(H[i]).tolist())
            if not supp:
                problems.append(f"{where}: H{typ} row {i} is empty")
                continue
            cols = [a for a, _ in c.cnots]
            dup = sorted({a for a in cols if cols.count(a) > 1})
            if dup:
                problems.append(f"{where}: data column(s) {dup} have more than one CNOT (exactly one per column)")
            miss, extra = sorted(supp - set(cols)), sorted(set(cols) - supp)
            if miss:
                problems.append(f"{where}: missing CNOT(s) to data column(s) {miss} (row support is {sorted(supp)})")
            if extra:
                problems.append(f"{where}: CNOT(s) to data column(s) {extra} outside the row support {sorted(supp)}")
            dm, offs = c.offsets(D)
            if dm == 0:
                problems.append(f"{where}: prep and meas are in the same time step {c.prep}")
                continue
            for o, a in offs:
                if not 0 < o < dm:
                    t = (c.prep + o) % D
                    problems.append(f"{where}: CNOT to data column {a} at time {t} is outside the window: reading the "
                                    f"period cyclically from prep (t={c.prep}), CNOTs must come strictly after prep "
                                    f"and strictly before meas (t={c.meas})")
            ts = [o for o, _ in offs]
            clash = sorted({(c.prep + o) % D for o in ts if ts.count(o) > 1})
            if clash:
                problems.append(f"{where}: its ancilla has two CNOTs in the same time step(s) {clash}")
    if problems:
        return problems
    # 数据比特：同一时间步（模 D）至多一个 CNOT
    use: dict[tuple[int, int], list[str]] = {}
    for typ, checks in (("X", spec.x_checks), ("Z", spec.z_checks)):
        for i, c in enumerate(checks):
            for a, t in c.cnots:
                use.setdefault((t, a), []).append(f"{typ}-check #{i}")
    for (t, a), who in sorted(use.items()):
        if len(who) > 1:
            problems.append(f"data column {a} has {len(who)} CNOTs in time step {t} ({', '.join(who)}); at most one "
                            f"operation per qubit per time step")
    return problems


# ---------------------------------------------------------------------------
# 展开与电路
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Layout:
    n: int
    data: tuple[int, ...]
    x_anc: tuple[int, ...]
    z_anc: tuple[int, ...]

    @property
    def num_qubits(self) -> int:
        return self.n + len(self.x_anc) + len(self.z_anc)


def layout_for(code: CSSCode) -> Layout:
    n, mx, mz = code.n, code.HX.shape[0], code.HZ.shape[0]
    return Layout(n, tuple(range(n)), tuple(range(n, n + mx)), tuple(range(n + mx, n + mx + mz)))


def template_edges(code: CSSCode) -> set[tuple[int, int]]:
    """模板电路允许的双比特门（Tanner 图的边，有向：X 辅助 → 数据，数据 → Z 辅助）。"""
    lay = layout_for(code)
    e = set()
    for i, a in enumerate(lay.x_anc):
        for c in np.flatnonzero(code.HX[i]):
            e.add((a, int(c)))
    for i, a in enumerate(lay.z_anc):
        for c in np.flatnonzero(code.HZ[i]):
            e.add((int(c), a))
    return e


@dataclass(frozen=True)
class Unrolled:
    num_layers: int                               # 不含最终读出层
    sigma: int
    start: dict                                   # 辅助比特 -> 第 0 轮复位层
    preps: dict                                   # 层 -> [(辅助比特, 类型)]
    cnots: dict                                   # 层 -> [(control, target)]
    meas: dict                                    # 层 -> [(辅助比特, 类型, 轮)]


def unroll(spec: ScheduleSpec, code: CSSCode, rounds: int) -> Unrolled:
    """按模板展开（规则见模块说明；与 baselines.circuit.unroll_schedule 相同）。"""
    if not _is_int(rounds) or rounds < 1:
        raise ValueError(f"rounds must be a positive integer, got {rounds!r}")
    problems = validate_schedule(spec, code)
    if problems:
        raise ScheduleError(problems)
    D = spec.period
    lay = layout_for(code)
    info = {}
    for typ, checks, anc in (("X", spec.x_checks, lay.x_anc), ("Z", spec.z_checks, lay.z_anc)):
        for c, q in zip(checks, anc):
            dm, offs = c.offsets(D)
            info[q] = (typ, c.prep, dm, offs)
    best = None
    for sigma in range(D):
        start = {}
        for q, (_, tp, dm, offs) in info.items():
            s = sigma + tp - D
            if s < 0:
                s += D
            if s + offs[0][0] < 1:      # 第一个 CNOT 必须在第 0 层（数据复位）之后
                s += D
            start[q] = s
        end = max(start[q] + D * (rounds - 1) + info[q][2] for q in info)
        if best is None or end < best[0]:
            best = (end, sigma, start)
    end, sigma, start = best
    preps: dict[int, list] = {}
    cnots: dict[int, list] = {}
    meas: dict[int, list] = {}
    for q, (typ, _, dm, offs) in info.items():
        for j in range(rounds):
            s = start[q] + D * j
            preps.setdefault(s, []).append((q, typ))
            for o, col in offs:
                cnots.setdefault(s + o, []).append((q, col) if typ == "X" else (col, q))
            meas.setdefault(s + dm, []).append((q, typ, j))
    # 防御性检查：展开后每层每个比特至多一个操作
    for t in range(end + 1):
        qs = [a for pr in cnots.get(t, []) for a in pr] + [q for q, _ in preps.get(t, [])] + \
             [q for q, _, _ in meas.get(t, [])] + (list(lay.data) if t == 0 else [])
        if len(qs) != len(set(qs)):
            raise ScheduleError([f"unrolled layer {t}: a qubit is used twice (internal template error)"])
    return Unrolled(end + 1, sigma, dict(start), preps, cnots, meas)


def memory_circuit(spec: ScheduleSpec, code: CSSCode, basis: str, rounds: int) -> stim.Circuit:
    """无噪声 memory 电路（basis = "Z" 或 "X"）。噪声由评估器之后按任务加。"""
    if basis not in ("X", "Z"):
        raise ValueError("basis must be 'X' or 'Z'")
    U = unroll(spec, code, rounds)
    lay = layout_for(code)
    c = stim.Circuit()
    nmeas = 0
    rec: dict[tuple[int, int], int] = {}
    for t in range(U.num_layers):
        if t == 0:
            c.append("R" if basis == "Z" else "RX", list(lay.data))
        px = sorted(q for q, typ in U.preps.get(t, []) if typ == "X")
        pz = sorted(q for q, typ in U.preps.get(t, []) if typ == "Z")
        if px:
            c.append("RX", px)
        if pz:
            c.append("R", pz)
        cn = sorted(U.cnots.get(t, []))
        if cn:
            c.append("CX", [a for pr in cn for a in pr])
        for typ, gate in (("Z", "M"), ("X", "MX")):
            ms = sorted((q, j) for q, ty, j in U.meas.get(t, []) if ty == typ)
            if ms:
                c.append(gate, [q for q, _ in ms])
                for q, j in ms:
                    rec[(q, j)] = nmeas
                    nmeas += 1
        c.append("TICK")
    # detector（与 baselines 相同的顺序与坐标）：轮 → X 校验 → Z 校验
    checks = {"X": lay.x_anc, "Z": lay.z_anc}
    for j in range(rounds):
        for typ in ("X", "Z"):
            if typ != basis:
                continue
            for i, q in enumerate(checks[typ]):
                cur = rec[(q, j)] - nmeas
                tg = [stim.target_rec(cur)] if j == 0 else [stim.target_rec(cur), stim.target_rec(rec[(q, j - 1)] - nmeas)]
                c.append("DETECTOR", tg, [i, j, 0 if typ == "X" else 1])
    # 最终读出（单独一层，之后没有任何操作）
    c.append("M" if basis == "Z" else "MX", list(lay.data))
    data_rec = {j: nmeas + j for j in range(lay.n)}
    nmeas += lay.n
    H = code.HZ if basis == "Z" else code.HX
    for i, q in enumerate(checks[basis]):
        tg = [stim.target_rec(data_rec[col] - nmeas) for col in np.flatnonzero(H[i])]
        tg.append(stim.target_rec(rec[(q, rounds - 1)] - nmeas))
        c.append("DETECTOR", tg, [i, rounds, 0 if basis == "X" else 1])
    L = code.LZ if basis == "Z" else code.LX
    for k, row in enumerate(L):
        c.append("OBSERVABLE_INCLUDE", [stim.target_rec(data_rec[col] - nmeas) for col in np.flatnonzero(row)], k)
    return c


def build_circuits(spec: ScheduleSpec, code: CSSCode, rounds: int) -> dict[str, stim.Circuit]:
    return {b: memory_circuit(spec, code, b, rounds) for b in ("Z", "X")}


def schedule_from_cyclic_layers(period: int, x_checks, z_checks) -> ScheduleSpec:
    """便捷构造：x_checks / z_checks 为 [(prep, meas, {data_col: t})]。"""
    def mk(lst):
        return tuple(CheckTiming(int(p), int(m), tuple(sorted((int(a), int(t)) for a, t in cn.items())))
                     for p, m, cn in lst)
    return ScheduleSpec(int(period), mk(x_checks), mk(z_checks))
