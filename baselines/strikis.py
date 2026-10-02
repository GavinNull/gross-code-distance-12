"""E-003: Strikis-Browne-Beverland conjectured d_circ=11 circuit for the gross code [[144,12,12]].

Source: arXiv:2603.05481 v2, App. H.2 "An explicit 3-coloured circuit", Fig. 12 (schedule), Fig. 10 (Tanner
graph layout, three-colouring, long-range edges), Sec. III.A (left-right circuits).

  uv run python -m baselines.strikis --config experiments/E-003-strikis-gross.yaml [--stage ...]

Stages: verify | l0 | distance | sample | analyze   (default: all, in order)

How the figure is turned into a schedule (details and checks in the E-003 journal):
  * Fig. 10 is a 12-row x 24-column torus. Even rows: X checks (even cols) and "open" data circles (odd cols);
    odd rows: "filled" data circles (even cols) and Z checks (odd cols). Nearest-neighbour edges are the grid
    edges; the two long-range edges (drawn for one check of each type) are, read off the figure,
      X check (r,c): filled (r-3, c+6) [up-right], open (r+6, c-3) [down-left]
      Z check (r,c): filled (r-6, c+3) [up-right], open (r+3, c-6) [down-left]
    Check colours (R,G,B) were read from the figure pixels: colour index = (r//2 + c//2) mod 3, R=0,G=1,B=2.
  * Lattice indices: X check / open circle at (2i, 2j / 2j+1) -> (i,j); filled circle / Z check at (2i+1, 2j / 2j+1)
    -> (i,j); i in Z6, j in Z12.
  * `lattice_to_bb` finds (by exhaustive search over group isomorphisms Z6xZ12 -> Z12xZ6 and block shifts) the
    maps that turn this lattice Tanner graph into the project's BBCode (A = x^3+y+y^2, B = y^3+x+x^2). Exactly two
    exist (related by a code automorphism exchanging the blocks); we use the first one (filled -> L, open -> R).
  * Fig. 12 gives, for each colour and check type, the CNOT time step (1..8) of each of the 6 neighbours
    (up/down/left/right/up-right/down-left), plus prep and measurement time steps. Times are cyclic mod 8
    (several checks wrap around the cycle boundary), i.e. the circuit is staggered across rounds; it is unrolled
    by `baselines.circuit.pipelined_memory_circuit`.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import time
from pathlib import Path

import numpy as np
import yaml

from baselines.bb_code import BBCode
from baselines.circuit import pipelined_memory_circuit, check_deterministic, unroll_schedule, memory_circuit
from baselines.schedule import Schedule, Layer, bb_layout, ibm_depth8

RESULTS = Path("results")

# ---------------------------------------------------------------- Fig. 12 (arXiv:2603.05481 v2), verbatim numbers
# direction -> CNOT time step (1..8); "prep"/"meas" -> time step. Colours: R(ed), G(reen), B(lue).
FIG12 = {
    "Z": {
        "B": {"up": 4, "down": 5, "left": 6, "right": 8, "ur": 7, "dl": 3, "prep": 2, "meas": 1},
        "R": {"up": 4, "down": 2, "left": 7, "right": 6, "ur": 5, "dl": 3, "prep": 1, "meas": 8},
        "G": {"up": 4, "down": 2, "left": 5, "right": 7, "ur": 6, "dl": 3, "prep": 1, "meas": 8},
    },
    "X": {
        "B": {"up": 2, "down": 4, "left": 8, "right": 1, "ur": 3, "dl": 7, "prep": 6, "meas": 5},
        "R": {"up": 2, "down": 1, "left": 7, "right": 8, "ur": 3, "dl": 6, "prep": 5, "meas": 4},
        "G": {"up": 2, "down": 1, "left": 6, "right": 7, "ur": 3, "dl": 8, "prep": 5, "meas": 4},
    },
}
COLOURS = "RGB"

# ---------------------------------------------------------------- Fig. 10 lattice (lattice index (i, j), i mod 6, j mod 12)
# neighbour (kind, di, dj): kind 'F' = filled data circle, 'O' = open data circle
X_NEIGH = {"up": ("F", -1, 0), "down": ("F", 0, 0), "left": ("O", 0, -1), "right": ("O", 0, 0),
           "ur": ("F", -2, 3), "dl": ("O", 3, -2)}
Z_NEIGH = {"up": ("O", 0, 0), "down": ("O", 1, 0), "left": ("F", 0, 0), "right": ("F", 0, 1),
           "ur": ("F", -3, 2), "dl": ("O", 2, -3)}
NI, NJ = 6, 12


def colour(i: int, j: int) -> str:
    """Colour of the X check (2i,2j) or the Z check (2i+1,2j+1) in Fig. 10 (read from pixels)."""
    return COLOURS[(i + j) % 3]


def _exponent(term: str, l: int, m: int) -> tuple[int, int]:
    v = term[0]
    p = int(term.split("^")[1]) if "^" in term else 1
    return (p % l, 0) if v == "x" else (0, p % m)


def lattice_to_bb(code: BBCode) -> list[dict]:
    """All isomorphisms lattice -> BBCode of the form
        X check u -> X row phi(u);  filled f -> blockF[phi(f)+sF];  open o -> blockO[phi(o)+sO];  Z check w -> Z row phi(w)+sZ
    with phi a group isomorphism Z6xZ12 -> Z_l x Z_m (BB index = a*m + b). Brute force."""
    l, m = code.l, code.m
    Aset = {_exponent(t, l, m) for t in code.A_terms}
    Bset = {_exponent(t, l, m) for t in code.B_terms}
    G = [(a, b) for a in range(l) for b in range(m)]
    add = lambda u, v: ((u[0] + v[0]) % l, (u[1] + v[1]) % m)  # noqa: E731
    neg = lambda u: ((-u[0]) % l, (-u[1]) % m)  # noqa: E731
    FX = [(di, dj) for k, di, dj in X_NEIGH.values() if k == "F"]
    OX = [(di, dj) for k, di, dj in X_NEIGH.values() if k == "O"]
    FZ = [(di, dj) for k, di, dj in Z_NEIGH.values() if k == "F"]
    OZ = [(di, dj) for k, di, dj in Z_NEIGH.values() if k == "O"]
    sols = []
    for e1, e2 in itertools.product(G, G):
        def phi(v, e1=e1, e2=e2):
            return ((v[0] * e1[0] + v[1] * e2[0]) % l, (v[0] * e1[1] + v[1] * e2[1]) % m)
        if len({phi((i, j)) for i in range(NI) for j in range(NJ)}) != l * m:
            continue
        for filled_is_L in (True, False):
            SF, SO = (Aset, Bset) if filled_is_L else (Bset, Aset)
            nA, nB = {neg(a) for a in Aset}, {neg(b) for b in Bset}
            WF, WO = (nB, nA) if filled_is_L else (nA, nB)
            for sF in G:
                if {add(phi(f), sF) for f in FX} != SF:
                    continue
                for sO in G:
                    if {add(phi(o), sO) for o in OX} != SO:
                        continue
                    for sZ in G:
                        if ({add(add(phi(f), sF), neg(sZ)) for f in FZ} == WF and
                                {add(add(phi(o), sO), neg(sZ)) for o in OZ} == WO):
                            sols.append({"e1": e1, "e2": e2, "filled_is_L": filled_is_L, "sF": sF, "sO": sO,
                                         "sZ": sZ, "phi": phi})
    return sols


def strikis_fig12(code: BBCode, iso_index: int = 0) -> tuple[Schedule, dict]:
    """Depth-8 cyclic schedule of Fig. 12 on the project's BB qubit layout (X 0..71, L, R, Z 216..287)."""
    sols = lattice_to_bb(code)
    iso = sols[iso_index]
    phi, m = iso["phi"], code.m
    lay = bb_layout(code)
    idx = lambda ab: ab[0] * m + ab[1]  # noqa: E731
    add = lambda u, v: ((u[0] + v[0]) % code.l, (u[1] + v[1]) % code.m)  # noqa: E731
    blockF, blockO = (lay["L"], lay["R"]) if iso["filled_is_L"] else (lay["R"], lay["L"])

    def data_qubit(kind, i, j):
        v = phi((i % NI, j % NJ))
        return blockF[idx(add(v, iso["sF"]))] if kind == "F" else blockO[idx(add(v, iso["sO"]))]

    layers = [Layer() for _ in range(8)]
    meta = {"check_colour": {}, "iso": {k: v for k, v in iso.items() if k != "phi"}, "num_isomorphisms": len(sols)}
    for i, j in itertools.product(range(NI), range(NJ)):
        col = colour(i, j)
        # X check
        qx = lay["X"][idx(phi((i, j)))]
        fx = FIG12["X"][col]
        layers[fx["prep"] - 1].prep_x.append(qx)
        layers[fx["meas"] - 1].meas_x.append(qx)
        for d, (kind, di, dj) in X_NEIGH.items():
            layers[fx[d] - 1].cnots.append((qx, data_qubit(kind, i + di, j + dj)))
        # Z check
        qz = lay["Z"][idx(add(phi((i, j)), iso["sZ"]))]
        fz = FIG12["Z"][col]
        layers[fz["prep"] - 1].prep_z.append(qz)
        layers[fz["meas"] - 1].meas_z.append(qz)
        for d, (kind, di, dj) in Z_NEIGH.items():
            layers[fz[d] - 1].cnots.append((data_qubit(kind, i + di, j + dj), qz))
        meta["check_colour"][qx] = col
        meta["check_colour"][qz] = col
    for L in layers:
        L.cnots.sort(); L.prep_x.sort(); L.prep_z.sort(); L.meas_x.sort(); L.meas_z.sort()
    sched = Schedule(name="strikis_fig12", num_qubits=4 * code.n2, data=lay["L"] + lay["R"],
                     x_checks=lay["X"], z_checks=lay["Z"], layers=layers)
    return sched, meta


