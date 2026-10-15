"""Audit rev-g (1b): own Pauli-frame propagation (no DEM, no stim error analysis) of every SD6 fault location.

Backward pass over the noiseless template circuit: reach_t[q] = set of data qubits whose final memory-basis readout
is flipped by a frame-type Pauli (X for Z basis, Z for X basis) on q right after layer t's operations.
Rules: CX(c,t): X: before[c]=after[c]^after[t]; Z: before[t]=after[t]^after[c]. Reset of q in layer t erases.
SD6 locations (as evaluators/noise.py): flip after reset (only R gives X / only RX gives Z), DEPOLARIZE2 after each
CX (frame components on either or both qubits), flip before measurement, DEPOLARIZE1 on each untouched qubit per
layer, data flip after data reset and before final readout.  Each image s is checked to be: empty, a single data
qubit, or a suffix {q_k..q_6} (k=1..6) of one hook-spreading check's order; also tallies which location produces what.
    PYTHONPATH=.:tests uv run python research/audits/2026-10-14-revg-scripts/g2_propagate.py
"""
import json, sys
from collections import Counter
sys.path.insert(0, "tests")
from evaluators.tasks import build_code, get_task
from evaluators.candidate import parse_schedule, build_circuits, layout_for
from schedule_helpers import from_baseline
from baselines.bb_code import gross_code
from baselines.strikis import strikis_fig12

code, _ = build_code(get_task("gross-dcirc"), None)
lay = layout_for(code)
n = 144
specA = parse_schedule(json.load(open("search/experiments/e024a/cs_P18_H24.json")))
specF = from_baseline(strikis_fig12(gross_code())[0])


def run(spec, R, basis):
    c = build_circuits(spec.canonical(), code, R)[basis].flattened()
    layers, cur = [], []
    for op in c:
        if op.name == "TICK":
            layers.append(cur); cur = []
        elif op.name in ("R", "RX", "M", "MX", "CX"):
            cur.append((op.name, [t.value for t in op.targets_copy()]))
    layers.append(cur)                                   # final readout layer
    nq = c.num_qubits
    hook_anc = set(lay.x_anc if basis == "Z" else lay.z_anc)
    other_anc = set(lay.z_anc if basis == "Z" else lay.x_anc)
    # hook orders in time order, from the circuit itself (ancilla -> data targets/controls by time)
    seq = {a: [] for a in hook_anc}; inst_of = {}
    for li, L in enumerate(layers):
        for name, tg in L:
            if name == "CX":
                for a, b in zip(tg[::2], tg[1::2]):
                    if a in hook_anc: seq[a].append((li, b))
                    if b in hook_anc: seq[b].append((li, a))
    suffixes = set()
    for a, lst in seq.items():
        for j in range(0, len(lst), 6):
            o = [q for _, q in lst[j:j + 6]]
            assert len(o) == 6
            for k in range(6):
                suffixes.add(frozenset(o[k:]))
    erase_reset = "R" if basis == "Z" else "RX"       # resets whose flip is a frame-type Pauli
    frame_meas = "M" if basis == "Z" else "MX"
    reach = [frozenset() for _ in range(nq)]
    for q in range(n):
        reach[q] = frozenset({q})
    tally = Counter(); bad = []
    def chk(s, label):
        if not s: cat = "empty"
        elif len(s) == 1: cat = "single"
        elif s in suffixes: cat = f"suffix{len(s)}"
        else:
            cat = "BAD"; bad.append((label, sorted(s)))
        tally[(label, cat)] += 1
    for li in range(len(layers) - 1, -1, -1):
        L = layers[li]
        after = list(reach)
        touched = set()
        # faults acting after this layer's ops / before its measurements (frame unchanged by measurement)
        for name, tg in L:
            touched.update(tg)
            if name in ("R", "RX"):
                kind = "data" if tg[0] < n else ("hookanc" if tg[0] in hook_anc else "otheranc")
                for q in tg:
                    chk(after[q] if name == erase_reset else frozenset(), f"reset_flip_{'data' if q < n else ('hook' if q in hook_anc else 'other')}")
            elif name in ("M", "MX"):
                for q in tg:
                    chk(after[q] if name == frame_meas else frozenset(), f"meas_flip_{'data' if q < n else ('hook' if q in hook_anc else 'other')}")
            elif name == "CX":
                for a, b in zip(tg[::2], tg[1::2]):
                    typ = "hookCX" if (a in hook_anc or b in hook_anc) else "otherCX"
                    chk(after[a], typ + "_ctrl"); chk(after[b], typ + "_tgt"); chk(after[a] ^ after[b], typ + "_both")
        if li < len(layers) - 1:   # idle noise (final readout layer: data all measured)
            for q in range(nq):
                if q not in touched:
                    chk(after[q], f"idle_{'data' if q < n else ('hook' if q in hook_anc else 'other')}")
        # backward through ops
        for name, tg in L:
            if name in ("R", "RX"):
                for q in tg: reach[q] = frozenset()
            elif name == "CX":
                for a, b in zip(tg[::2], tg[1::2]):
                    if basis == "Z": reach[a] = reach[a] ^ reach[b]
                    else: reach[b] = reach[b] ^ reach[a]
    return {f"{k[0]}:{k[1]}": v for k, v in sorted(tally.items())}, bad


out = {}
for name, spec in (("circuitA", specA), ("fig12", specF)):
    for R in (1, 2, 3):
        for basis in "ZX":
            t, bad = run(spec, R, basis)
            out[f"{name}_R{R}_{basis}"] = dict(tally=t, bad=len(bad), examples=bad[:5])
            print(name, R, basis, "BAD", len(bad), flush=True)
            if R == 2: print(json.dumps(t))
json.dump(out, open("research/audits/2026-10-14-revg-scripts/g2_propagate.json", "w"), indent=1)
