"""CSS 码数据结构与 GF(2) 线性代数工具。

约定（全部为 numpy uint8，取值 0/1，运算在 GF(2) 上）：
  - HX: (mx, n)  X 型稳定子生成元（行可以冗余，例如 BB 码）
  - HZ: (mz, n)  Z 型稳定子生成元
  - LX: (k, n)   X 型逻辑算符
  - LZ: (k, n)   Z 型逻辑算符，要求 LX @ LZ.T = I_k（互相配对）
列 j 对应码的第 j 个数据比特；电路里的物理比特编号由 L0Constraints.data_qubits 给出映射。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


# ---------------------------------------------------------------------------
# GF(2) 基础
# ---------------------------------------------------------------------------

def _as_gf2(a) -> np.ndarray:
    a = np.asarray(a)
    if a.ndim == 1:
        a = a.reshape(1, -1)
    if a.ndim != 2:
        raise ValueError(f"expected a 2D matrix, got shape {a.shape}")
    if a.size and not np.all((a == 0) | (a == 1)):
        raise ValueError("GF(2) matrix entries must be 0/1")
    return (a.astype(np.uint8) & 1)


def row_reduce(a) -> tuple[np.ndarray, list[int]]:
    """Reduced row echelon form over GF(2). Returns (rref with zero rows removed, pivot columns)."""
    m = _as_gf2(a).copy()
    rows, cols = m.shape
    pivots: list[int] = []
    r = 0
    for c in range(cols):
        if r >= rows:
            break
        nz = np.nonzero(m[r:, c])[0]
        if nz.size == 0:
            continue
        p = r + nz[0]
        if p != r:
            m[[r, p]] = m[[p, r]]
        others = np.nonzero(m[:, c])[0]
        others = others[others != r]
        if others.size:
            m[others] ^= m[r]
        pivots.append(c)
        r += 1
    return m[:r], pivots


def rank(a) -> int:
    a = _as_gf2(a)
    if a.size == 0:
        return 0
    return len(row_reduce(a)[1])


def nullspace(a) -> np.ndarray:
    """Basis (rows) of {x : a @ x = 0} over GF(2)."""
    a = _as_gf2(a)
    n = a.shape[1]
    if a.shape[0] == 0:
        return np.eye(n, dtype=np.uint8)
    rref, piv = row_reduce(a)
    free = [c for c in range(n) if c not in set(piv)]
    basis = np.zeros((len(free), n), dtype=np.uint8)
    for i, f in enumerate(free):
        basis[i, f] = 1
        for r, pc in enumerate(piv):
            if rref[r, f]:
                basis[i, pc] = 1
    return basis


def in_rowspace(v, a) -> bool:
    """v (1D) 是否在 a 的行空间里。"""
    v = _as_gf2(v)
    a = _as_gf2(a)
    if a.shape[0] == 0:
        return not v.any()
    return rank(np.vstack([a, v])) == rank(a)


def solve_left(a, b) -> np.ndarray | None:
    """Find x (1D, len = rows of a) with x @ a = b over GF(2), or None."""
    a = _as_gf2(a)
    b = _as_gf2(b).reshape(-1)
    m, n = a.shape
    aug = np.hstack([a.T, b.reshape(-1, 1)])  # (n, m+1): a.T x = b
    rref, piv = row_reduce(aug)
    if m in piv:
        return None
    x = np.zeros(m, dtype=np.uint8)
    for r, pc in enumerate(piv):
        x[pc] = rref[r, m]
    return x


class GF2Basis:
    """增量式 GF(2) 向量空间，向量用 Python int 位集表示（适合几千维的稀疏集合）。"""

    def __init__(self) -> None:
        self._basis: dict[int, int] = {}  # leading bit -> vector

    def reduce(self, v: int) -> int:
        while v:
            hb = v.bit_length() - 1
            b = self._basis.get(hb)
            if b is None:
                return v
            v ^= b
        return 0

    def add(self, v: int) -> bool:
        r = self.reduce(v)
        if r:
            self._basis[r.bit_length() - 1] = r
            return True
        return False

    def contains(self, v: int) -> bool:
        return self.reduce(v) == 0

    def __len__(self) -> int:
        return len(self._basis)


def bits_to_int(indices) -> int:
    v = 0
    for i in indices:
        v ^= 1 << int(i)
    return v


# ---------------------------------------------------------------------------
# 码
# ---------------------------------------------------------------------------

def code_dimension(HX, HZ) -> int:
    """k = n - rank(HX) - rank(HZ)."""
    HX = _as_gf2(HX)
    HZ = _as_gf2(HZ)
    return HX.shape[1] - rank(HX) - rank(HZ)


def compute_logicals(HX, HZ) -> tuple[np.ndarray, np.ndarray]:
    """给出一组配对好的逻辑算符 (LX, LZ)，满足 LX @ LZ.T = I。

    LZ 取 ker(HX) 模 rowspace(HZ) 的一组代表元；LX 取 ker(HZ) 模 rowspace(HX)，
    然后对 LX 做基变换使配对矩阵为单位阵。
    """
    HX = _as_gf2(HX)
    HZ = _as_gf2(HZ)
    k = code_dimension(HX, HZ)

    def reps(kernel_of, modulo):
        ker = nullspace(kernel_of)
        chosen = []
        cur = modulo.copy()
        r0 = rank(cur) if cur.size else 0
        for v in ker:
            cand = np.vstack([cur, v]) if cur.size else v.reshape(1, -1)
            r1 = rank(cand)
            if r1 > r0:
                chosen.append(v)
                cur, r0 = cand, r1
            if len(chosen) == k:
                break
        return np.array(chosen, dtype=np.uint8).reshape(len(chosen), HX.shape[1])

    LZ = reps(HX, HZ)
    LX = reps(HZ, HX)
    if LZ.shape[0] != k or LX.shape[0] != k:
        raise RuntimeError("failed to find k logical operators")
    P = (LX.astype(np.int64) @ LZ.T.astype(np.int64)) % 2
    Pinv = gf2_inverse(P)
    LX = ((Pinv.astype(np.int64) @ LX.astype(np.int64)) % 2).astype(np.uint8)
    return LX, LZ


def gf2_inverse(a) -> np.ndarray:
    a = _as_gf2(a)
    n = a.shape[0]
    if a.shape != (n, n):
        raise ValueError("matrix must be square")
    aug = np.hstack([a, np.eye(n, dtype=np.uint8)])
    rref, piv = row_reduce(aug)
    if piv[:n] != list(range(n)):
        raise ValueError("matrix is singular over GF(2)")
    return rref[:, n:]


@dataclass
class CSSCode:
    HX: np.ndarray
    HZ: np.ndarray
    LX: np.ndarray
    LZ: np.ndarray
    name: str = ""
    validate: bool = field(default=True, repr=False)

    def __post_init__(self) -> None:
        self.HX = _as_gf2(self.HX)
        self.HZ = _as_gf2(self.HZ)
        self.LX = _as_gf2(self.LX)
        self.LZ = _as_gf2(self.LZ)
        if self.validate:
            problems = self.check()
            if problems:
                raise ValueError(f"invalid CSSCode {self.name!r}:\n  - " + "\n  - ".join(problems))

    @classmethod
    def from_checks(cls, HX, HZ, name: str = "") -> "CSSCode":
        LX, LZ = compute_logicals(HX, HZ)
        return cls(HX=HX, HZ=HZ, LX=LX, LZ=LZ, name=name)

    @property
    def n(self) -> int:
        return self.HX.shape[1]

    @property
    def k(self) -> int:
        return code_dimension(self.HX, self.HZ)

    def check(self) -> list[str]:
        """自检，返回问题列表（空 = 合法）。"""
        p: list[str] = []
        n = self.HX.shape[1]
        for nm, m in (("HZ", self.HZ), ("LX", self.LX), ("LZ", self.LZ)):
            if m.shape[1] != n:
                p.append(f"{nm} has {m.shape[1]} columns, HX has {n}")
        if p:
            return p
        if ((self.HX.astype(np.int64) @ self.HZ.T) % 2).any():
            p.append("HX @ HZ^T != 0: X and Z stabilizers do not commute")
        k = self.k
        if self.LX.shape[0] != k or self.LZ.shape[0] != k:
            p.append(f"expected k={k} logical operators, got LX:{self.LX.shape[0]} LZ:{self.LZ.shape[0]}")
        if ((self.LX.astype(np.int64) @ self.HZ.T) % 2).any():
            p.append("some LX anticommutes with a Z stabilizer (LX @ HZ^T != 0)")
        if ((self.LZ.astype(np.int64) @ self.HX.T) % 2).any():
            p.append("some LZ anticommutes with an X stabilizer (LZ @ HX^T != 0)")
        if self.LX.shape[0] == self.LZ.shape[0]:
            P = (self.LX.astype(np.int64) @ self.LZ.T) % 2
            if not np.array_equal(P, np.eye(self.LX.shape[0], dtype=np.int64)):
                p.append("LX @ LZ^T != I: logical operators are not pairwise conjugate")
        # 不在稳定子空间内（独立于稳定子）。配对为 I 时已隐含，这里显式检查以便给出诊断。
        for nm, L, H in (("LX", self.LX, self.HX), ("LZ", self.LZ, self.HZ)):
            if L.shape[0] and rank(np.vstack([H, L])) != rank(H) + L.shape[0]:
                p.append(f"{nm} rows are not independent modulo the stabilizer group (some combination is a stabilizer)")
        return p

    def is_logical_z(self, v) -> bool:
        """v 是否是非平凡的 Z 型逻辑算符：v ∈ ker(HX) 且 v ∉ rowspace(HZ)。"""
        v = _as_gf2(v).reshape(-1)
        return not ((self.HX.astype(np.int64) @ v) % 2).any() and not in_rowspace(v, self.HZ)

    def is_logical_x(self, v) -> bool:
        v = _as_gf2(v).reshape(-1)
        return not ((self.HZ.astype(np.int64) @ v) % 2).any() and not in_rowspace(v, self.HX)


# ---------------------------------------------------------------------------
# 测试辅助：从 stim 生成的旋转表面码电路构造 CSSCode
# ---------------------------------------------------------------------------

def rotated_surface_code_from_stim(distance: int, basis: str = "Z", rounds: int | None = None):
    """返回 (code, data_qubits, noiseless_circuit)。

    data_qubits[j] 是码第 j 列在 stim 电路中的比特编号。
    稳定子从电路结构读出：辅助比特 = 被测量过不止一次的比特（MR）；
    其类型由是否被 H 作用判断（X 型辅助比特前后有 H）；支撑 = 与其做过 CX 的数据比特。
    这是测试辅助函数，不是评估器的一部分。
    """
    import stim

    rounds = distance if rounds is None else rounds
    task = "surface_code:rotated_memory_" + basis.lower()
    circ = stim.Circuit.generated(task, distance=distance, rounds=rounds)
    flat = circ.flattened()
    meas_count: dict[int, int] = {}
    h_qubits: set[int] = set()
    partners: dict[int, set[int]] = {}
    for inst in flat:
        name = inst.name
        if name in ("M", "MR", "MX", "MRX"):
            for t in inst.targets_copy():
                meas_count[t.value] = meas_count.get(t.value, 0) + 1
        elif name == "H":
            h_qubits.update(t.value for t in inst.targets_copy())
        elif name == "CX":
            for a, b in inst.target_groups():
                partners.setdefault(a.value, set()).add(b.value)
                partners.setdefault(b.value, set()).add(a.value)
    ancillas = sorted(q for q, c in meas_count.items() if c > 1)
    data = sorted(q for q in meas_count if q not in set(ancillas))
    col = {q: j for j, q in enumerate(data)}
    hx, hz = [], []
    for a in ancillas:
        row = np.zeros(len(data), dtype=np.uint8)
        for q in partners[a]:
            row[col[q]] = 1
        (hx if a in h_qubits else hz).append(row)
    code = CSSCode.from_checks(np.array(hx), np.array(hz), name=f"rotated_surface_d{distance}")
    return code, data, circ