# ---------------------------------------------------------------- shared with E-002 (identical settings)
from baselines.gross import DECODER_KW, parse_poly, dump, clopper_pearson, per_round  # noqa: E402


def load(cfg_path):
    cfg = yaml.safe_load(open(cfg_path))
    cc = cfg["code"]
    code = BBCode(cc["l"], cc["m"], parse_poly(cc["A"]), parse_poly(cc["B"]))
    sched, meta = strikis_fig12(code)
    out = RESULTS / cfg["id"]
    out.mkdir(parents=True, exist_ok=True)
    return cfg, code, sched, meta, out


def circuits(code, sched, rounds, basis, p, detectors="basis"):
    L = code.logical_z() if basis == "Z" else code.logical_x()
    return pipelined_memory_circuit(sched, code.HX, code.HZ, L, rounds, basis, p, detectors)


def _dem_lines(c):
    return sorted(str(x) for x in c.detector_error_model().flattened())


def interleaving_report(sched: Schedule, rounds: int) -> dict:
    """Order of X- and Z-type CNOTs on shared data qubits, per pair of check instances (X round j, Z round k).
    Strikis Sec. II.A: a circuit is non-interleaved iff, among checks that overlap, either all X CNOTs precede the
    overlapping Z CNOTs or all Z CNOTs precede the X CNOTs. Returned: counts keyed by 'k-j' (Z round minus X round)
    and direction ('Z_first' | 'X_first' | 'mixed_within_pair')."""
    U = unroll_schedule(sched, rounds)
    xset = set(sched.x_checks)
    start, D = U["start"], sched.depth
    by = {}
    for t, (a, b) in U["ops"]["cnot"]:
        chk = a if a in xset else b
        dq = b if a in xset else a
        by.setdefault((chk, (t - start[chk]) // D), {})[dq] = t
    cnt = {}
    for (x, j), dx in by.items():
        if x not in xset:
            continue
        for (z, k), dz in by.items():
            if z in xset:
                continue
            sh = set(dx) & set(dz)
            if not sh:
                continue
            o = {dz[d] < dx[d] for d in sh}
            key = f"{k - j:+d}:" + ("mixed_within_pair" if len(o) > 1 else ("Z_first" if o.pop() else "X_first"))
            cnt[key] = cnt.get(key, 0) + 1
    return dict(sorted(cnt.items()))


def stage_verify(cfg, code, sched, meta, out):
    t0 = time.process_time()
    res = {"n": code.n, "k": code.k, "num_isomorphisms_lattice_to_bb": meta["num_isomorphisms"],
           "iso_used": meta["iso"]}
    # Fig. 10 colouring is proper (checks of the same type sharing support have distinct colours)
    HX, HZ = code.HX, code.HZ
    col = meta["check_colour"]
    for H, checks, name in ((HX, sched.x_checks, "X"), (HZ, sched.z_checks, "Z")):
        ov = (H.astype(int) @ H.T.astype(int))
        bad = [(a, b) for a in range(len(checks)) for b in range(a + 1, len(checks))
               if ov[a, b] and col[checks[a]] == col[checks[b]]]
        res[f"colouring_proper_{name}"] = not bad
        res[f"colour_counts_{name}"] = {c: sum(col[q] == c for q in checks) for c in COLOURS}
    sched.validate(HX, HZ)
    res["schedule_valid_cyclic"] = True
    res["depth_cyclic"] = sched.depth
    res["cnots_per_cycle"] = sum(len(L.cnots) for L in sched.layers)
    res["data_cnots_per_layer"] = [len(L.cnots) for L in sched.layers]
    res["data_idle_per_cycle"] = sum(len(sched.data) - len({d for pr in L.cnots for d in pr if d in set(sched.data)})
                                     for L in sched.layers)
    res["wrapped_checks"] = len(sched.wrapped_checks())
    for r in (1, 2, 3, cfg["rounds"]):
        U = unroll_schedule(sched, r)
        res.setdefault("unrolled", {})[r] = {"sigma": U["sigma"], "ticks": U["last_layer"] + 1,
                                            "last_data_cnot": U["last_data_cnot"]}
    res["interleaving_r3"] = interleaving_report(sched, 3)
    det = {}
    for basis in "ZX":
        for r in (1, 2, 3, cfg["rounds"]):
            c = circuits(code, sched, r, basis, 0.0, detectors="both")
            det[f"{basis}_r{r}"] = check_deterministic(c)
    res["noiseless_determinism"] = det
    # regression: generic pipelined generator reproduces E-002's memory_circuit on the IBM schedule
    ibm = ibm_depth8(code)
    reg = {}
    for basis in "ZX":
        L = code.logical_z() if basis == "Z" else code.logical_x()
        a = memory_circuit(ibm, HX, HZ, L, 3, basis, 0.003)
        b = pipelined_memory_circuit(ibm, HX, HZ, L, 3, basis, 0.003)
        ta = sum(1 for i in a.flattened() if i.name == "TICK")
        tb = sum(1 for i in b.flattened() if i.name == "TICK")
        reg[basis] = {"dem_equal": _dem_lines(a) == _dem_lines(b), "ticks_memory_circuit": ta, "ticks_pipelined": tb}
    res["regression_ibm_pipelined_vs_memory_circuit_r3"] = reg
    for basis in "ZX":
        c12 = circuits(code, sched, cfg["rounds"], basis, 0.003)
        res[f"dem_{basis}_r12"] = {"detectors": c12.num_detectors, "errors": c12.detector_error_model().num_errors,
                                   "ticks": sum(1 for i in c12.flattened() if i.name == "TICK")}
        if basis == "Z":
            (out / "circuit_Z_r12_p0.003.stim").write_text(str(c12))
    (out / "schedule_strikis_fig12.json").write_text(sched.to_json())
    res["cpu_seconds"] = time.process_time() - t0
    dump(out / "verify.json", res)
    print(json.dumps(res, indent=1, default=str))
    return res


def stage_l0(cfg, code, sched, out, rounds_list=(3, 12)):
    from evaluators.codes import CSSCode
    from evaluators.l0 import check_l0, L0Constraints
    css = CSSCode.from_checks(code.HX, code.HZ)
    res = {}
    for r in rounds_list:
        circ = {b: circuits(code, sched, r, b, 0.0) for b in "ZX"}
        cons = L0Constraints(data_qubits=sched.data, max_qubits=sched.num_qubits, rounds=r)
        t0 = time.time()
        rep = check_l0(circ, css, "both", cons)
        res[f"strikis_r{r}"] = {"passed": rep.passed, "wall_s": round(time.time() - t0, 1), "text": rep.to_text()}
        print(f"--- Strikis r={r} passed={rep.passed}\n{rep.to_text()}", flush=True)
        # IBM through the same generator as a control
        ibm = ibm_depth8(code)
        circ = {b: pipelined_memory_circuit(ibm, code.HX, code.HZ,
                                            code.logical_z() if b == "Z" else code.logical_x(), r, b, 0.0)
                for b in "ZX"}
        rep = check_l0(circ, css, "both", cons)
        res[f"ibm_control_r{r}"] = {"passed": rep.passed, "text": rep.to_text()}
        print(f"--- IBM control r={r} passed={rep.passed}", flush=True)
    dump(out / "l0.json", res)
    return res


def stage_distance(cfg, code, sched, out, rounds_list=(1, 2, 3), trials=2000, trials12=500, which="both"):
    """Identical to E-002 stage_distance's BP-OSD Eq.(12) search (same seed, trials, BP-OSD params),
    run on the Strikis circuit and (as same-budget control) on the IBM circuit."""
    from ldpc import BpOsdDecoder
    from stimbposd.dem_to_matrices import detector_error_model_to_check_matrices
    import scipy.sparse as sp
    path = out / "circuit_distance.json"
    res = json.loads(path.read_text()) if path.exists() else {}
    ibm = ibm_depth8(code)
    gens = {
        "strikis": lambda r, b: circuits(code, sched, r, b, 0.001),
        "ibm": lambda r, b: memory_circuit(ibm, code.HX, code.HZ,
                                           code.logical_z() if b == "Z" else code.logical_x(), r, b, 0.001),
    }
    names = ["strikis", "ibm"] if which == "both" else [which]
    for name in names:
        rng = np.random.default_rng(cfg.get("seed", 0))
        rows = res.setdefault(name, [])
        for basis in "ZX":
            for r in sorted(set(rounds_list) | {cfg["rounds"]}):
                if any(x["basis"] == basis and x["rounds"] == r for x in rows):
                    continue
                c = gens[name](r, basis)
                dem = c.detector_error_model()
                mm = detector_error_model_to_check_matrices(dem, allow_undecomposed_hyperedges=True)
                D = mm.check_matrix.tocsr().astype(np.uint8)
                Lm = mm.observables_matrix.tocsr().astype(np.uint8)
                t0 = time.process_time()
                best, hist, best_xi = None, {}, None
                ntr = trials if r <= 3 else trials12
                for _ in range(ntr):
                    a = rng.integers(0, 2, Lm.shape[0])
                    if not a.any():
                        a[rng.integers(Lm.shape[0])] = 1
                    b = rng.integers(0, 2, D.shape[0])
                    eta = ((a @ Lm) + (b @ D)) % 2
                    H = sp.vstack([D, sp.csr_matrix(eta.astype(np.uint8))]).tocsr()
                    syn = np.zeros(H.shape[0], dtype=np.uint8)
                    syn[-1] = 1
                    dec = BpOsdDecoder(H, error_rate=0.01, max_iter=100, bp_method="minimum_sum",
                                       osd_method="osd_cs", osd_order=10)
                    xi = dec.decode(syn)
                    w = int(xi.sum())
                    assert not ((D @ xi) % 2).any() and ((Lm @ xi) % 2).any()
                    hist[w] = hist.get(w, 0) + 1
                    if best is None or w < best:
                        best, best_xi = w, np.nonzero(xi)[0].tolist()
                row = {"basis": basis, "rounds": r, "trials": ntr, "min_weight": best,
                       "hist": {int(k): v for k, v in sorted(hist.items())},
                       "min_columns": best_xi, "cpu_s": round(time.process_time() - t0, 1)}
                rows.append(row)
                print(name, {k: v for k, v in row.items() if k != "min_columns"}, flush=True)
                dump(path, res)
    return res


def stage_distance_extra(cfg, code, sched, out, witness_trials=6000, witness_seed=12345):
    """(a) stim search_for_undetectable_logical_errors with E-002's truncations; (b) E-002's targeted
    BP-OSD witness search (`circuit_distance.bposd_witness`, weight <= 10, 6000 trials, seed 12345) at 3 rounds,
    both bases. Any witness found is re-verified by probability-1 Pauli injection (`inject_witness`)."""
    from baselines.circuit_distance import bposd_witness
    path = out / "circuit_distance_extra.json"
    res = json.loads(path.read_text()) if path.exists() else {"stim_search": [], "witness": []}
    for basis in "ZX":
        for r in (1, 2, 3):
            c = circuits(code, sched, r, basis, 0.001)
            for deg, size in ((3, 4), (4, 4)):
                if any(x["basis"] == basis and x["rounds"] == r and x["max_degree"] == deg for x in res["stim_search"]):
                    continue
                t0 = time.process_time()
                try:
                    errs = c.search_for_undetectable_logical_errors(
                        dont_explore_detection_event_sets_with_size_above=size,
                        dont_explore_edges_with_degree_above=deg,
                        dont_explore_edges_increasing_symptom_degree=False, canonicalize_circuit_errors=True)
                    w = len(errs)
                except ValueError:
                    w = None
                row = {"basis": basis, "rounds": r, "max_degree": deg, "max_event_set": size, "weight_found": w,
                       "cpu_s": round(time.process_time() - t0, 1)}
                res["stim_search"].append(row)
                print(row, flush=True)
                dump(path, res)
    for basis in "XZ":
        if any(x["basis"] == basis for x in res["witness"]):
            continue
        c = circuits(code, sched, 3, basis, 0.001)
        t0 = time.process_time()
        w = bposd_witness(c, 10, witness_trials, witness_seed)
        row = {"basis": basis, "rounds": 3, "target_weight": 10, "max_trials": witness_trials, "seed": witness_seed,
               "result": w, "cpu_s": round(time.process_time() - t0, 1)}
        if w is not None:
            row["injection"] = inject_witness(code, sched, 3, basis, w["columns"])
        res["witness"].append(row)
        print({k: v for k, v in row.items() if k != "result"}, (w or {}).get("weight"), flush=True)
        dump(path, res)
    return res


def inject_witness(code, sched, rounds, basis, columns, gen=None):
    """Insert one representative circuit fault per DEM column as probability-1 Pauli errors into the noiseless
    circuit (just after the noisy layer, before its TICK) and sample: expect 0 detectors fired and >=1 observable
    flipped, deterministically."""
    import collections
    import stim
    gen = gen or circuits
    noisy = gen(code, sched, rounds, basis, 0.001)
    dem = noisy.detector_error_model()
    flat = [inst for inst in dem.flattened() if inst.type == "error"]
    sub = stim.DetectorErrorModel()
    for i in columns:
        sub.append(flat[i])
    expl = noisy.explain_detector_error_model_errors(dem_filter=sub, reduce_to_one_representative_error=True)
    by_tick = collections.defaultdict(list)
    meas_flips = []
    desc = []
    for e in expl:
        loc = e.circuit_error_locations[0]
        desc.append(str(loc)[:300])
        if loc.flipped_measurement is not None and loc.flipped_measurement.record_index >= 0 and not loc.flipped_pauli_product:
            meas_flips.append(loc.flipped_measurement.record_index)
        for t in loc.flipped_pauli_product:
            by_tick[loc.tick_offset].append((t.gate_target.pauli_type, t.gate_target.value))
    base = gen(code, sched, rounds, basis, 0.0)
    newc = stim.Circuit()
    seg, mi = 0, 0
    for inst in base.flattened():
        if inst.name == "TICK":
            for P, q in by_tick.get(seg, []):
                newc.append(P + "_ERROR", [q], 1.0)
            seg += 1
        if inst.name in ("M", "MX") and meas_flips:
            tg = inst.targets_copy()
            flip = [t.value for k, t in enumerate(tg) if mi + k in meas_flips]
            if flip:   # measurement-result error: equivalent Pauli just before the measurement
                newc.append("X_ERROR" if inst.name == "M" else "Z_ERROR", flip, 1.0)
            mi += len(tg)
        newc.append(inst)
    det, obs = newc.compile_detector_sampler().sample(4, separate_observables=True)
    return {"faults": desc, "detectors_fired": int(det[0].sum()), "observables_flipped": np.flatnonzero(obs[0]).tolist(),
            "deterministic": bool((det == det[0]).all() and (obs == obs[0]).all()),
            "n_pauli_faults": sum(len(v) for v in by_tick.values()), "n_measurement_faults": len(meas_flips)}


def _sinter_tasks(code, sched, basis, p, rounds):
    import sinter
    c = circuits(code, sched, rounds, basis, p)
    return [sinter.Task(circuit=c, json_metadata={"basis": basis, "p": p, "rounds": rounds, "schedule": sched.name})]


def stage_sample(cfg, code, sched, out, budget_cpu_s, only_p=None, max_shots=None, max_errors=None, bases="ZX"):
    import sinter
    from stimbposd import SinterDecoder_BPOSD
    nw = min(4, cfg["budget"]["num_workers"])
    ps = sorted(only_p or cfg["noise"]["p"], reverse=True)
    rounds = cfg["rounds"]
    csv = out / "stats.csv"
    logp = out / "sample_log.json"
    log = json.loads(logp.read_text()) if logp.exists() else []
    used = sum(r.get("decoder_seconds_this_call", 0) for r in log)
    for p in ps:
        for basis in bases:
            if used > budget_cpu_s:
                print(f"BUDGET STOP before basis={basis} p={p}: used {used:.0f}s", flush=True)
                log.append({"basis": basis, "p": p, "skipped": "budget"})
                continue
            tasks = _sinter_tasks(code, sched, basis, p, rounds)
            prev = [x for x in sinter.read_stats_from_csv_files(str(csv))
                    if x.json_metadata == tasks[0].json_metadata] if csv.exists() else []
            prev_s = sum(x.seconds for x in prev)
            st = sinter.collect(num_workers=nw, tasks=tasks, decoders=["bposd"],
                                custom_decoders={"bposd": SinterDecoder_BPOSD(**DECODER_KW)},
                                max_shots=int(max_shots or cfg.get("max_shots", 50_000)),
                                max_errors=int(max_errors or cfg.get("max_errors", 200)),
                                save_resume_filepath=str(csv))
            s = next(x for x in st if x.json_metadata == tasks[0].json_metadata and x.decoder == "bposd")
            used += s.seconds - prev_s
            row = {"basis": basis, "p": p, "shots": s.shots, "errors": s.errors,
                   "decoder_seconds_total": round(s.seconds, 1),
                   "decoder_seconds_this_call": round(s.seconds - prev_s, 1),
                   "cumulative_decoder_seconds": round(used, 1)}
            log.append(row)
            print(row, flush=True)
            dump(logp, log)
    return log


def stage_analyze(cfg, code, sched, out):
    import sinter
    stats = sinter.read_stats_from_csv_files(str(out / "stats.csv"))
    agg = {}
    for s in stats:
        key = (s.json_metadata["basis"], s.json_metadata["p"])
        agg[key] = s if key not in agg else agg[key] + s
    e002 = json.loads((RESULTS / "E-002-gross-baseline" / "summary.json").read_text())
    ibm = {r["p"]: r for r in e002["points"]}
    N = cfg["rounds"]
    rows = []
    comb = lambda a, b: 1 - (1 - a) * (1 - b)  # noqa: E731
    for p in sorted(cfg["noise"]["p"]):
        r = {"p": p}
        Ps = {}
        for basis in "ZX":
            s = agg.get((basis, p))
            if s is None:
                continue
            P = s.errors / s.shots
            lo, hi = clopper_pearson(s.errors, s.shots)
            Ps[basis] = (P, lo, hi)
            r[basis] = {"shots": s.shots, "errors": s.errors, "PL": P, "PL_ci95": [lo, hi],
                        "pL_per_round": per_round(P, N), "pL_ci95": [per_round(lo, N), per_round(hi, N)],
                        "decoder_seconds": round(s.seconds, 1)}
            if p in ibm and basis in ibm[p]:
                r[basis]["ratio_to_ibm_E002"] = per_round(P, N) / ibm[p][basis]["pL_per_round"]
        if len(Ps) == 2:
            Pc = comb(Ps["Z"][0], Ps["X"][0])
            r["combined"] = {"PL": Pc, "pL_per_round": per_round(Pc, N),
                             "pL_ci95_conservative": [per_round(comb(Ps["Z"][1], Ps["X"][1]), N),
                                                      per_round(comb(Ps["Z"][2], Ps["X"][2]), N)]}
            if p in ibm and "combined" in ibm[p]:
                ib = ibm[p]["combined"]
                r["combined"]["ibm_E002_pL_per_round"] = ib["pL_per_round"]
                r["combined"]["ibm_E002_ci95_conservative"] = ib["pL_ci95_conservative"]
                r["combined"]["ratio_to_ibm_E002"] = per_round(Pc, N) / ib["pL_per_round"]
                # conservative ratio range from the two conservative intervals
                r["combined"]["ratio_range_conservative"] = [
                    r["combined"]["pL_ci95_conservative"][0] / ib["pL_ci95_conservative"][1],
                    r["combined"]["pL_ci95_conservative"][1] / ib["pL_ci95_conservative"][0]]
        rows.append(r)
    dump(out / "summary.json", {"rounds": N, "decoder": DECODER_KW, "schedule": sched.name, "points": rows})
    for r in rows:
        print(json.dumps(r, default=float))
    _plot(rows, ibm, out / "pL_vs_p.png")
    return rows


def _plot(rows, ibm, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(5, 4))
    for src, lab, mk in ((rows, "Strikis Fig.12 (E-003)", "o"),
                         ([ibm[p] for p in sorted(ibm)], "IBM depth-8 (E-002)", "s")):
        xs, ys, lo, hi = [], [], [], []
        for r in src:
            if "combined" not in r:
                continue
            d = r["combined"]; ci = d["pL_ci95_conservative"]
            xs.append(r["p"]); ys.append(d["pL_per_round"]); lo.append(d["pL_per_round"] - ci[0]); hi.append(ci[1] - d["pL_per_round"])
        ax.errorbar(xs, ys, yerr=[lo, hi], fmt=mk, ms=4, capsize=2, label=lab)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("physical error rate p"); ax.set_ylabel("combined X+Z logical error rate per cycle")
    ax.set_title("[[144,12,12]], 12 cycles, BP-OSD, project-internal noise")
    ax.legend(fontsize=7); fig.tight_layout(); fig.savefig(path, dpi=130)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--stage", default="all", choices=["all", "verify", "l0", "distance", "distance_extra", "sample", "analyze"])
    ap.add_argument("--which", default="both", choices=["both", "strikis", "ibm"], help="distance stage")
    ap.add_argument("--p", type=float, nargs="*", default=None)
    ap.add_argument("--max-shots", type=int, default=None)
    ap.add_argument("--max-errors", type=int, default=None, help="override yaml max_errors (budget)")
    ap.add_argument("--bases", default="ZX")
    ap.add_argument("--sample-budget-cpu-s", type=float, default=None)
    a = ap.parse_args()
    cfg, code, sched, meta, out = load(a.config)
    budget = a.sample_budget_cpu_s or 0.7 * cfg["budget"]["cpu_hours"] * 3600
    stages = ["verify", "l0", "distance", "distance_extra", "sample", "analyze"] if a.stage == "all" else [a.stage]
    for st in stages:
        print(f"=== stage {st} ===", flush=True)
        if st == "verify":
            stage_verify(cfg, code, sched, meta, out)
        elif st == "l0":
            stage_l0(cfg, code, sched, out)
        elif st == "distance":
            stage_distance(cfg, code, sched, out, which=a.which)
        elif st == "distance_extra":
            stage_distance_extra(cfg, code, sched, out)
        elif st == "sample":
            stage_sample(cfg, code, sched, out, budget, a.p, a.max_shots, a.max_errors, a.bases)
        elif st == "analyze":
            stage_analyze(cfg, code, sched, out)


if __name__ == "__main__":
    main()
