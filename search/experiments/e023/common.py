"""E-023: does +1 in proven circuit distance give a measurable LER benefit?  Shared tools.  experimenter.

A "problem" = one circuit (one member of an A/B pair) = a list of independently decoded *sectors*.  A sector is the
merged-column DEM of one memory basis (morphing circuits: separate Z- and X-memory circuits; BB108: the Z / X
sectors of the E-016 joint circuit; surface control: Z memory only).  Sector columns are independent mechanisms
(each joint mechanism maps to one column), so the sector marginal is exact.  LER(shot) ~= sum over sectors.

Noise models
  sd6      : evaluators/noise.py sd6 (evaluator default).
  si1000   : SI1000 coefficients of evaluators/noise.py (2q p, 1q p/10, meas 5p, reset 2p, idle p/10, resonator-idle
             2p) BUT with CX accepted as the native two-qubit gate (the evaluator's si1000 refuses CX and demands a
             CZ+H compilation).  We monkeypatch evaluators.noise._model_params at run time *in our process only*
             (no evaluator file is modified).  Circuit distance (a fault count) is noise-model independent because
             every fault location keeps a nonzero probability.

Circuits
  m54_<v>   : [[108,8,10]] mother code, f_y morphing (E-019 construction), v in paper/repo/std01/std10; T = 8.
  m72_<v>   : [[144,12,12]] mother code, f_y morphing, v in sw11/sw01; T = 8.
  bb108_<c> : E-016 model (evaluator template circuit, joint X/Z, boundary 'paper', 10 rounds), c in ibm/twocolour.
  sc5_<o>   : rotated surface code d=5 Z memory, 5 rounds, CNOT order good (hook across logical) / bad (along).
"""
from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import scipy.sparse as sp
import stim

ROOT = Path(__file__).resolve().parents[3]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = ROOT / "results" / "E-023-ler-benefit"
OUT.mkdir(parents=True, exist_ok=True)
P_DEC = 1e-3          # decoder priors are always the DEM at this p (fixed-prior decoders)

import evaluators.noise as _noise  # noqa: E402

_orig_params = _noise._model_params


def _patched_params(model, p, idle):
    prm = _orig_params(model, p, idle)
    if model == "si1000":
        prm = dict(prm)
        prm["native_2q"] = None          # accept CX with SI1000 coefficients
    return prm


_noise._model_params = _patched_params


def add_noise(c, model, p):
    return _noise.add_noise(c, model, p)


