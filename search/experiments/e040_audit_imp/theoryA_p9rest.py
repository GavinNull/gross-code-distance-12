"""E-040 impossibility audit: signatures of the T(9) schedules NOT killed by a flat pair hook (Lemma F, weight d-1),
compared with theory A's 864 survivors (same for both codes?).
   PYTHONPATH=.:tests uv run python -m search.experiments.e040_audit_imp.theoryA_p9rest"""
import json

import numpy as np

import search.experiments.e040_audit_imp.theoryA_check as T
from search.experiments.e040_audit_imp.enum_a import sig_keys

src = T.flat_cover.__code__
res = {}
for name in ("bb90", "gross"):
    # re-run flat_cover but keep the mask
    import types
    killed_holder = {}
    orig = np.zeros
    def fc(name=name):
        C = T.code(name)
        out = T.flat_cover(name, 9)
        return out
    z = np.load("results/E-040-audit-imp/canon_P9.npz")
    TX, TZ = z["TX"].astype(np.int64), z["TZ"].astype(np.int64)
    # mask via monkeypatched np.zeros capture is fragile; recompute directly
    T_np_zeros = np.zeros
    cap = []
    def zeros(*a, **k):
        r = T_np_zeros(*a, **k)
        if a and a[0] == len(TX) and k.get("dtype", a[1] if len(a) > 1 else None) is bool:
            cap.append(r)
        return r
    T.np.zeros = zeros
    T.flat_cover(name, 9)
    T.np.zeros = T_np_zeros
    killed = cap[-1]
    k = sig_keys(TX[~killed], TZ[~killed], 9)
    kall = sig_keys(TX, TZ, 9)
    # signatures all of whose vectors survive vs partially
    surv_sig = np.unique(k)
    killed_sig = np.unique(kall[killed])
    res[name] = {"surviving_vectors": int((~killed).sum()), "surviving_signatures": int(len(surv_sig)),
                 "signatures_with_some_vector_killed_and_some_not": int(len(np.intersect1d(surv_sig, killed_sig)))}
    res[name + "_keys"] = surv_sig
print(json.dumps({n: res[n] for n in ("bb90", "gross")}))
print("same survivor set both codes:", bool(np.array_equal(res["bb90_keys"], res["gross_keys"])))
