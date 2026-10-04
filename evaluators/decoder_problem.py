"""解码器任务的“题目”：电路、按 sector 拆开的解码问题、保密种子与 shot 生成（H-005，2026-10-03）。

评估器自己生成电路（不 import search/ 或 baselines/）：
  - BB 码：IBM depth-8 调度（arXiv:2308.07915 Table 5；与 baselines/schedule.py 的 ibm_depth8 相同，代码搬进评估器，
    测试逐元素对照），模板 `candidate.memory_circuit`，噪声 sd6，boundary="paper"，X/Z 联合采样（`l2.build_joint_circuit`）。
  - 表面码（自检）：stim 生成的旋转表面码的标准 CNOT 顺序（与 tests/schedule_helpers.surface_schedule 相同）。

每个 sector（Z / X）的解码问题 = 联合 DEM 限制到该 sector、合并相同症状后**有症状**的机制（与 l2._SectorDecoder 的
BP-OSD 路径相同，E-002 / IBM 的“X、Z 分开解码”）：
    H      (num_det × M) GF(2) 稀疏矩阵（scipy.sparse.csc_matrix, uint8）
    L      (k × M)       每个机制翻转哪些 observable
    priors (M,)          机制概率
无症状但翻转 observable 的机制（不可检测的逻辑错误）不在 H 里，它们对任何解码器都一样。

## 保密种子

搜索集（split="search"）与留出集（split="holdout"）的 shot 由 repo 之外的密钥文件派生：
    root(split) = HMAC-SHA256(secret, "qec-decoder-shots|<task_id>|<task_hash>|<split>")
    第 b 批的 stim 种子 = SeedSequence([root, b]) 的第一个 uint64
密钥文件默认 ~/.config/qec-ai-search/decoder_secret.key（环境变量 QEC_DECODER_SECRET_FILE 可改，测试用），
内容是 64 个十六进制字符，权限必须是 0600，且不能在项目目录（worktree 或主目录）里。候选程序在沙箱里运行，
沙箱禁止读它（evaluators/decoder_sandbox.py）；父进程从不把种子或密钥传给候选。
自检任务（purpose="selftest"）另有 split="public"：种子由公开常量派生，不需要密钥（测试、演示用）。
"""
from __future__ import annotations

import functools
import hashlib
import hmac
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import stim

from evaluators import candidate as cand
from evaluators.codes import CSSCode, rotated_surface_code_from_stim
from evaluators.l2 import build_joint_circuit, split_dem

__all__ = [
    "SPLITS", "SECRET_ENV", "DEFAULT_SECRET_PATH", "SecretError",
    "ibm_schedule", "surface_schedule", "SectorProblem", "DecodingInstance", "build_instance",
    "secret_path", "load_secret", "ensure_secret", "split_root", "batch_seed", "sample_batch",
    "project_roots",
]

SPLITS = ("search", "holdout", "public")
SECRET_ENV = "QEC_DECODER_SECRET_FILE"
DEFAULT_SECRET_PATH = Path("~/.config/qec-ai-search/decoder_secret.key")
EVAL_DIR = Path(__file__).resolve().parent
ROOT = EVAL_DIR.parent


class SecretError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# 项目根目录（worktree 与主目录）
# ---------------------------------------------------------------------------

def project_roots() -> list[Path]:
    """本项目的所有根目录：当前 checkout（可能是 worktree），以及 git 主目录（worktree 的 .git 文件指向的
    common dir 的上一级）。沙箱要同时屏蔽两者：从 worktree 运行时，只屏蔽 worktree 会让主目录的 evaluators/ 可读。"""
    roots = [ROOT]
    g = ROOT / ".git"
    try:
        if g.is_file():
            txt = g.read_text(encoding="utf-8").strip()
            if txt.startswith("gitdir:"):
                gitdir = Path(txt.split(":", 1)[1].strip())
                if not gitdir.is_absolute():
                    gitdir = (ROOT / gitdir).resolve()
                # <main>/.git/worktrees/<name>  ->  <main>
                common = gitdir.parent.parent
                if common.name == ".git":
                    roots.append(common.parent.resolve())
    except OSError:
        pass
    # 另一个保险：路径里出现 .claude/worktrees/<name> 时，其上三级是主目录
    parts = ROOT.parts
    for i in range(len(parts) - 2):
        if parts[i] == ".claude" and parts[i + 1] == "worktrees":
            roots.append(Path(*parts[:i]).resolve())
    out = []
    for r in roots:
        if r not in out:
            out.append(r)
    return out


