"""A1: code identity, legality, determinism, translation invariance, interleaving; own encoder vs evaluator DEM.
Usage: a1_circuit.py SPEC [R ...]   (default R = 1 2 3)"""
import sys, json, collections
sys.path.insert(0, "research/audits/2026-10-22-E-032-scripts")
import numpy as np, stim
from alib32 import *

path = sys.argv[1]
Rs = [int(x) for x in sys.argv[2:]] or [1, 2, 3]
spec = load_spec(path)
HX, HZ, LX, LZ = code()
D = spec["period"]
out = {"spec": path, "period": D}

# ---- code identity vs evaluator (public entry)
from evaluators.tasks import build_code, get_task
ec, _ = build_code(get_task("gross-dcirc"), None)
out["HX_equal"] = bool((np.asarray(ec.HX) % 2 == HX).all())
out["HZ_equal"] = bool((np.asarray(ec.HZ) % 2 == HZ).all())
out["n"] = int(HX.shape[1]); out["k"] = int(N - rank(HX) - rank(HZ)); out["rankHX"] = rank(HX); out["rankHZ"] = rank(HZ)
out["k_LX_LZ"] = (len(LX), len(LZ))
# symplectic pairing of my logicals is full rank
out["LX_LZ_pairing_rank"] = rank((LX.astype(int) @ LZ.T.astype(int)) % 2)
assert (HZ.astype(int) @ LX.T.astype(int) % 2 == 0).all() and (HX.astype(int) @ LZ.T.astype(int) % 2 == 0).all()

# ---- legality (own)
probs = []
use = collections.Counter()
for typ, H, chk in (("X", HX, spec["x_checks"]), ("Z", HZ, spec["z_checks"])):
    if len(chk) != N2:
        probs.append(f"{typ}: {len(chk)} checks")
    for i, c in enumerate(chk):
        assert set(c) == {"prep", "meas", "cnots"}
        cols = [a for a, _ in c["cnots"]]
        if sorted(cols) != sorted(np.nonzero(H[i])[0].tolist()):
            probs.append(f"{typ}{i} support")
        dm = (c["meas"] - c["prep"]) % D
        offs = [(t - c["prep"]) % D for _, t in c["cnots"]]
        if not (dm > 0 and all(0 < o < dm for o in offs) and len(set(offs)) == 6):
            probs.append(f"{typ}{i} window")
        for a, t in c["cnots"]:
            use[(a, t)] += 1
out["legality_problems"] = probs
out["data_timestep_clashes"] = sum(1 for v in use.values() if v > 1)

# ---- evaluator validate_schedule + canonical form
from evaluators.candidate import parse_schedule, validate_schedule, build_circuits
es = parse_schedule(json.load(open(path)))
out["validate_schedule"] = validate_schedule(es, ec)
can = es.canonical().to_dict()
out["spec_is_canonical"] = (json.dumps(can, sort_keys=True) == json.dumps({k: spec[k] for k in can}, sort_keys=True))

# ---- labels and translation invariance
def label(typ, i, col):
    a, b = divmod(i, M_)
    if typ == "X":
        cand = {((a + 3) % L_) * M_ + b: "A1", a * M_ + (b + 1) % M_: "A2", a * M_ + (b + 2) % M_: "A3",
                N2 + a * M_ + (b + 3) % M_: "B1", N2 + ((a + 1) % L_) * M_ + b: "B2", N2 + ((a + 2) % L_) * M_ + b: "B3"}
    else:
        cand = {N2 + ((a - 3) % L_) * M_ + b: "A1", N2 + a * M_ + (b - 1) % M_: "A2", N2 + a * M_ + (b - 2) % M_: "A3",
                a * M_ + (b - 3) % M_: "B1", ((a - 1) % L_) * M_ + b: "B2", ((a - 2) % L_) * M_ + b: "B3"}
    assert len(cand) == 6
    return cand[col]
for typ, chk in (("X", spec["x_checks"]), ("Z", spec["z_checks"])):
    sig = collections.Counter((c["prep"], c["meas"], tuple((label(typ, i, a), t) for a, t in sorted(c["cnots"], key=lambda x: x[1])))
                              for i, c in enumerate(chk))
    out[f"{typ}_signatures"] = [list(map(str, k)) for k in sig]
