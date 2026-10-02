"""Item 3: boundary-equalised ("bulk-only") variant of the per-basis memory circuits.

From the experiment's noisy circuit (E-003 generator for Strikis, E-002 memory_circuit for IBM) remove:
  * the data-qubit reset flip (X_ERROR/Z_ERROR right after the initial data R/RX),
  * the data-qubit readout flip (M(p)/MX(p) on the final data readout -> noiseless),
  * every DEPOLARIZE1 on a data qubit in a layer strictly before that qubit's first CX or strictly after its last CX
    (this is exactly where the 4 extra fill/drain layers of the pipelined circuit put extra data idling).
Everything else (all ancilla noise, all bulk data idling, all CX noise) is kept. Applied identically to both circuits.
"""
import stim

from common import code_and_scheds, memory


def layers_of(c: stim.Circuit):
    L = [[]]
    for inst in c.flattened():
        if inst.name == "TICK":
            L.append([])
        else:
            L[-1].append(inst)
    return L


def trim(c: stim.Circuit, data: list[int]) -> tuple[stim.Circuit, dict]:
    data = set(data)
    L = layers_of(c)
    first, last = {}, {}
    for t, insts in enumerate(L):
        for inst in insts:
            if inst.name == "CX":
                for tg in inst.targets_copy():
                    q = tg.value
                    if q in data:
                        first.setdefault(q, t); last[q] = t
    final_meas_layer = len(L) - 1   # final data readout + detectors live after the last TICK
    removed = {"idle": 0, "reset_flip": 0, "readout_flip": 0}
    out = stim.Circuit()
    for t, insts in enumerate(L):
        for inst in insts:
            tg = inst.targets_copy()
            if inst.name == "DEPOLARIZE1":
                keep = [x for x in tg if not (x.value in data and (t < first[x.value] or t > last[x.value]))]
                removed["idle"] += len(tg) - len(keep)
                if keep:
                    out.append(inst.name, keep, inst.gate_args_copy())
                continue
            if inst.name in ("X_ERROR", "Z_ERROR") and t == 0:
                keep = [x for x in tg if x.value not in data]
                removed["reset_flip"] += len(tg) - len(keep)
                if keep:
                    out.append(inst.name, keep, inst.gate_args_copy())
                continue
            if inst.name in ("M", "MX") and t == final_meas_layer and all(x.value in data for x in tg):
                removed["readout_flip"] += len(tg)
                out.append(inst.name, tg)
                continue
            out.append(inst)
        if t < len(L) - 1:
            out.append("TICK")
    return out, removed


if __name__ == "__main__":
    code, S = code_and_scheds()
    for name, sched in S.items():
        for b in "ZX":
            c = memory(code, sched, name, 12, b, 0.005)
            tc, rm = trim(c, sched.data)
            idle_total = sum(len(i.targets_copy()) for i in c.flattened() if i.name == "DEPOLARIZE1"
                             and all(x.value in set(sched.data) for x in i.targets_copy()))
            data_idle = sum(1 for i in c.flattened() if i.name == "DEPOLARIZE1" for x in i.targets_copy()
                            if x.value in set(sched.data))
            print(name, b, rm, "data idle locations before:", data_idle, "after:", data_idle - rm["idle"],
                  "DEM errors", tc.detector_error_model().num_errors, "dets", tc.num_detectors)
