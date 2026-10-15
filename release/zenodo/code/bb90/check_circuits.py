"""[[90,8,10]] circuits c16 and the controls u16, s16: legality, determinism, frame, interleaving, symmetry, extended code.

For each circuit: (i) every check applies exactly six CNOTs to its row support at distinct steps inside its window
and no data qubit takes part in two CNOTs in one step; (ii) the noiseless memory circuits (R = 1, 2, 3, 6, both
bases) have deterministic detectors and observables and fire nothing; (iii) reset / measurement / CNOT steps and the
number of X/Z switches per data qubit over one period (cyclic; > 2 = interleaved); (iv) the translations of the
15 x 3 torus that map every check's CNOT order to the order of the image check (45 = translation invariant);
(v) the extended-code column set (both bases) equals data/extended_code/bb90_extended_code_*_memory.json, with 5
column orbits of size 45.

    python code/bb90/check_circuits.py c16 u16 s16
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common_cli import Verdict                                  # noqa: E402
from bb90 import bbcode, ext as E                               # noqa: E402
from gross12.schedule import build_circuits, validate_schedule  # noqa: E402

names = sys.argv[1:] or ["c16", "u16", "s16"]
code = bbcode.load_code()
V = Verdict()
V(True, "[[90,8,10]] code: HX, HZ equal the polynomial definition (l=15, m=3, A = x^9+y+y^2, B = 1+x^2+x^7); k = 8; "
        "LX, LZ are logical operators of rank 8")
for name in names:
    spec = E.circuit(name)
    P = spec.period
    pr = validate_schedule(spec, code)
    V(not pr, f"[{name}] legality: period {P}, every check 6 CNOTs on its support inside its window at distinct steps, "
              f"no data-qubit conflict ({len(pr)} problems)")
    det = []
    for R in (1, 2, 3, 6):
        for b, c in build_circuits(spec.canonical(), code, R).items():
            c.detector_error_model()
            s = c.compile_detector_sampler(seed=1).sample(64, append_observables=True)
            det.append(not s.any())
    V(all(det), f"[{name}] determinism: R = 1, 2, 3, 6 both bases: detectors/observables deterministic, noiseless "
                f"circuit fires nothing ({sum(det)}/{len(det)})")
    checks = spec.x_checks + spec.z_checks
    preps = sorted({c.prep for c in checks})
    meas = sorted({c.meas for c in checks})
    xs = sorted({t for c in spec.x_checks for _, t in c.cnots})
    zs = sorted({t for c in spec.z_checks for _, t in c.cnots})
    nonwrap = all(c.prep < min(t for _, t in c.cnots) and max(t for _, t in c.cnots) < c.meas for c in checks)
    seq = {}
    for ty, chk in (("X", spec.x_checks), ("Z", spec.z_checks)):
        for c in chk:
            for a, t in c.cnots:
                seq.setdefault(a, []).append((t, ty))
    sw = []
    for a, s in seq.items():
        s = [ty for _, ty in sorted(s)]
        sw.append(sum(s[i] != s[i - 1] for i in range(len(s))))
    hist = {k: sw.count(k) for k in sorted(set(sw))}
    frame = nonwrap and preps == [0] and meas == [P - 1]
    V(True,
      f"[{name}] frame: reset steps {preps}, measurement steps {meas}; " + (
          f"every check reset at 0, measured at {P - 1}, all CNOTs strictly inside (non-wrapping: round j occupies "
          f"layers {P}j..{P}j+{P - 1}); " if frame else "") + f"X-check CNOT steps {xs}, Z-check CNOT steps "
      f"{zs}; X/Z switches per data qubit per period: {hist} "
      f"({'interleaved' if max(hist) > 2 else 'non-interleaved'})")
    G = E.order_group(spec)
    V(len(G) == 45, f"[{name}] symmetry: {len(G)}/45 translations of the 15 x 3 torus map every check order to the "
                    f"order of the image check (translation invariant)")
    for basis in "ZX":
        keys = E.ext_keys_from_file(code, basis)
        kc, sups, supkey = E.ext_columns(code, basis, spec)
        perms = E.column_perms(code, basis, kc, sups, supkey, G)
        orbs = E.orbits(perms, len(kc))
        V(set(kc) == set(keys) and len(kc) == 225 and sorted(len(o) for o in orbs) == [45] * 5,
          f"[{name}] extended code, {basis}-basis memory: {len(kc)} merged columns, equal to "
          f"data/extended_code/bb90_extended_code_{basis}_memory.json; {len(orbs)} column orbits of size 45")
V.exit()
