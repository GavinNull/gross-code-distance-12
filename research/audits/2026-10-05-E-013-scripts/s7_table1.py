"""Computational check of Prop. 3's key step (Strikis Table I) on the evaluator's actual noisy memory circuits:
every single fault mechanism, propagated (own Pauli-frame propagation: CX conjugation, resets clear) to the end,
has a data X-part (resp. Z-part) whose [H;L] vector is 0 or equal to one column of the X-type (resp. Z-type)
extended code.  Then any undetected logical fault set of size w gives an ext logical of weight <= w, i.e.
d_circ >= d_ext.  Also reports whether the ext column set is 'tight' (every column used by some single fault)."""
import sys, json
sys.path.insert(0, "research/audits/2026-10-05-E-013-scripts")
import numpy as np, stim
from evaluators.tasks import get_task, build_code
from evaluators.candidate import parse_schedule, build_circuits
from evaluators.noise import add_noise
from extcode import ext

R = int(sys.argv[1]) if len(sys.argv) > 1 else 3
code, _ = build_code(get_task("bb108-dcirc"), None)
spec = parse_schedule(json.load(open("results/E-013-audit/spec_auditor.json"))).canonical()
n = code.n
out = {}
for basis in "ZX":
    circ = add_noise(build_circuits(spec, code, R)[basis], "sd6", 1e-3).flattened()
    nq = circ.num_qubits
    ops = []
    for inst in circ:
        if inst.name == "TICK": continue
        t = [q.value for q in inst.targets_copy() if q.is_qubit_target]
        ops.append((inst.name, t))
    NOISE = {"DEPOLARIZE1", "DEPOLARIZE2", "X_ERROR", "Z_ERROR", "Y_ERROR"}
    # precompute
    def propagate(start, qubit, which):
        x = np.zeros(nq, bool); z = np.zeros(nq, bool)
        (x if which == "X" else z)[qubit] = True
        for name, t in ops[start:]:
            if name in ("CX", "CNOT"):
                c = np.array(t[0::2]); g = np.array(t[1::2])
                x[g] ^= x[c]; z[c] ^= z[g]
            elif name in ("R", "RX", "RZ"):
                x[t] = False; z[t] = False
            elif name in NOISE or name in ("M", "MX", "MZ", "DETECTOR", "OBSERVABLE_INCLUDE") or name.startswith("M"):
                pass
            else:
                raise ValueError(name)
        return x[:n].copy(), z[:n].copy()
    cols = {}
    for kind in "XZ":
        d = ext(kind)
        cols[kind] = ({d["He"][:, j].tobytes() + d["Le"][:, j].tobytes() for j in range(d["He"].shape[1])},
                      d["H"], d["L"], set())
    bad = {"X": 0, "Z": 0}; total = 0
    cache = {}
    for i, (name, t) in enumerate(ops):
        if name not in NOISE: continue
        groups = [t[k:k + 2] for k in range(0, len(t), 2)] if name == "DEPOLARIZE2" else [[q] for q in t]
        for grp in groups:
            for kind in "XZ":
                effs = []
                for q in grp:
                    key = (i, q, kind)
                    if key not in cache:
                        cache[key] = propagate(i + 1, q, kind)[0 if kind == "X" else 1]
                    effs.append(cache[key])
                combos = effs + ([effs[0] ^ effs[1]] if len(effs) == 2 else [])
                S, H, L, used = cols[kind]
                for v in combos:
                    total += 1
                    hv = (H.astype(np.int64) @ v) % 2; lv = (L.astype(np.int64) @ v) % 2
                    if not hv.any() and not lv.any(): continue
                    k = hv.astype(np.uint8).tobytes() + lv.astype(np.uint8).tobytes()
                    if k in S: used.add(k)
                    else: bad[kind] += 1
    out[basis] = dict(rounds=R, checked_fault_parts=total, not_a_column=bad,
                      ext_columns_used={k: f"{len(cols[k][3])}/{len(cols[k][0])}" for k in "XZ"})
    print(basis, out[basis], flush=True)
json.dump(out, open(f"results/E-013-audit/s7_table1_R{R}.json", "w"), indent=1)
