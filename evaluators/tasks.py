"""评估任务注册表（评估器 v2，2026-10-02）。

一个任务冻结了打分口径的全部参数：码族、噪声模型（只允许 sd6）与 p、解码器参数、边界口径、轮数、停止规则
（每个 sector >= 1000 次失败才能上榜）、L0 约束（距离下限与搜索预算）、分层漏斗与各层预算。候选只提交
(task_id, code_spec, schedule)；其余一切由任务决定。榜单条目带 task_id 与 task_hash，不同任务不混榜。

注册表就是本文件里的 `TASKS`（随评估器一起冻结）。运行时不提供“注册新任务”的接口；新增或修改任务 = 修改
evaluators/，需要 PI 重新冻结。

## 码族（code_family）

    {"kind": "bb", "fixed": {"l": 12, "m": 6, "A": ["x^3", "y", "y^2"], "B": ["y^3", "x", "x^2"]}}
    {"kind": "bb", "constraints": {"max_n": 300, "max_row_weight": 6, "min_k": 1}}      # 自由搜码（H-003）
    {"kind": "rotated_surface", "fixed": {"d": 3}}

候选的 code_spec 与族同形：{"family": "bb", "l":.., "m":.., "A": [...], "B": [...]}；fixed 族可以传 None。
BB 码：x = S_l ⊗ I_m，y = I_l ⊗ S_m（S 为循环移位），HX = [A | B]，HZ = [Bᵀ | Aᵀ]（arXiv:2308.07915 式 (1)(2)，
与 baselines/bb_code.py 相同）；单项式写作 "1"、"x"、"x^3"、"y^2"、"x^2*y" 等。逻辑算符由评估器计算。
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Mapping

import numpy as np

from evaluators.codes import CSSCode, rotated_surface_code_from_stim
from evaluators.noise import SCORING_MODELS

__all__ = ["Task", "TASKS", "get_task", "build_code", "CodeSpecError", "MIN_SECTOR_ERRORS_FOR_LEADERBOARD",
           "PINNED_VERSIONS"]

# 小样本结果不能上榜（evaluators/stats.py MIN_LOGICAL_ERRORS_FOR_COMPARISON；auditor G1 L2-4）
MIN_SECTOR_ERRORS_FOR_LEADERBOARD = 1000

# 评估器依赖的关键库（与 pyproject.toml 的 == 约束一致；auditor G1 F6）。pipeline 在写榜前核对。
PINNED_VERSIONS = {
    "stim": "1.16.0",
    "sinter": "1.16.0",
    "ldpc": "2.4.1",
    "pymatching": "2.4.0",
    "numpy": "2.2.6",
    "scipy": "1.18.1",
    "ortools": "9.15.6755",
    "python-sat": "1.9.dev15",
}


class CodeSpecError(ValueError):
    pass


@dataclass(frozen=True)
class Task:
    task_id: str
    description: str
    code_family: Mapping
    noise_model: str
    p: float
    decoder: Mapping                    # {"name": "bposd"|"pymatching", "params": {...}}
    boundary: str                       # "paper" | "diff"（diff 时 inner_boundary 见 boundary_options）
    rounds: int                         # 打分电路的轮数（diff 时为较长的 r2）
    stop: Mapping                       # StopRule 参数；min_sector_errors 必须 >= 1000
    l0: Mapping                         # L0Constraints 的距离相关参数（min_circuit_distance、预算、超时、进程数）
    boundary_options: Mapping = field(default_factory=dict)   # diff: {"diff_rounds": r1, "inner": "paper"}
    funnel: Mapping = field(default_factory=dict)             # 分层漏斗（见 README §9.3；E-004 之后填）
    num_workers: int = 3                                      # sinter / 距离搜索进程数（项目规定 ≤ 3）
    purpose: str = "score"                                    # "score" | "selftest"
    allow_redundant_row_omission: bool = False                # PI 未决定前一律不允许（L0-2）
    # 评估器 v2.1：任务类型。"l2" = 逻辑错误率打分（原有）；"distance" = 只评电路级距离（H-004，不跑 L2）
    kind: str = "l2"
    # 调度的额外约束（任务级），目前只有 {"max_period": D}（摊销深度上限）
    schedule_constraints: Mapping = field(default_factory=dict)

    def to_dict(self) -> dict:
        return json.loads(json.dumps(asdict(self), sort_keys=True, default=_jsonable))

    def hash(self) -> str:
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def validate(self) -> None:
        if self.noise_model not in SCORING_MODELS:
            raise ValueError(f"task {self.task_id}: noise model {self.noise_model!r} is not a scoring model "
                             f"{SCORING_MODELS}")
        if self.num_workers > 3:
            raise ValueError("num_workers must be <= 3 (project CPU policy)")
        if self.allow_redundant_row_omission:
            raise ValueError("omitting redundant check rows is not allowed until the PI decides (L0-2)")
        if self.purpose not in ("score", "selftest"):
            raise ValueError(f"task {self.task_id}: purpose must be 'score' or 'selftest'")
        extra = set(self.schedule_constraints) - {"max_period"}
        if extra:
            raise ValueError(f"task {self.task_id}: unknown schedule constraints {sorted(extra)}")
        if self.kind == "distance":
            self._validate_distance()
            return
        if self.kind != "l2":
            raise ValueError(f"task {self.task_id}: kind must be 'l2' or 'distance'")
        if self.boundary not in ("paper", "diff"):
            raise ValueError(f"task {self.task_id}: boundary must be 'paper' or 'diff'")
        if self.boundary == "diff":
            r1 = self.boundary_options.get("diff_rounds")
            if not isinstance(r1, int) or not 0 < r1 < self.rounds:
                raise ValueError(f"task {self.task_id}: diff needs 0 < diff_rounds < rounds")
        if int(self.stop.get("min_sector_errors") or 0) < MIN_SECTOR_ERRORS_FOR_LEADERBOARD:
            raise ValueError(f"task {self.task_id}: stop.min_sector_errors must be >= "
                             f"{MIN_SECTOR_ERRORS_FOR_LEADERBOARD}")

    def _validate_distance(self) -> None:
        L = dict(self.l0)
        if self.boundary != "none" or self.decoder or self.stop or self.funnel or self.boundary_options:
            raise ValueError(f"task {self.task_id}: distance tasks have no L2 (boundary 'none', empty decoder / stop / "
                             f"funnel / boundary_options)")
        if L.get("distance_rounds") != self.rounds or not isinstance(self.rounds, int) or self.rounds < 1:
            raise ValueError(f"task {self.task_id}: distance tasks need rounds == l0.distance_rounds >= 1")
        if L.get("distance_seed") != "derived":
            raise ValueError(f"task {self.task_id}: distance seed must be 'derived' (from task and schedule hashes)")
        need = {"distance_methods", "distance_bposd_trials", "distance_lns_starts", "distance_lns_det_time",
                "distance_timeout_s"}
        if need - set(L):
            raise ValueError(f"task {self.task_id}: distance budget must be fixed in the task (missing {sorted(need - set(L))})")
        if set(L["distance_methods"]) - {"graphlike", "stim_search", "bposd"}:
            raise ValueError(f"task {self.task_id}: unknown distance methods")


def _jsonable(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, Mapping):
        return dict(o)
    if isinstance(o, tuple):
        return list(o)
    raise TypeError(type(o))


# ---------------------------------------------------------------------------
# 码族
# ---------------------------------------------------------------------------

_MONO = re.compile(r"^(?:(1)|(?:x(?:\^(\d+))?)?\*?(?:y(?:\^(\d+))?)?)$")


def _mono_exponents(term: str, l: int, m: int) -> tuple[int, int]:
    t = term.replace(" ", "")
    mt = _MONO.match(t)
    if not t or mt is None:
        raise CodeSpecError(f"bad monomial {term!r} (use '1', 'x', 'x^3', 'y^2', 'x^2*y', ...)")
    if mt.group(1):
        return 0, 0
    a = 0 if "x" not in t else int(mt.group(2) or 1)
    b = 0 if "y" not in t else int(mt.group(3) or 1)
    return a % l, b % m


def bb_matrices(l: int, m: int, A_terms, B_terms) -> tuple[np.ndarray, np.ndarray]:
    Sl = np.roll(np.eye(l, dtype=np.int64), 1, axis=1)
    Sm = np.roll(np.eye(m, dtype=np.int64), 1, axis=1)

    def poly(terms):
        exps = [_mono_exponents(t, l, m) for t in terms]
        if len(set(exps)) != len(exps):
            raise CodeSpecError(f"repeated monomials in {list(terms)} (they would cancel mod 2)")
        M = np.zeros((l * m, l * m), dtype=np.int64)
        for a, b in exps:
            M += np.kron(np.linalg.matrix_power(Sl, a), np.linalg.matrix_power(Sm, b))
        return (M % 2).astype(np.uint8)

    A, B = poly(A_terms), poly(B_terms)
    return np.hstack([A, B]), np.hstack([B.T, A.T])


def _normalize_spec(kind: str, spec: Mapping) -> dict:
    if kind == "bb":
        try:
            l, m = int(spec["l"]), int(spec["m"])
            A, B = [str(t) for t in spec["A"]], [str(t) for t in spec["B"]]
        except (KeyError, TypeError, ValueError) as e:
            raise CodeSpecError(f"bb code_spec needs integer l, m and term lists A, B: {e}") from e
        if not (1 <= l <= 64 and 1 <= m <= 64):
            raise CodeSpecError("l, m must be in 1..64")
        return {"family": "bb", "l": l, "m": m,
                "A": sorted(A, key=lambda t: _mono_exponents(t, l, m)),
                "B": sorted(B, key=lambda t: _mono_exponents(t, l, m))}
    if kind == "rotated_surface":
        d = int(spec["d"])
        if not 2 <= d <= 15:
            raise CodeSpecError("d must be in 2..15")
        return {"family": "rotated_surface", "d": d}
    raise CodeSpecError(f"unknown code family {kind!r}")


def build_code(task: Task, code_spec: Mapping | None) -> tuple[CSSCode, dict]:
    """按任务的码族把候选的 code_spec 变成 CSSCode（逻辑算符由评估器计算）。返回 (code, 规范化 spec)。"""
    fam = task.code_family
    kind = fam["kind"]
    fixed = fam.get("fixed")
    if code_spec is None:
        if fixed is None:
            raise CodeSpecError(f"task {task.task_id} has no fixed code; code_spec is required")
        code_spec = dict(fixed, family=kind)
    if not isinstance(code_spec, Mapping):
        raise CodeSpecError("code_spec must be a JSON object")
    if code_spec.get("family", kind) != kind:
        raise CodeSpecError(f"task {task.task_id} only accepts family {kind!r}, got {code_spec.get('family')!r}")
    extra = set(code_spec) - {"family", "l", "m", "A", "B", "d"}
    if extra:
        raise CodeSpecError(f"unknown code_spec field(s) {sorted(extra)}")
    norm = _normalize_spec(kind, code_spec)
    if fixed is not None and norm != _normalize_spec(kind, fixed):
        raise CodeSpecError(f"task {task.task_id} fixes the code to {_normalize_spec(kind, fixed)}; got {norm}")
    if kind == "bb":
        HX, HZ = bb_matrices(norm["l"], norm["m"], norm["A"], norm["B"])
        name = f"bb_l{norm['l']}_m{norm['m']}_A{'+'.join(norm['A'])}_B{'+'.join(norm['B'])}"
    else:
        HX, HZ = None, None
        code0, _, _ = rotated_surface_code_from_stim(norm["d"], "Z", 2)
        HX, HZ, name = code0.HX, code0.HZ, f"rotated_surface_d{norm['d']}"
    try:
        code = CSSCode.from_checks(HX, HZ, name=name)
    except ValueError as e:
        raise CodeSpecError(f"not a valid CSS code: {e}") from e
    cons = fam.get("constraints") or {}
    probs = []
    if code.k < int(cons.get("min_k", 1)):
        probs.append(f"k = {code.k} < {cons.get('min_k', 1)}")
    if "max_n" in cons and code.n > cons["max_n"]:
        probs.append(f"n = {code.n} > {cons['max_n']}")
    if "max_row_weight" in cons:
        w = int(max(code.HX.sum(1).max(), code.HZ.sum(1).max()))
        if w > cons["max_row_weight"]:
            probs.append(f"max check weight {w} > {cons['max_row_weight']}")
    if (code.HX.sum(1) == 0).any() or (code.HZ.sum(1) == 0).any():
        probs.append("code has an empty check row")
    if probs:
        raise CodeSpecError(f"code violates the task constraints: {'; '.join(probs)}")
    return code, norm


def code_hash(code: CSSCode) -> str:
    return hashlib.sha256(code.HX.tobytes() + b"|" + code.HZ.tobytes()
                          + repr((code.HX.shape, code.HZ.shape)).encode()).hexdigest()


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------

_IBM_BPOSD = {"max_iter": 10000, "bp_method": "min_sum", "ms_scaling_factor": 0.0, "osd_method": "osd_cs",
              "osd_order": 7, "schedule": "parallel"}

_TASK_LIST = [
    Task(
        task_id="gross-sd6-p4e-3",
        description=("gross code [[144,12,12]] (arXiv:2308.07915), schedule search only; SD6 p=4e-3; X/Z joint "
                     "sampling, BP-OSD with the IBM parameters, paper boundary (H-003 metric B); 12 rounds. "
                     "Funnel tiers and budgets are placeholders until E-004 reports."),
        code_family={"kind": "bb", "fixed": {"l": 12, "m": 6, "A": ["x^3", "y", "y^2"], "B": ["y^3", "x", "x^2"]}},
        noise_model="sd6", p=4e-3,
        decoder={"name": "bposd", "params": _IBM_BPOSD},
        boundary="paper", rounds=12,
        stop={"max_shots": 2_000_000, "max_errors": 1000, "min_sector_errors": 1000, "batch_size": 25},
        # IBM depth-8 在 3 轮电路上的距离上界为 10（E-002 / evaluator_issues.md），Strikis 猜想 11。
        # 门槛暂定 10，待 PI 确认。距离在 distance_rounds 轮电路上算（gross 12 轮太慢）。
        l0={"min_circuit_distance": 10, "distance_rounds": 3, "distance_seed": 0, "distance_bposd_trials": 1500,
            "distance_lns_starts": 96, "distance_timeout_s": 3600.0},
        funnel={"status": "PENDING E-004: tiers and budgets to be filled after E-004 (proxy fidelity)",
                "tiers": []},
        num_workers=3,
    ),
    Task(
        task_id="selftest-surface-d3-sd6-paper",
        description="self-test task (not a research result): rotated surface code d=3, SD6 p=5e-3, pymatching, "
                    "paper boundary, 3 rounds.",
        code_family={"kind": "rotated_surface", "fixed": {"d": 3}},
        noise_model="sd6", p=5e-3,
        decoder={"name": "pymatching", "params": {}},
        boundary="paper", rounds=3,
        stop={"max_shots": 400_000, "max_errors": 1000, "min_sector_errors": 1000, "batch_size": 2000},
        l0={"min_circuit_distance": 3, "distance_rounds": 3, "distance_seed": 0, "distance_bposd_trials": 100,
            "distance_lns_starts": 8, "distance_timeout_s": 600.0},
        funnel={"status": "selftest: single full tier", "tiers": []},
        num_workers=3, purpose="selftest",
    ),
    Task(
        task_id="selftest-surface-d3-sd6-diff",
        description="self-test task (not a research result): rotated surface code d=3, SD6 p=5e-3, pymatching, "
                    "diff boundary (rounds 3 and 9, inner paper).",
        code_family={"kind": "rotated_surface", "fixed": {"d": 3}},
        noise_model="sd6", p=5e-3,
        decoder={"name": "pymatching", "params": {}},
        boundary="diff", rounds=9, boundary_options={"diff_rounds": 3, "inner": "paper"},
        stop={"max_shots": 400_000, "max_errors": 1000, "min_sector_errors": 1000, "batch_size": 2000},
        l0={"min_circuit_distance": 3, "distance_rounds": 3, "distance_seed": 0, "distance_bposd_trials": 100,
            "distance_lns_starts": 8, "distance_timeout_s": 600.0},
        funnel={"status": "selftest: single full tier", "tiers": []},
        num_workers=3, purpose="selftest",
    ),
]

# ---------------------------------------------------------------------------
# 评估器 v2.1：只评距离的任务（H-004，research/decisions.md 2026-10-02 主线）
# ---------------------------------------------------------------------------
# 码（多项式出处）：
#   bb72 / bb90 / bb108 / gross：arXiv:2308.07915 Table 3（research/literature/qldpc-code-catalog.md、search/codes/catalog.py）
#   bb120 [[120,8,12]]：l=20, m=3, A=1+x^3y^2+x^7y^2, B=1+x^16y+x^9y（E-004 用的码，search/proxy/candidates.py，
#         试运行发现、MILP 精确 d=12；与 arXiv:2601.09911 Table I 的 [[120,8,12]]（l,m=10,6）是否等价**未核实**）
#   cp126 coprime [[126,12,10]]：arXiv:2408.10001 Table 2，l=7, m=9, A=1+π+π^58, B=1+π^13+π^41（π=xy），
#         这里写成 x、y 的单项式：π^k = x^(k mod 7) y^(k mod 9)
# 约束：每校验一个辅助比特、所有行每轮都测（模板结构保证）；period ≤ 8（IBM 原电路的摊销深度）。
# 距离在 3 轮电路上算；种子由 (task_hash, schedule_hash) 派生；预算写死（README §9.4 的标定）。
DCIRC_BUDGET = {"distance_methods": ["graphlike", "bposd"], "distance_bposd_trials": 600, "distance_lns_starts": 32,
                "distance_lns_det_time": 1.0, "distance_timeout_s": 1800.0}
DCIRC_BUDGET_GROSS = {"distance_methods": ["graphlike", "bposd"], "distance_bposd_trials": 1500,
                      "distance_lns_starts": 96, "distance_lns_det_time": 1.0, "distance_timeout_s": 3600.0}

_DCIRC_CODES = [
    # task_id, (l, m, A, B), (n, k, d), d 的出处, 已知 d_circ 上界（IBM 调度）及出处
    ("bb72-dcirc", (6, 6, ["x^3", "y", "y^2"], ["y^3", "x", "x^2"]), (72, 12, 6), "arXiv:2308.07915 Table 3",
     "IBM depth-8: d_circ <= 6 (E-004)"),
    ("bb90-dcirc", (15, 3, ["x^9", "y", "y^2"], ["1", "x^2", "x^7"]), (90, 8, 10), "arXiv:2308.07915 Table 3",
     "IBM depth-8: d_circ <= 8 (E-004; 2308.07915 Table 1)"),
    ("bb108-dcirc", (9, 6, ["x^3", "y", "y^2"], ["y^3", "x", "x^2"]), (108, 8, 10), "arXiv:2308.07915 Table 3",
     "IBM depth-8: d_circ <= 8 (E-004; 2308.07915 Table 1)"),
    ("bb120-dcirc", (20, 3, ["1", "x^3*y^2", "x^7*y^2"], ["1", "x^16*y", "x^9*y"]), (120, 8, 12),
     "E-004 pilot (MILP exact); not in the literature catalogue", "IBM term order: d_circ <= 10 (E-004)"),
    ("cp126-dcirc", (7, 9, ["1", "x*y", "x^2*y^4"], ["1", "x^6*y^4", "x^6*y^5"]), (126, 12, 10),
     "arXiv:2408.10001 Table 2 (coprime BB)", "IBM term order: d_circ <= 9 (E-004; 2408.10001 Sec. 5.2)"),
    ("gross-dcirc", (12, 6, ["x^3", "y", "y^2"], ["y^3", "x", "x^2"]), (144, 12, 12), "arXiv:2308.07915 Table 3",
     "IBM depth-8: d_circ <= 10 (E-002); Strikis Fig. 12: 11 conjectured"),
]
for _tid, (_l, _m, _A, _B), (_n, _k, _d), _src, _known in _DCIRC_CODES:
    _TASK_LIST.append(Task(
        task_id=_tid,
        description=(f"distance-only task (H-004): [[{_n},{_k},{_d}]] BB code ({_src}); score = circuit-level distance "
                     f"upper bound on the 3-round memory circuits (both bases, SD6 fault locations), larger is better; "
                     f"ties: fewer minimum-weight witnesses, then smaller period. One ancilla per check, every row "
                     f"every round, period <= 8. Known: {_known}. No L2."),
        code_family={"kind": "bb", "fixed": {"l": _l, "m": _m, "A": _A, "B": _B}},
        noise_model="sd6", p=1e-3, decoder={}, boundary="none", rounds=3, stop={},
        l0={"min_circuit_distance": None, "distance_rounds": 3, "distance_seed": "derived",
            **(DCIRC_BUDGET_GROSS if _n > 126 else DCIRC_BUDGET)},
        num_workers=3, kind="distance", schedule_constraints={"max_period": 8},
    ))

for _t in _TASK_LIST:
    _t.validate()
TASKS: dict[str, Task] = {t.task_id: t for t in _TASK_LIST}
if len(TASKS) != len(_TASK_LIST):
    raise RuntimeError("duplicate task ids")


def get_task(task_id: str) -> Task:
    try:
        return TASKS[task_id]
    except KeyError:
        raise KeyError(f"unknown task {task_id!r}; registered: {sorted(TASKS)}") from None