# ------------------------------------------------------------------ morphing circuits (E-019 construction)
def morph_plain(key: str, basis: str, T: int):
    """Noiseless morphing memory circuit + derived detectors/observables (copy of the record-kernel derivation in
    search/experiments/e019/instance.py build(); logic unchanged).  Returns (plain stim circuit, annotation)."""
    from search.experiments.e019.common import get_code, logicals, memory, nullspace, rank, rref, spec
    name, hom, variant = key.split("_")
    code = get_code(name)
    N = code.N
    gates, meas, _, _ = spec(code, hom, variant)
    C = memory(code, gates, meas, T, basis)
    mop = "M" if basis == "Z" else "MX"
    HX, HZ = code.checks()
    recs = C.recs
    same = [i for i, (tg, op, q) in enumerate(recs) if op == mop]
    grp = {}
    for i in same:
        (r, kind), op, q = recs[i]
        k = "F" if (r == T and q < N) else r
        grp.setdefault(k, []).append(i)
    for k in grp:
        grp[k] = sorted(grp[k])
    LOG = logicals(HX, HZ) if basis == "Z" else logicals(HZ, HX)
    kq = len(LOG)
    pchar = "X" if basis == "Z" else "Z"
    li_mid = [i for i, (ops, tg) in enumerate(C.layers) if tg == (1, "Fd2")][0]
    rand = stim.Circuit()
    for v in LOG:
        rand.append("E", [stim.target_x(q) if pchar == "X" else stim.target_z(q) for q in np.nonzero(v)[0]], 0.5)
    c_plain = C.stim()
    c_rand = C.stim({li_mid: rand})
    cols_all = same
    colpos = {c: i for i, c in enumerate(cols_all)}
    shots = max(1600, 3 * len(cols_all))

    def sample_kernel(circ, cols):
        s = circ.compile_sampler(seed=12345).sample(shots).astype(np.uint8)
        d = s ^ s[0]
        return nullspace(d[:, cols])

    def embed(vecs, sub):
        out = np.zeros((len(vecs), len(cols_all)), np.uint8)
        for j, c in enumerate(sub):
            out[:, colpos[c]] = vecs[:, j]
        return out

    Kdet = sample_kernel(c_rand, cols_all)
    Kall = sample_kernel(c_plain, cols_all)

    def rand_before_round(r):
        if r <= 1:
            return c_rand
        li = [i for i, (ops, tg) in enumerate(C.layers) if tg == (r - 1, "M")][0]
        ini = stim.Circuit()
        ini.append("X_ERROR" if basis == "Z" else "Z_ERROR", list(range(2 * N)), 0.5)
        return C.stim({li: ini, li_mid: rand} if li_mid > li else {li: ini})

    blocks = {1: embed(sample_kernel(c_rand, grp[1]), grp[1])}
    for t in range(2, T + 1):
        sub = grp[t - 1] + grp[t]
        blocks[t] = embed(sample_kernel(rand_before_round(t - 1), sub), sub)
    keep = []
    rk0 = rank(blocks[1])
    for v in blocks[2]:
        if rank(np.vstack([blocks[1]] + keep + [v[None]])) > rk0 + len(keep):
            keep.append(v[None])
    blocks[2] = np.vstack(keep)
    sub = grp[T] + grp["F"]
    fin = embed(sample_kernel(rand_before_round(T), sub), sub)
    base = blocks[T]
    rk = rank(base)
    extra = []
    for v in fin:
        if rank(np.vstack([base] + extra + [v[None]])) > rk + len(extra):
            extra.append(v[None])
    blocks[T + 1] = np.vstack(extra) if extra else np.zeros((0, len(cols_all)), np.uint8)

    def sparsify(B, first):
        if len(B) == 0:
            return B
        fs = set(colpos[c] for c in first)
        order_ = [colpos[c] for c in first] + [i for i in range(len(cols_all)) if i not in fs]
        Rm, _ = rref(B[:, order_])
        out = np.zeros_like(Rm)
        out[:, order_] = Rm
        return out

    for t in range(2, T + 1):
        blocks[t] = sparsify(blocks[t], grp[t])
    blocks[T + 1] = sparsify(blocks[T + 1], grp[T])
    Dall = np.vstack([blocks[t] for t in range(1, T + 2)])
    assert rank(np.vstack([Dall, Kdet])) == rank(Dall) == len(Kdet)
    subL = grp.get(T - 1, []) + grp[T] + grp["F"]
    Klate = embed(sample_kernel(c_plain, subL), subL)
    obs = []
    cur = Kdet.copy()
    rk = rank(cur)
    for v in list(Klate) + list(Kall):
        t2 = np.vstack([cur, v])
        if rank(t2) > rk:
            obs.append(v)
            cur = t2
            rk += 1
    assert len(obs) == kq
    ann = stim.Circuit()
    nrec = C.nrec
    for t in sorted(blocks):
        for v in blocks[t]:
            ann.append("DETECTOR", [stim.target_rec(cols_all[j] - nrec) for j in np.nonzero(v)[0]])
    for k, v in enumerate(obs):
        ann.append("OBSERVABLE_INCLUDE", [stim.target_rec(cols_all[j] - nrec) for j in np.nonzero(v)[0]], k)
    return c_plain, ann