# ---------------------------------------------------------------------------
# 密钥与种子
# ---------------------------------------------------------------------------

def secret_path() -> Path:
    p = os.environ.get(SECRET_ENV)
    return Path(p).expanduser().resolve() if p else DEFAULT_SECRET_PATH.expanduser().resolve()


def _check_secret_location(p: Path) -> None:
    for r in project_roots():
        if p == r or r in p.parents:
            raise SecretError(f"decoder secret {p} is inside the project directory {r}; it must live outside the repo")


def load_secret() -> bytes:
    p = secret_path()
    _check_secret_location(p)
    if not p.exists():
        raise SecretError(f"decoder secret file {p} does not exist; create it with "
                          f"`uv run python -m evaluators.decoder_eval init-secret` (PI)")
    st = p.stat()
    if stat.S_IMODE(st.st_mode) & 0o077:
        raise SecretError(f"decoder secret file {p} must not be readable by group/others (chmod 600)")
    txt = p.read_text(encoding="ascii").strip()
    try:
        key = bytes.fromhex(txt)
    except ValueError as e:
        raise SecretError(f"decoder secret file {p} must contain hex") from e
    if len(key) < 32:
        raise SecretError("decoder secret must be at least 32 bytes")
    return key


def ensure_secret() -> Path:
    """创建密钥文件（不存在时）；返回路径。只应由 PI / lead 在正式使用前执行一次。"""
    import secrets as _secrets
    p = secret_path()
    _check_secret_location(p)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(_secrets.token_hex(32) + "\n")
    return p


def split_root(task_id: str, task_hash: str, split: str) -> int:
    """split 的根种子（整数）。search / holdout 需要密钥；public 由公开常量派生。"""
    if split not in SPLITS:
        raise ValueError(f"split must be one of {SPLITS}")
    msg = f"qec-decoder-shots|{task_id}|{task_hash}|{split}".encode()
    key = b"qec-ai-search public decoder shots (not secret)" if split == "public" else load_secret()
    return int.from_bytes(hmac.new(key, msg, hashlib.sha256).digest(), "big")


def batch_seed(root: int, index: int) -> int:
    return int(np.random.SeedSequence([root, int(index)]).generate_state(1, dtype=np.uint64)[0])


# ---------------------------------------------------------------------------
# 调度（评估器自带，不 import baselines）
# ---------------------------------------------------------------------------

# IBM depth-8（arXiv:2308.07915 Table 5；与 baselines/schedule.py 相同）：项编号 0,1,2 = A1,A2,A3；3,4,5 = B1,B2,B3。
IBM_SX = (None, 1, 4, 3, 5, 0, 2)   # X 校验在 CNOT 层 0..6 用的项
IBM_SZ = (0, 2, 3, 4, 5, 1, None)   # Z 校验


def _bb_term_mats(l: int, m: int, terms) -> list[np.ndarray]:
    from evaluators.tasks import bb_matrices
    out = []
    for t in terms:
        H, _ = bb_matrices(l, m, [t], ["1"])
        out.append(H[:, : l * m])
    return out


def ibm_schedule(l: int, m: int, A, B) -> cand.ScheduleSpec:
    """BB 码的 IBM depth-8 调度（周期 8）：X 校验 prep 0 / CNOT 1..6 / meas 7；Z 校验 prep 7 / CNOT 0..5 / meas 6。
    码的列顺序：L 块 0..n2-1，R 块 n2..2n2-1（与 tasks.bb_matrices 相同）。"""
    n2 = l * m
    Am, Bm = _bb_term_mats(l, m, A), _bb_term_mats(l, m, B)
    xs, zs = [], []
    for i in range(n2):
        cn = {}
        for t, term in enumerate(IBM_SX):
            if term is None:
                continue
            col = int(np.flatnonzero(Am[term][i])[0]) if term < 3 else n2 + int(np.flatnonzero(Bm[term - 3][i])[0])
            cn[col] = t
        xs.append((0, 7, cn))
    for i in range(n2):
        cn = {}
        for t, term in enumerate(IBM_SZ):
            if term is None:
                continue
            # Z 校验 i：A_t -> R 块的 j（A_t[j, i] = 1）；B_t -> L 块的 j（B_t[j, i] = 1）
            col = n2 + int(np.flatnonzero(Am[term][:, i])[0]) if term < 3 else int(np.flatnonzero(Bm[term - 3][:, i])[0])
            cn[col] = t
        zs.append((7, 6, cn))
    return cand.schedule_from_cyclic_layers(8, xs, zs)


