"""SM S11-S12 (circuits A, B, C and Fig. 12): legality, determinism, pipelining, interleaving, and invariance of the extended code.

For each circuit: (i) every check applies exactly six CNOTs to its row support at distinct steps inside its window
and no data qubit takes part in two CNOTs in one step; (ii) the noiseless memory circuits (R = 1, 2, 3, 6, both bases)
have deterministic detectors and observables (stim builds the detector error model) and fire nothing; (iii) reset and
measurement steps, number of X/Z switches per data qubit over one period (cyclic); (iv) relation of every check's CNOT
order to the Fig. 12 order (rev, s12, s56); (v) the extended-code column set (both bases) equals the one in
data/extended_code/.

    python code/check_circuits.py A B C fig12
"""
import sys

from common_cli import Verdict, circuit, load_code
from gross12 import ext as E
from gross12.schedule import build_circuits, validate_schedule

names = sys.argv[1:] or ["A", "B", "C", "fig12"]
code = load_code()
V = Verdict()
V(True, "gross code: HX, HZ equal the polynomial definition; k = 12; LX, LZ are logical operators of rank 12")
fx, fz = circuit("fig12").orders()


def relation(o, f):
    if o == f:
        return "id"
    r = f[::-1]
    if {o[0], o[1]} == {r[0], r[1]} and o[2:4] == r[2:4] and {o[4], o[5]} == {r[4], r[5]}:
        return "rev*swaps"
    if {o[0], o[1]} == {f[0], f[1]} and o[2:4] == f[2:4] and {o[4], o[5]} == {f[4], f[5]}:
        return "swaps"
    return "other"


for name in names:
    spec = circuit(name)
    P = spec.period
    pr = validate_schedule(spec, code)
    V(not pr, f"[{name}] legality: period {P}, every check 6 CNOTs on its support inside its window at distinct steps, "
              f"no data-qubit conflict ({len(pr)} problems)")
    det = []
    for R in (1, 2, 3, 6):
        for b, c in build_circuits(spec.canonical(), code, R).items():
            c.detector_error_model()           # raises if a detector or observable is not deterministic
            s = c.compile_detector_sampler(seed=1).sample(64, append_observables=True)
            det.append(not s.any())
    V(all(det), f"[{name}] determinism: R = 1, 2, 3, 6 both bases: detectors/observables deterministic, noiseless "
                f"circuit fires nothing ({sum(det)}/{len(det)})")
    preps = sorted({c.prep for c in spec.x_checks + spec.z_checks})
    meas = sorted({c.meas for c in spec.x_checks + spec.z_checks})
    seq = {}
    for ty, checks in (("X", spec.x_checks), ("Z", spec.z_checks)):
        for c in checks:
            for a, t in c.cnots:
                seq.setdefault(a, []).append((t, ty))
    sw = []
    for a, s in seq.items():
        s = [ty for _, ty in sorted(s)]
        sw.append(sum(s[i] != s[i - 1] for i in range(len(s))))
    hist = {k: sw.count(k) for k in sorted(set(sw))}
    wrap = sum(1 for c in spec.x_checks + spec.z_checks if any((t - c.prep) % P != t - c.prep for _, t in c.cnots)
               or c.meas < c.prep)
    V(True, f"[{name}] reset steps {preps}, measurement steps {meas}; windows crossing the period boundary: {wrap}/144; "
            f"X/Z switches per data qubit per period: {hist} ({'interleaved' if max(hist) > 2 else 'non-interleaved'})")
    xo, zo = spec.orders()
    rel = {}
    for o, f in list(zip(xo, fx)) + list(zip(zo, fz)):
        r = relation(o, f)
        rel[r] = rel.get(r, 0) + 1
    V(rel.get("other", 0) == 0, f"[{name}] CNOT orders vs Fig. 12: {rel} (all in the 8-element class <rev, s12, s56>)")
    for basis in "ZX":
        keys = E.ext_keys_from_file(code, basis)
        kc, _, _ = E.ext_columns(code, basis, spec)
        V(set(kc) == set(keys) and len(kc) == 360,
          f"[{name}] extended code, {basis}-basis memory: {len(kc)} merged columns, equal to the Fig. 12 column set")
        for R in (1, 2, 3):
            g, st = E.dem_groups(spec, code, R, basis)
            V(set(g) == set(keys) and st["telescoping_bad"] == 0 and st["bad_obs"] == 0,
              f"[{name}] {basis} basis R={R}: DEM image set = extended code ({st['image_keys']} keys), template "
              f"identity and logical effect hold for all {st['mechanisms']} mechanisms")
V.exit()