# explicit: every translation maps the schedule onto itself
inv = 0
for a in range(L_):
    for b in range(M_):
        P, p = translation(a, b)
        ok = True
        for typ, chk in (("X", spec["x_checks"]), ("Z", spec["z_checks"])):
            by = {frozenset((int(P[c]), t) for c, t in ch["cnots"]) | {("p", ch["prep"]), ("m", ch["meas"])} for ch in chk}
            for ch in chk:
                if frozenset((int(P[c]), t) for c, t in ch["cnots"]) | {("p", ch["prep"]), ("m", ch["meas"])} not in by:
                    ok = False
        inv += ok
out["translations_preserving_schedule"] = inv

# ---- per data qubit: cyclic X/Z CNOT sequence; instance-level interleaving in the unrolled circuit
seqs = collections.Counter()
for q in range(N):
    s = sorted([(t, "X") for c in spec["x_checks"] for a, t in c["cnots"] if a == q] +
               [(t, "Z") for c in spec["z_checks"] for a, t in c["cnots"] if a == q])
    seqs["".join(x for _, x in s) + "@" + ",".join(str(t) for t, _ in s)] += 1
out["data_cyclic_sequences"] = dict(seqs)
xt = sorted({t for c in spec["x_checks"] for _, t in c["cnots"]}); zt = sorted({t for c in spec["z_checks"] for _, t in c["cnots"]})
out["X_cnot_steps"], out["Z_cnot_steps"] = xt, zt
R = 4
Dd, st, info, nl, sg = my_unroll(spec, R)
out["sigma"], out["starts_set"] = sg, sorted(set(st.values()))
# events on each data qubit: (layer, typ, check, round)
ev = collections.defaultdict(list)
for k, (dm, offs) in info.items():
    for j in range(R):
        for o, a in offs:
            ev[a].append((st[k] + D * j + o, k[0], k[1], j))
# a qubit sees pattern  Z_k ... X_(k') ... Z_k  (an X instance strictly inside a Z instance's CNOTs on one qubit) or vice versa
sand = 0; examples = []
for q, lst in ev.items():
    lst.sort()
    for i1 in range(len(lst)):
        for i2 in range(i1 + 1, len(lst)):
            for i3 in range(i2 + 1, len(lst)):
                a1, b1, c1 = lst[i1], lst[i2], lst[i3]
                if (a1[1], a1[2], a1[3]) == (c1[1], c1[2], c1[3]) and b1[1] != a1[1]:
                    sand += 1
                    if len(examples) < 3:
                        examples.append((q, a1, b1, c1))
out["sandwich_patterns_R4"] = sand
out["sandwich_examples"] = [str(e) for e in examples]
# checks whose instances' CNOT windows on shared qubits interleave: X instance j vs Z instance k with both orders present
both = 0
for i, cx in enumerate(spec["x_checks"]):
    pass
print(json.dumps(out, indent=1, default=str), flush=True)

# ---- determinism and DEM equality with the evaluator's circuits
from evaluators.noise import add_noise
res = []
for basis in "ZX":
    EL = np.asarray(ec.LZ if basis == "Z" else ec.LX) % 2
    for R in Rs:
        nl_ = memory_circuit(spec, basis, R, noise=False, Lover=EL)
        smp = nl_.compile_detector_sampler().sample(32, append_observables=True)
        try:
            nl_.detector_error_model(); dem_ok = True
        except Exception as e:
            dem_ok = repr(e)[:200]
        mine, nd, no = dem_terms(memory_circuit(spec, basis, R, Lover=EL))
        evc = build_circuits(es.canonical(), ec, R)[basis]
        evraw = build_circuits(es, ec, R)[basis]
        evd, end_, eno = dem_terms(add_noise(evc, "sd6", 1e-3))
        r = {"basis": basis, "R": R, "noiseless_all_zero": not smp.any(), "dem_ok": dem_ok,
             "mine_terms": len(mine), "eval_terms": len(evd), "dets": (nd, end_),
             "dem_equal": collections.Counter(mine) == collections.Counter(evd),
             "unique_terms": len(set(mine)) == len(mine),
             "canonical_eq_raw_circuit": str(evc) == str(evraw),
             "det_free_obs_terms": sum(1 for d, o in mine if d == 0 and o)}
        print(json.dumps(r), flush=True)
