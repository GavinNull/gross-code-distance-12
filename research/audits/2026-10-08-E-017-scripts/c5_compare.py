"""C5: compare with the experimenter's construction (run, not modified):
 (1) gate-by-gate: search.experiments.e017.morph memory circuits vs mine (all homs, both orders, both bases,
     both first rounds);
 (2) their DFS instance file == their builder output (regenerated);
 (3) their single-round instance vs mine: fault-by-fault correspondence through stim's
     explain_detector_error_model_errors on their noisy-window circuit; rank conditions.
usage: c5_compare.py <basis>
"""
import json, pickle, sys, os
sys.path.insert(0, "/Users/ephemeral/Desktop/qec-ai-search")
import numpy as np, stim
from common import memory, N, rank
from search.experiments.e017.morph import TWO_GROSS, Morph
from search.experiments.e017 import dfs_inst
OUT = "/Users/ephemeral/Desktop/qec-ai-search/results/E-017-audit"
basis = sys.argv[1]
hom = sys.argv[2] if len(sys.argv) > 2 else "x"
DO_GATES = hom == "x"
res = {}


def layers_of_stim(c):
    out = [dict()]
    for ins in c.flattened():
        if ins.name == "TICK":
            out.append(dict()); continue
        if ins.name in ("DETECTOR", "OBSERVABLE_INCLUDE", "QUBIT_COORDS", "SHIFT_COORDS"):
            continue
        ts = [t.value for t in ins.targets_copy()]
        if ins.name == "CX":
            v = frozenset(zip(ts[0::2], ts[1::2]))
        else:
            v = frozenset(ts)
        out[-1][ins.name] = out[-1].get(ins.name, frozenset()) | v
    return [d for d in out]


cmp = {}
for hom_ in (("x", "y", "xy") if DO_GATES else ()):
    for order, sw in (("repo", False), ("paper", True)):
        for b in ("Z", "X"):
            for fj in (0, 1):
                Mo = Morph(TWO_GROSS, hom_, swap23=sw)
                theirs = layers_of_stim(Mo.memory_circuit(b, 4, first_j=fj))
                C, _, _ = memory(hom_, order, 4, b, first_c=fj)
                mine = layers_of_stim(C.stim())
                cmp[f"{hom_}/{order}/{b}/fj{fj}"] = (len(theirs) == len(mine) and all(x == y for x, y in zip(theirs, mine)))
res["gate_by_gate_equal"] = cmp
print(cmp)

# (2) regenerate their instance and compare with their file
inst = dfs_inst.build(hom, False, basis, 1, 0)
tmp = f"{OUT}/regen_inst_{hom}_{basis}.txt"
dfs_inst.write(inst, tmp)
theirfile = f"/Users/ephemeral/Desktop/qec-ai-search/results/E-017-gross-morphing-scoping/dfs/inst_{hom}_{basis}.txt"
res["their_file_reproduced"] = open(tmp).read() == open(theirfile).read()
print("file reproduced", res["their_file_reproduced"])

# (3) fault correspondence. Their sandwich: 3 rounds, first_j=1, noisy round 2 (c=0), ticks 8..15.
c = inst["circuit"]
keep, cols = inst["keep"], inst["cols"]
He, Le = inst["He"], inst["Le"]
rows = inst["rows"]
dpos = {keep[r]: i for i, r in enumerate(rows)}
want = 1 if basis == "Z" else 0
coords = c.get_detector_coordinates()
P = pickle.load(open(f"{OUT}/c2_{hom}_repo_{basis}_T4.pkl", "rb"))
faults, sigs, blocks = P["faults"], P["sigs"], P["blocks"]
Cm, _, _ = memory(hom, "repo", 4, basis)
Mlayers = set(i for i, (ops, tg) in enumerate(Cm.layers) if tg[1] == "M")
def canon(comp):
    return tuple(sorted(((pt + 1) if (q < N and pt in Mlayers) else pt, q) for pt, q in comp))
comp2sig = {}
for ft, sg in zip(faults, sigs):
    comp2sig.setdefault(canon(ft[5]), sg)
ROUND = 3   # my round 3 (c=0) of the T=4 circuit; layers 16..23
off = 16 - 8
dem = c.detector_error_model(decompose_errors=False)
ex = c.explain_detector_error_model_errors(reduce_to_one_representative_error=False)
nloc = 0
A, B = [], []
mismatch_zero = 0
proj_letters = ("X", "Y") if basis == "Z" else ("Z", "Y")
their_comps = set()
for e in ex:
    ds = [t.dem_target.val for t in e.dem_error_terms if t.dem_target.is_relative_detector_id()]
    ob = [t.dem_target.val for t in e.dem_error_terms if t.dem_target.is_logical_observable_id()]
    hv = np.zeros(He.shape[0], np.uint8)
    for d in ds:
        if int(coords[d][2]) == want:
            hv[dpos[d]] ^= 1
    lv = np.zeros(Le.shape[0], np.uint8)
    for o in ob:
        lv[o] ^= 1
    for loc in e.circuit_error_locations:
        nloc += 1
        tick = loc.tick_offset
        name = loc.instruction_targets.gate
        comp = []
        for t in loc.flipped_pauli_product:
            q = t.gate_target.value
            pc = "X" if t.gate_target.is_x_target else ("Y" if t.gate_target.is_y_target else "Z")
            if pc in proj_letters:
                pre = (name in ("X_ERROR", "Z_ERROR") and (tick % 8) == 7)   # pre-measurement flip
                comp.append((tick + off + (0 if pre else 1), q))
        comp = canon(comp)
        their_comps.add(comp)
        if not comp:
            if hv.any() or lv.any():
                mismatch_zero += 1
            continue
        sg = comp2sig[comp]
        mine = np.concatenate([sg[0][ROUND], sg[0][ROUND + 1], sg[1]])
        A.append(np.concatenate([hv, lv])); B.append(mine)
A = np.array(A).T; B = np.array(B).T
nh_a, nh_b = He.shape[0], len(blocks[ROUND]) + len(blocks[ROUND + 1])
rA, rB, rAB = rank(A[:nh_a]), rank(B[:nh_b]), rank(np.vstack([A[:nh_a], B[:nh_b]]))
sA, sB, sAB = rank(A), rank(B), rank(np.vstack([A, B]))
my_comps = set(canon(ft[5]) for ft, sg in zip(faults, sigs) if ft[0] == ROUND and ft[5]
               and (any(np.any(sg[0][t]) for t in sg[0]) or np.any(sg[1])))
res["explain"] = dict(dem_terms=len(ex), locations=nloc, zero_projection_but_column=mismatch_zero,
                      rankH=(rA, rB, rAB), rankHL=(sA, sB, sAB),
                      equivalent=bool(rA == rB == rAB and sA == sB == sAB),
                      my_nonzero_comps_covered=bool(my_comps <= their_comps), n_my=len(my_comps))
# every one of their columns hit by some location?
print(res["explain"])
json.dump(res, open(f"{OUT}/c5_{hom}_{basis}.json", "w"), indent=1, default=str)
