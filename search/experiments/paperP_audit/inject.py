"""Deterministic Pauli injection into the evaluator's noiseless memory circuit (public API only).
Faults: ("anc", typ, check_index, instance j, after_cnot_k)  -> Pauli on that ancilla after its k-th CNOT (1-based)
        ("data", q, layer)                                   -> Pauli on data qubit q at the end of `layer`
Pauli type: X for Z-basis memory, Z for X-basis memory.
Returns (set of (check_index, instance) of fired detectors, observable flips vector)."""
from collections import defaultdict
import numpy as np
import stim
from evaluators import candidate as cand


class Injector:
    def __init__(self, spec_d, code, basis, R):
        self.spec = cand.parse_schedule(spec_d); self.code = code; self.basis = basis; self.R = R
        self.U = cand.unroll(self.spec, code, R); self.lay = cand.layout_for(code)
        self.base = cand.memory_circuit(self.spec, code, basis, R)
        self.D = self.spec.period
        # detector coordinates: (i, j, type)
        self.coords = self.base.get_detector_coordinates()
        s = self.base.compile_detector_sampler().sample(4, append_observables=True)
        assert not s.any(), "noiseless circuit not deterministic"

    def anc_layer(self, typ, ci, j, k):
        checks, anc = (self.spec.x_checks, self.lay.x_anc) if typ == "X" else (self.spec.z_checks, self.lay.z_anc)
        a = anc[ci]; dm, offs = checks[ci].offsets(self.D)
        return a, self.U.start[a] + self.D * j + offs[k - 1][0], [col for _, col in offs[k:]]

    def meas_layer(self, typ, j):
        """layer of the measurement of round j of checks of type typ (all checks of a type share it here)."""
        ls = {t for t, ms in self.U.meas.items() for (q, ty, jj) in ms if ty == typ and jj == j}
        assert len(ls) == 1, ls
        return ls.pop()

    def run(self, faults):
        P = "X" if self.basis == "Z" else "Z"
        at = defaultdict(list)
        for f in faults:
            if f[0] == "anc":
                a, t, _ = self.anc_layer(*f[1:])
                at[t].append(a)
            else:
                at[f[2]].append(f[1])
        c = stim.Circuit(); t = 0
        for ins in self.base:
            if ins.name == "TICK":
                for q in sorted(at.get(t, [])):
                    c.append(f"{P}_ERROR", [q], 1.0)
                t += 1
            c.append(ins)
        det, obs = c.compile_detector_sampler().sample(1, separate_observables=True)
        fired = [tuple(int(v) for v in self.coords[i][:2]) for i in np.flatnonzero(det[0])]
        return fired, obs[0]