def surface_schedule(d: int) -> tuple[CSSCode, cand.ScheduleSpec]:
    """旋转表面码 + stim 生成电路里的 CNOT 顺序（4 个 CNOT 层），周期 6（与 tests/schedule_helpers 相同）。"""
    code, data, circ = rotated_surface_code_from_stim(d, "Z", 2)
    col = {q: j for j, q in enumerate(data)}
    cx_layer = 0
    times: dict[int, dict[int, int]] = {}
    h_qubits = set()
    for inst in circ.flattened():
        if inst.name == "H":
            h_qubits.update(t.value for t in inst.targets_copy())
        if inst.name == "CX":
            cx_layer += 1
            for a, b in inst.target_groups():
                a, b = a.value, b.value
                anc, dq = (a, b) if a not in col else (b, a)
                times.setdefault(anc, {})[col[dq]] = cx_layer
        if inst.name in ("MR", "M") and cx_layer >= 4:
            break
    xs = [a for a in sorted(times) if a in h_qubits]
    zs = [a for a in sorted(times) if a not in h_qubits]

    def ordered(ancs, H):
        out = []
        for i in range(H.shape[0]):
            a = next(a for a in ancs if sorted(times[a]) == np.flatnonzero(H[i]).tolist())
            out.append(cand.CheckTiming(0, 5, tuple(sorted(times[a].items()))))
        return tuple(out)

    return code, cand.ScheduleSpec(6, ordered(xs, code.HX), ordered(zs, code.HZ))


# ---------------------------------------------------------------------------
# 解码问题
# ---------------------------------------------------------------------------

@dataclass
class SectorProblem:
    sector: str                    # "Z" | "X"
    H: sp.csc_matrix               # num_det × M, uint8
    L: sp.csr_matrix               # k × M, uint8
    priors: np.ndarray             # (M,) float64
    det_coords: list               # 每个 detector 的 [校验行号, 轮次, 类型(0=X,1=Z)]（memory 电路的坐标）
    num_undetectable: int          # 无症状但翻转 observable 的机制数（不进 H）

    @property
    def num_det(self) -> int:
        return self.H.shape[0]

    @property
    def num_obs(self) -> int:
        return self.L.shape[0]

    def to_payload(self) -> dict:
        """发给沙箱的纯数据：列支撑（稀疏）、observable 支撑、先验。"""
        Hc = self.H.tocsc()
        Lc = self.L.tocsc()
        return {"num_det": int(self.num_det), "num_obs": int(self.num_obs), "num_mech": int(self.H.shape[1]),
                "H_cols": [Hc.indices[Hc.indptr[j]:Hc.indptr[j + 1]].tolist() for j in range(Hc.shape[1])],
                "L_cols": [Lc.indices[Lc.indptr[j]:Lc.indptr[j + 1]].tolist() for j in range(Lc.shape[1])],
                "priors": [float(x) for x in self.priors]}

    def fingerprint(self) -> str:
        h = hashlib.sha256()
        for M in (self.H.tocsc(), self.L.tocsc()):
            M = M.copy()
            M.sort_indices()
            h.update(repr(M.shape).encode())
            h.update(M.indptr.astype(np.int64).tobytes())
            h.update(M.indices.astype(np.int64).tobytes())
        h.update(np.asarray(self.priors, dtype=np.float64).tobytes())
        return h.hexdigest()


@dataclass
class DecodingInstance:
    task_id: str
    task_hash: str
    code: CSSCode
    schedule: cand.ScheduleSpec
    rounds: int
    p: float
    noise_model: str
    circuit: stim.Circuit          # 联合电路（带噪声）
    num_det_z: int
    num_obs_z: int
    sectors: dict = field(default_factory=dict)    # "Z"/"X" -> SectorProblem
    circuit_hash: str = ""

    def info(self, sector: str) -> dict:
        """给候选 make_decoder 的 info（纯数据，不含任何种子）。"""
        sp_ = self.sectors[sector]
        H = self.code.HZ if sector == "Z" else self.code.HX
        return {"task_id": self.task_id, "sector": sector, "rounds": self.rounds, "p": self.p,
                "noise_model": self.noise_model, "num_detectors": sp_.num_det, "num_observables": sp_.num_obs,
                "num_mechanisms": int(sp_.H.shape[1]), "detector_coords": sp_.det_coords,
                "code": {"n": self.code.n, "k": self.code.k,
                         "checks": [np.flatnonzero(r).tolist() for r in H]},
                "note": "detector_coords[i] = [check row, round (rounds = final readout comparison), "
                        "type 0=X/1=Z]; the sector's detectors are this basis' checks only"}


