"""Build all variants from the paper; end-cycle k, generator weights; stim determinism of memory circuits."""
import sys, json, itertools
import numpy as np, stim
sys.path.insert(0, '.')
from mycirc import *
sys.path.insert(0, '/Users/ephemeral/Desktop/qec-ai-search')
from evaluators.noise import add_noise

def variants(code, hom):
    a, b = natural_order(code, hom)
    out = {}
    for kind in ("IV", "VIII"):
        for sa, sb in itertools.product((0, 1), (0, 1)):
            aa = (a[0], a[2], a[1]) if sa else a
            bb = (b[0], b[2], b[1]) if sb else b
            out[(kind, sa, sb)] = (aa, bb)
    return out

if __name__ == "__main__":
    res = []
    for code in PARENT:
        l, m, A, B = PARENT[code]
        for hom in ("x", "y", "xy"):
            try:
                a, b = natural_order(code, hom)
                Morph(l, m, a, b, hom, "IV")
            except AssertionError:
                continue
            for key, (aa, bb) in variants(code, hom).items():
                M = Morph(l, m, aa, bb, hom, key[0])
                ec = M.check_contraction()
                info = dict(code=code, hom=hom, kind=key[0], sa=key[1], sb=key[2], a=aa, b=bb)
                for i in (1, 2):
                    HX, HZ = ec[i]
                    k = M.N - gf2_rank(HX) - gf2_rank(HZ)
                    info[f"k{i}"] = int(k)
                    info[f"wX{i}"] = sorted(set(map(int, HX.sum(1))))
                    info[f"wZ{i}"] = sorted(set(map(int, HZ.sum(1))))
                if code != "bb288":
                    pass
                if code != "bb288":
                    for basis, full in (("Z", True), ("X", True), ("Z", False)):
                        c = M.memory(basis, 3, full_detectors=full)
                        nc = add_noise(c, "sd6", 1e-3)
                        dem = nc.detector_error_model(decompose_errors=False)  # raises if nondeterministic
                        info[f"dem{basis}{int(full)}"] = (dem.num_detectors, dem.num_observables, dem.num_errors, M.det_info)
                print(json.dumps(info), flush=True)
                res.append(info)
    json.dump(res, open('/Users/ephemeral/Desktop/qec-ai-search/results/E-019-audit/t0_build.json', 'w'), indent=1)
