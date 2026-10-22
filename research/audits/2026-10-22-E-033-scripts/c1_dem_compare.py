"""Auditor E-033: own gross circuit (mylib: own code, own logicals, own encoder incl. wrapping, own SD6-lambda noise)
vs experimenter's e033.common.noisy() (evaluator template + e026b rescale).  R = 12, p = 3e-3, lam in {0, 0.1, 1},
circuits u11 / ibm / fig12 (specs read from json), Z and X.  Compares:
  (a) detector count; (b) DEM columns keyed by detector set, XOR-merged prior: set equality + max rel. diff;
  (c) observables: there must be ONE invertible 12x12 GF(2) map T with obs_mine = T obs_theirs on every column
      (so "any observable flipped" -- the failure event -- is basis independent).
Also: noiseless circuits sample all-zero detectors/observables; number of idle DEPOLARIZE1 targets per round."""
import sys, json
sys.path[:0] = ["/Users/ephemeral/Desktop/qec-ai-search", "/Users/ephemeral/Desktop/qec-ai-search/tests",
                "/Users/ephemeral/Desktop/qec-ai-search/research/audits/2026-10-22-E-033-scripts"]
import numpy as np
import mylib
from search.experiments.e033.common import noisy as their_noisy
SPEC = {"u11": "search/experiments/e032/u11_spec.json", "ibm": "search/experiments/e033/ibm_gross_spec.json",
        "fig12": "search/experiments/e033/fig12_gross_spec.json"}
ROOT = "/Users/ephemeral/Desktop/qec-ai-search/"

def cols(c):
    out = {}
    nobs = c.num_observables
    for ins in c.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True).flattened():
        if ins.type != "error": continue
        ds = frozenset(t.val for t in ins.targets_copy() if t.is_relative_detector_id())
        ob = 0
        for t in ins.targets_copy():
            if t.is_logical_observable_id(): ob ^= 1 << t.val
        pr = ins.args_copy()[0]
        if ds in out:
            q, o = out[ds]
            out[ds] = (q * (1 - pr) + pr * (1 - q), o if o == ob else None)  # None marks inconsistent obs
        else:
            out[ds] = (pr, ob)
    return out

def bits(x, n=12): return np.array([(x >> i) & 1 for i in range(n)], np.uint8)

def solve_T(pairs):
    """find T (12x12) with T a = b for all (a, b); return (ok, rank of span(a))."""
    A = np.array([bits(a) for a, b in pairs], np.uint8); B = np.array([bits(b) for a, b in pairs], np.uint8)
    M = np.concatenate([A, B], 1)
    Rm, piv = mylib.rref(M)
    if any(pc >= 12 for pc in piv): return False, None
    # consistency: rows of Rm with zero A-part must have zero B-part (handled by piv check); T exists
    ra = mylib.rank(A); rb = mylib.rank(B)
    return True, (ra, rb)

res = []
for name, sp in SPEC.items():
    d = mylib.load_spec(ROOT + sp)
    for b in "ZX":
        c0 = mylib.memory_circuit(d, b, 12, p=0.0)
        s = c0.compile_detector_sampler().sample(200, append_observables=True)
        assert not s.any(), "noiseless not deterministic"
        for lam in (0.0, 0.1, 1.0):
            mine = mylib.memory_circuit(d, b, 12, p=3e-3, lam=lam)
            theirs = their_noisy(name, b, 12, 3e-3, {0.0: "lam0", 0.1: "lam0.1", 1.0: "lam1"}[lam])
            assert mine.num_detectors == theirs.num_detectors
            cm, ct = cols(mine), cols(theirs)
            same = set(cm) == set(ct)
            rel = max(abs(cm[k][0] - ct[k][0]) / ct[k][0] for k in ct) if same else None
            pairs = [(ct[k][1], cm[k][1]) for k in ct if same and ct[k][1] is not None and cm[k][1] is not None]
            incons = sum(1 for k in ct if ct[k][1] is None) + sum(1 for k in cm if cm[k][1] is None)
            okT, rk = solve_T(pairs) if same else (False, None)
            nz_m = sum(1 for k in cm if cm[k][1]); nz_t = sum(1 for k in ct if ct[k][1])
            r = dict(circ=name, basis=b, lam=lam, ndet=mine.num_detectors, ncols=len(cm), same_cols=same,
                     max_rel=rel, T_exists=okT, rank=rk, obs_cols_mine=nz_m, obs_cols_theirs=nz_t, inconsistent=incons)
            print(r, flush=True); res.append(r)
json.dump(res, open(ROOT + "results/E-033-audit/c1_dem_compare.json", "w"), indent=1, default=str)