def _sector_matrices(model: dict, num_det: int, num_obs: int):
    cols = sorted(((d, o, pr) for (d, o), pr in model.items() if d), key=lambda x: (x[0], x[1]))
    undetectable = sum(1 for (d, o) in model if not d and o)
    rows, cidx, orows, ocidx = [], [], [], []
    for j, (d, o, _) in enumerate(cols):
        rows.extend(d); cidx.extend([j] * len(d))
        orows.extend(o); ocidx.extend([j] * len(o))
    H = sp.csc_matrix((np.ones(len(rows), dtype=np.uint8), (rows, cidx)), shape=(num_det, len(cols)))
    L = sp.csr_matrix((np.ones(len(orows), dtype=np.uint8), (orows, ocidx)), shape=(num_obs, len(cols)))
    return H, L, np.array([pr for _, _, pr in cols], dtype=np.float64), undetectable


def _code_and_schedule(task) -> tuple[CSSCode, cand.ScheduleSpec]:
    from evaluators.tasks import build_code
    fam = task.code_family
    if fam["kind"] == "bb":
        code, norm = build_code(task, None)
        return code, ibm_schedule(norm["l"], norm["m"], norm["A"], norm["B"])
    if fam["kind"] == "rotated_surface":
        code, spec = surface_schedule(int(fam["fixed"]["d"]))
        code2, _ = build_code(task, None)
        if not (np.array_equal(code.HX, code2.HX) and np.array_equal(code.HZ, code2.HZ)):
            raise RuntimeError("surface code rows differ from the task code (internal error)")
        return code2, spec
    raise ValueError(f"no decoder schedule for code family {fam['kind']!r}")


@functools.lru_cache(maxsize=8)
def _build_instance_cached(task_id: str, task_hash: str) -> DecodingInstance:
    from evaluators.l2 import circuit_hash
    from evaluators.tasks import get_task
    task = get_task(task_id)
    if task.hash() != task_hash:
        raise RuntimeError("task changed at runtime")
    code, spec = _code_and_schedule(task)
    spec = spec.canonical()
    if cand.validate_schedule(spec, code):
        raise RuntimeError(f"internal schedule invalid: {cand.validate_schedule(spec, code)[:3]}")
    circuits = cand.build_circuits(spec, code, task.rounds)
    lay = cand.layout_for(code)
    joint = build_joint_circuit(code, circuits, list(lay.data), noise_model=task.noise_model, p=task.p,
                                boundary=task.boundary)
    nz, oz = joint.num_detectors_z, joint.num_observables_z
    dem = joint.circuit.detector_error_model(allow_gauge_detectors=False)
    model = split_dem(dem, nz, oz)
    ndet, nobs = joint.circuit.num_detectors, joint.circuit.num_observables
    sectors = {}
    for s, nd, no in (("Z", nz, oz), ("X", ndet - nz, nobs - oz)):
        coords_map = circuits[s].get_detector_coordinates()
        if len(coords_map) != nd:
            raise RuntimeError(f"sector {s}: {len(coords_map)} memory-circuit detectors vs {nd} joint detectors")
        coords = [[int(round(c)) for c in coords_map[i]] for i in range(nd)]
        H, L, pri, und = _sector_matrices(model[s], nd, no)
        sectors[s] = SectorProblem(s, H, L, pri, coords, und)
    return DecodingInstance(task_id, task_hash, code, spec, task.rounds, task.p, task.noise_model, joint.circuit,
                            nz, oz, sectors, circuit_hash(circuits))


def build_instance(task) -> DecodingInstance:
    return _build_instance_cached(task.task_id, task.hash())


def sample_batch(inst: DecodingInstance, root: int, index: int, shots: int):
    """第 index 批：返回 {"Z": (dets bool (shots, nd), obs bool (shots, k)), "X": (...)}。只在父进程里调用。"""
    s = batch_seed(root, index)
    sampler = inst.circuit.compile_detector_sampler(seed=s)
    dets, obs = sampler.sample(shots, separate_observables=True)
    nz, oz = inst.num_det_z, inst.num_obs_z
    return {"Z": (dets[:, :nz], obs[:, :oz]), "X": (dets[:, nz:], obs[:, oz:])}
