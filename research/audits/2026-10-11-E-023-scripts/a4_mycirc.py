"""Audit E-023 priority (a), test 2: independent [[54]] f_y morphing circuit (E-019 auditor's mycirc: explicit
Pauli-propagation detectors, the natural local basis), T = 8 half-cycles, SD6 (evaluators/noise.py read-only),
own DEM column merge, fixed-weight MC with BP-OSD (IBM params) and Relay5, priors = DEM at p = 1e-3.
paper = IV00, repo = IV11 (E-019 audit mapping).
args: variant(paper|repo) basis(X|Z) w n seed full(0|1)"""
import sys, json, time
import numpy as np, scipy.sparse as sp
sys.path.insert(0, 'research/audits/2026-10-08-E-019-scripts'); sys.path.insert(0, '.')
from inst import make
from evaluators.noise import add_noise
sys.path.insert(0, 'research/audits/2026-10-11-E-023-scripts')
from a3_decode_basis import decoders, fw_sample

def merged_dem(nc):
    dem = nc.detector_error_model(decompose_errors=False)
    m, order = {}, []
    for e in dem.flattened():
        if e.type != "error": continue
        pr = e.args_copy()[0]; D, O = set(), set()
        for t in e.targets_copy():
            if t.is_relative_detector_id(): D ^= {t.val}
            elif t.is_logical_observable_id(): O ^= {t.val}
        k = (tuple(sorted(D)), tuple(sorted(O)))
        assert k[0], "detector-free logical"
        if k not in m: m[k] = 0.0; order.append(k)
        m[k] = m[k] * (1 - pr) + pr * (1 - m[k])
    H = np.zeros((dem.num_detectors, len(order)), np.uint8); L = np.zeros((dem.num_observables, len(order)), np.uint8)
    for j, (D, O) in enumerate(order):
        H[list(D), j] = 1; L[list(O), j] = 1
    return H, L, np.array([m[k] for k in order]), order

if __name__ == "__main__":
    var, basis, w, n, seed, full = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6])
    sab = {"paper": (0, 0), "repo": (1, 1)}[var]
    M = make("bb108", "y", "IV", *sab)
    c = M.memory(basis, 8, full_detectors=bool(full))
    nc = add_noise(c, "sd6", 1e-3)
    H, L, q, keys = merged_dem(nc)
    # same-sector restriction is automatic for full=0 (only same-basis detectors); for full=1 keep everything
    deg = H.sum(0)
    info = dict(var=var, basis=basis, full=full, ndet=int(H.shape[0]), ncol=int(H.shape[1]), nobs=int(L.shape[0]),
                lam=float(q.sum()), coldeg_mean=float(deg.mean()), coldeg_max=int(deg.max()),
                rowwt_max=int(H.sum(1).max()), det_info=M.det_info)
    print(json.dumps(info), flush=True)
    rng = np.random.default_rng(seed)
    sets = fw_sample(q, w, n, rng)
    D = decoders(H, q)
    res = dict(info=info, w=w, n=n, seed=seed)
    for dn, d in D.items():
        fails, t0 = [], time.process_time()
        for S in sets:
            e = np.zeros(H.shape[1], np.uint8); e[S] = 1
            s = (H @ e % 2).astype(np.uint8)
            if not s.any():
                raise RuntimeError("undetectable weight-%d error" % w)
            eh = d(s)
            fl = bool(((L @ eh) % 2 != (L @ e) % 2).any()) or bool(((H @ eh) % 2 != s).any())
            fails.append(fl)
        idx = np.flatnonzero(fails)
        res[dn] = dict(nfail=int(len(idx)), cpu=time.process_time() - t0,
                       fail_sets=[[int(x) for x in sets[i]] for i in idx[:100]],
                       fail_keys=[[list(map(list, keys[x])) for x in sets[i]] for i in idx[:30]])
        print(var, basis, "full" if full else "css", "w", w, dn, len(idx), "/", n, round(res[dn]["cpu"]), flush=True)
    json.dump(res, open(f"results/E-023-audit/a4_{var}_{basis}_w{w}_f{full}_s{seed}.json", "w"), indent=1)
