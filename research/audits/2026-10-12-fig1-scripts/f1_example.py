"""Claim 1: the specific logical. Own DEM, own oracle, own injection, own read/deposit ticks."""
import itertools, json, sys
sys.path.insert(0, __import__("os").path.dirname(__file__))
from f_common import *

DATA = [0, 1, 6, 12, 16, 19, 74, 78, 79, 91]
HOOK = (9, 25)
out = {}
f12, p18 = fig12_spec(), p18_spec()
xo12, xo18 = xorders(f12), xorders(p18)
print("X7 order fig12", xo12[7], "p18", xo18[7])
assert sorted(xo12[7][4:]) == list(HOOK)
v = np.zeros(N, np.uint8); v[DATA + list(HOOK)] = 1
print("H-syndrome zero:", not ((HZ @ v) % 2).any(), " L image:", np.flatnonzero((LZ @ v) % 2))
keys = [key_of((q,)) for q in DATA] + [key_of(HOOK)]
assert key_of(HOOK) == key_of(tuple(xo18[7][2:])), "P18 suffix after 2nd CNOT ~ hook"

res = {}
for name, spec in (("fig12", f12), ("p18", p18)):
    c = circuit(spec)
    aug, dem, groups = my_dem(c)
    cols = [[t[0] for t in groups[k]] for k in keys]
    ok, ch = feasible(cols, want_witness=True)
    zr, xr = layer_ticks(c)
    hk = groups[keys[-1]]
    # all circuit realisations of every hook-column DEM term
    sub = stim.DetectorErrorModel()
    for _, inst in hk: sub.append(inst)
    reals = []
    for e in aug.explain_detector_error_model_errors(dem_filter=sub, reduce_to_one_representative_error=False):
        for loc in e.circuit_error_locations:
            reals.append(dict(tick=loc.tick_offset, gate=loc.instruction_targets.gate,
                              targets=[(t.gate_target.value) for t in loc.instruction_targets.targets_in_range],
                              paulis=[(p.gate_target.pauli_type, p.gate_target.value) for p in loc.flipped_pauli_product],
                              meas=None if loc.flipped_measurement is None else loc.flipped_measurement.measurement_record_index))
    print(f"\n== {name}: lift feasible={ok}; #hook-column DEM terms={len(hk)}; realisations:")
    for r_ in reals: print("  ", r_)
    print("  hook CNOT layers (X7):", {q: xr[(7, q)] for q in (xo12 if name == 'fig12' else xo18)[7]})
    det_coords = dem.get_detector_coordinates()
    res[name] = dict(feasible=ok, n_hook_terms=len(hk), hook_realisations=reals, groups=groups, cols=cols, c=c,
                     aug=aug, zr=zr, xr=xr, coords=det_coords, choice=ch)

# --- Fig. 12: inject the stated witness by hand (qubit, layer) and also the DP witness
STATED = {74: 4, 0: 6, 1: 6, 78: 3, 79: 4, 6: 6, 16: 6, 12: 7, 91: 3, 19: 6}
HOOK_FAULT = (144 + 7, 9)


def inject(c, faults):
    """faults: list of (qubit, layer): X inserted right after the CX instruction of that layer (noiseless circuit)."""
    noiseless = c.without_noise()
    new, t, done = stim.Circuit(), 0, set()
    for op in noiseless.flattened():
        new.append(op)
        if op.name == "TICK": t += 1
        if op.name == "CX":
            tg = {x.value for x in op.targets_copy()}
            for q, L in faults:
                if L == t and q in tg:
                    new.append("X_ERROR", [q], 1.0); done.add((q, L))
    assert len(done) == len(faults), (done, faults)
    d, o = new.compile_detector_sampler().sample(1, separate_observables=True)
    return int(d.sum()), list(np.flatnonzero(o[0]))


c12 = res["fig12"]["c"]
faults = [(q, L) for q, L in STATED.items()] + [HOOK_FAULT]
nd, obs = inject(c12, faults)
print("\nFig12 stated witness injection: detectors fired =", nd, " observables flipped =", obs)
# robustness: is it the 4th CNOT? (CX layer 9 of X7 is to qubit 8 = 4th in order)
print("X7 CNOT to 8 at layer", res["fig12"]["xr"][(7, 8)])
# P18: try every single-X ancilla-7 fault position + all 4^10-ish data placements is the DP's job; report DP result
print("P18 lift feasible (own DP):", res["p18"]["feasible"])

# --- conflicting set and reads
c18 = res["p18"]
core_dets = [72 + r for r in (6, 12, 15, 18)]
print("coords of core:", [c18["coords"][d] for d in core_dets])
inf = not feasible(c18["cols"], set(core_dets))[0]
subs = [feasible(c18["cols"], set(s))[0] for s in itertools.combinations(core_dets, 3)]
print("core {Z6,Z12,Z15,Z18 final} infeasible:", inf, " all 3-subsets feasible:", all(subs))
# also: is any set of <=3 detectors infeasible at all? (minimum)
mn = minimum_iis(c18["cols"])
print("minimum IIS (own IHS):", mn, [c18["coords"][d] for d in mn])
allds = sorted(set().union(*[d for col in c18["cols"] for d in col]))
print("ascending-order deletion IIS:", iis_deletion(c18["cols"], allds))
for nm in ("fig12", "p18"):
    zr = res[nm]["zr"]
    print(f"{nm} reads:", {r: {q: zr[(r, q)] for q in sorted(set(DATA) | set(HOOK) | set(xo18[7])) if HZ[r, q]} for r in (6, 12, 15, 18)})
# which logical errors each core check sees
for r in (6, 12, 15, 18):
    print(f"Z{r} support ∩ data:", [q for q in DATA if HZ[r, q]], " ∩ fig12 hook:", [q for q in HOOK if HZ[r, q]],
          " ∩ p18 spread:", [q for q in xo18[7][2:] if HZ[r, q]])
# signatures of each column on core final dets, p18
for k, q in zip(keys, DATA + ["hook"]):
    sig = collections.Counter(tuple(int(d in t[0]) for d in core_dets) for t in c18["groups"][k])
    print("p18 sig", q, dict(sig))