# ------------------------------------------------------------------ surface-code positive control
def surface_plain(d: int, rounds: int, order: str):
    """Rotated surface code, Z memory, CX gates, 4 CNOT layers.  Data (i, j) 0<=i,j<d; Z logical = row of Z on
    i = 0 ... we use the standard convention: X-type checks have their hook pair parallel/perpendicular to the X
    logical depending on `order`.  For Z memory only X-error hooks matter: they come from Z-check ancillas
    (CX data->ancilla; an X fault on the ancilla mid-circuit does not propagate to data) -- no: for a Z-check the
    ancilla is the target, X on ancilla does not spread; Z on ancilla spreads to data as Z (irrelevant to Z memory).
    X-check ancilla is the control (CX anc->data): an X fault on it after 2 CNOTs spreads X onto the remaining 2
    data qubits -> weight-2 X hook, which matters for Z memory.  'good' : X-check hooks perpendicular to the Z
    logical's X-error direction (d_circ = d);  'bad': parallel (d_circ ~ ceil(d/2)+...).  Validated numerically by
    the minimum-weight search (positive control)."""
    # coordinates: data at (2i+1, 2j+1); ancillas at even (x, y)
    data = {(2 * i + 1, 2 * j + 1): None for i in range(d) for j in range(d)}
    anc = {}
    for x in range(0, 2 * d + 1, 2):
        for y in range(0, 2 * d + 1, 2):
            nb = [(x + dx, y + dy) for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)) if (x + dx, y + dy) in data]
            typ = "X" if ((x // 2 + y // 2) % 2 == 0) else "Z"
            if len(nb) == 4 or (len(nb) == 2 and ((typ == "X" and y in (0, 2 * d)) or (typ == "Z" and x in (0, 2 * d)))):
                anc[(x, y)] = typ
    qid = {}
    for c in sorted(data):
        qid[c] = len(qid)
    for c in sorted(anc):
        qid[c] = len(qid)
    # CNOT order over the 4 diagonal neighbours: offsets
    NE, NW, SE, SW = (1, -1), (-1, -1), (1, 1), (-1, 1)
    # X logical runs along y (x fixed boundary ... ) -- decide by test: choose orders, check min weight numerically.
    z_order = [NW, NE, SW, SE]                     # "N" shape for Z checks (standard)
    # labels fixed by the min-weight search (first run had them swapped; see journal): with this Z logical
    # (row y = 1), X-check order [NW, NE, SW, SE] gives d_circ = 5 and [NW, SW, NE, SE] gives 3.
    x_good = [NW, NE, SW, SE]
    x_bad = [NW, SW, NE, SE]
    x_order = x_good if order == "good" else x_bad
    c = stim.Circuit()
    dq = [qid[q] for q in sorted(data)]
    xa = [qid[a] for a in sorted(anc) if anc[a] == "X"]
    za = [qid[a] for a in sorted(anc) if anc[a] == "Z"]
    alla = xa + za
    c.append("R", dq)
    c.append("R", za)
    c.append("RX", xa)
    nmeas = 0
    zpos = sorted([a for a in anc if anc[a] == "Z"])
    xpos = sorted([a for a in anc if anc[a] == "X"])
    for r in range(rounds):
        if r > 0:
            c.append("TICK")
            c.append("R", za)
            c.append("RX", xa)
        for k in range(4):
            c.append("TICK")
            pairs = []
            for a in xpos:
                dx, dy = x_order[k]
                q = (a[0] + dx, a[1] + dy)
                if q in data:
                    pairs += [qid[a], qid[q]]
            for a in zpos:
                dx, dy = z_order[k]
                q = (a[0] + dx, a[1] + dy)
                if q in data:
                    pairs += [qid[q], qid[a]]
            c.append("CX", pairs)
        c.append("TICK")
        c.append("M", za)
        c.append("MX", xa)
        nz, nx = len(za), len(xa)
        for i in range(nz):
            if r == 0:
                c.append("DETECTOR", [stim.target_rec(-(nz + nx) + i)])
            else:
                c.append("DETECTOR", [stim.target_rec(-(nz + nx) + i), stim.target_rec(-2 * (nz + nx) + i)])
        nmeas += nz + nx
    c.append("TICK")
    c.append("M", dq)
    nd = len(dq)
    dpos = sorted(data)
    for i, a in enumerate(zpos):
        nbr = [dpos.index((a[0] + dx, a[1] + dy)) for dx, dy in (NE, NW, SE, SW) if (a[0] + dx, a[1] + dy) in data]
        c.append("DETECTOR", [stim.target_rec(-nd + j) for j in nbr] + [stim.target_rec(-nd - (nz + nx) + i)])
    # Z logical: Z on a column of data commuting with X checks -> pick data with x = 1 (first column)
    col = [i for i, q in enumerate(dpos) if q[1] == 1]
    c.append("OBSERVABLE_INCLUDE", [stim.target_rec(-nd + j) for j in col], 0)
    # detectors/observables are annotations; add_noise accepts them interleaved
    return c


# ------------------------------------------------------------------ sectors
class Sec:
    """Merged-column DEM of one sector.  H: detectors x cols (csc uint8), L: obs x cols (csr uint8), q: priors."""

    def __init__(self, label, H, L, q, keys):
        self.label, self.H, self.L, self.q, self.keys = label, H, L, np.asarray(q, float), keys
        self.ndet, self.ncol = H.shape
        self.nobs = L.shape[0]


def sector_from_dem(dem: stim.DetectorErrorModel, label: str, det_range=None, obs_range=None):
    """Merge DEM errors by (detectors, observables) restricted to the sector (detector/observable id ranges)."""
    d0, d1 = det_range if det_range else (0, dem.num_detectors)
    o0, o1 = obs_range if obs_range else (0, dem.num_observables)
    merged, order = {}, []
    free = 0.0
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        pr = inst.args_copy()[0]
        ds, os_ = set(), set()
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                if d0 <= t.val < d1:
                    ds ^= {t.val - d0}
            elif t.is_logical_observable_id():
                if o0 <= t.val < o1:
                    os_ ^= {t.val - o0}
        key = (tuple(sorted(ds)), tuple(sorted(os_)))
        if not key[0]:
            if key[1]:
                free = free * (1 - pr) + pr * (1 - free)
            continue
        if key not in merged:
            merged[key] = 0.0
            order.append(key)
        q = merged[key]
        merged[key] = q * (1 - pr) + pr * (1 - q)
    assert free == 0.0, f"{label}: detector-free logical mechanism (d_circ = 1?)"
    rows, ci, orows, oci = [], [], [], []
    for i, (d, o) in enumerate(order):
        rows += d
        ci += [i] * len(d)
        orows += o
        oci += [i] * len(o)
    H = sp.csc_matrix((np.ones(len(rows), np.uint8), (rows, ci)), shape=(d1 - d0, len(order)))
    L = sp.csr_matrix((np.ones(len(orows), np.uint8), (orows, oci)), shape=(o1 - o0, len(order)))
    return Sec(label, H, L, [merged[k] for k in order], order)


PROBLEMS = {}
for _v in ("paper", "repo", "std01", "std10"):
    PROBLEMS[f"m54_{_v}"] = dict(kind="morph", key=f"bb108_y_{_v}", T=8, k=8)
for _v in ("sw11", "sw01", "sw10"):
    PROBLEMS[f"m72_{_v}"] = dict(kind="morph", key=f"bb144_y_{_v}", T=8, k=12)
for _c in ("ibm", "twocolour"):
    PROBLEMS[f"bb108_{_c}"] = dict(kind="bb108", circ=_c, T=10, k=8)
for _o in ("good", "bad"):
    PROBLEMS[f"sc5_{_o}"] = dict(kind="surface", order=_o, d=5, T=5, k=1)

D_CIRC = {"m54_paper": 6, "m54_std01": 6, "m54_repo": 7, "m54_std10": 7, "m72_sw11": 6, "m72_sw01": 7,
          "m72_sw10": 7, "bb108_ibm": 8, "bb108_twocolour": 10}


@lru_cache(maxsize=None)
def _plain(name, basis):
    P = PROBLEMS[name]
    if P["kind"] == "morph":
        return morph_plain(P["key"], basis, P["T"])
    raise ValueError(name)


@lru_cache(maxsize=None)
def noisy_circuits(name: str, model: str, p: float):
    """Returns list of (label, noisy stim circuit, det_range, obs_range) -- one entry per sector."""
    P = PROBLEMS[name]
    if P["kind"] == "morph":
        out = []
        for b in "ZX":
            plain, ann = _plain(name, b)
            c = add_noise(plain, model, p) + ann
            out.append((b, c, None, None))
        return out
    if P["kind"] == "bb108":
        from evaluators import candidate as cand
        from evaluators.l2 import build_joint_circuit
        from search.experiments.e016.common import code_and_spec
        code, spec = code_and_spec(P["circ"])
        circs = cand.build_circuits(spec.canonical(), code, P["T"])
        lay = cand.layout_for(code)
        jc = build_joint_circuit(code, circs, list(lay.data), noise_model=model, p=p, boundary="paper")
        c = jc.circuit
        nz, oz = jc.num_detectors_z, jc.num_observables_z
        return [("Z", c, (0, nz), (0, oz)), ("X", c, (nz, c.num_detectors), (oz, c.num_observables))]
    if P["kind"] == "surface":
        plain = surface_plain(P["d"], P["T"], P["order"])
        return [("Z", add_noise(plain, model, p), None, None)]
    raise ValueError(name)


@lru_cache(maxsize=None)
def sectors(name: str, model: str, p: float):
    out = []
    dems = {}
    for label, c, dr, orr in noisy_circuits(name, model, p):
        if id(c) not in dems:
            dems[id(c)] = c.detector_error_model(allow_gauge_detectors=False)
        out.append(sector_from_dem(dems[id(c)], label, dr, orr))
    return out


def lam(sec: Sec) -> float:
    return float(sec.q.sum())


def weight_distribution(q: np.ndarray, wmax: int) -> np.ndarray:
    P = np.zeros(wmax + 1)
    P[0] = 1.0
    for x in q:
        P[1:] = P[1:] * (1 - x) + P[:-1] * x
        P[0] *= (1 - x)
    return P


def sample_fixed_weight(q: np.ndarray, w: int, n: int, rng) -> np.ndarray:
    """n sets of exactly w columns with P(S) ∝ prod r_i (r = q/(1-q)) -- exact rejection sampler (as E-006)."""
    r = q / (1 - q)
    lo, hi = 1e-12, 1e12
    for _ in range(200):
        lm = np.sqrt(lo * hi)
        m = (lm * r / (1 + lm * r)).sum()
        if m > w:
            hi = lm
        else:
            lo = lm
    qq = lm * r / (1 + lm * r)
    out = []
    while len(out) < n:
        B = rng.random((256, len(qq))) < qq[None, :]
        cnt = B.sum(1)
        for row in np.flatnonzero(cnt == w):
            out.append(np.flatnonzero(B[row]))
            if len(out) == n:
                break
    return np.array(out, dtype=np.int64).reshape(n, w)


# ------------------------------------------------------------------ decoders (fixed priors = DEM at P_DEC)
def make_decoder(sec: Sec, name: str):
    if name == "bposd":
        from ldpc import BpOsdDecoder
        from search.decoders.common import IBM_BPOSD
        d = BpOsdDecoder(sec.H, error_channel=list(sec.q), **IBM_BPOSD)
        return lambda s: np.asarray(d.decode(s), np.uint8)
    if name == "relay":
        import relay_bp
        from search.decoders.decoders import RELAY
        d = relay_bp.RelayDecoderF64(sec.H.tocsr(), error_priors=np.asarray(sec.q, np.float64), seed=20261003,
                                     **RELAY["relay5"])
        return lambda s: np.asarray(d.decode_detailed(s).decoding, np.uint8)
    if name == "pymatching":
        import pymatching
        m = pymatching.Matching.from_check_matrix(sec.H, weights=np.log((1 - sec.q) / sec.q),
                                                  faults_matrix=sec.L)
        return ("pm", m)
    raise ValueError(name)


def logical_of(sec: Sec, e: np.ndarray) -> np.ndarray:
    return (sec.L @ e) % 2


# ------------------------------------------------------------------ time-bulk region
@lru_cache(maxsize=None)
def det_rounds(name: str, label: str) -> np.ndarray:
    """Round index (1-based, = round of the latest measurement record it uses) of every sector detector."""
    P = PROBLEMS[name]
    if P["kind"] == "morph":
        plain, ann = _plain(name, label)
        n = plain.num_measurements
        per = plain.num_measurements // (P["T"] + 1)       # N records per round, N data records at the end
        out = []
        for inst in ann:
            if inst.name == "DETECTOR":
                out.append(max(n + t.value for t in inst.targets_copy()) // per + 1)
        return np.array(out)
    if P["kind"] == "bb108":
        sec = [s for s in sectors(name, "sd6", P_DEC) if s.label == label][0]
        return np.minimum(np.arange(sec.ndet) // 54 + 1, P["T"] + 1)
    if P["kind"] == "surface":
        sec = sectors(name, "sd6", P_DEC)[0]
        return np.minimum(np.arange(sec.ndet) // 12 + 1, P["T"] + 1)
    raise ValueError(name)


def bulk_mask(name: str, sec: Sec, lo: int = 3, hi_off: int = 1) -> tuple[np.ndarray, float]:
    """Columns whose detectors all lie in rounds lo .. T-hi_off (time bulk).  Returns (mask, rounds covered),
    rounds covered = λ(mask) / λ(per bulk round), λ per bulk round from columns whose latest round is the middle one."""
    T = PROBLEMS[name]["T"]
    dr = det_rounds(name, sec.label)
    H = sec.H.tocsc()
    mx = np.array([dr[H.indices[H.indptr[j]:H.indptr[j + 1]]].max() for j in range(sec.ncol)])
    mn = np.array([dr[H.indices[H.indptr[j]:H.indptr[j + 1]]].min() for j in range(sec.ncol)])
    mask = (mn >= lo) & (mx <= T - hi_off)
    mid = (lo + T - hi_off) // 2
    per_round = sec.q[mask & (mx == mid)].sum()
    return mask, float(sec.q[mask].sum() / per_round)
