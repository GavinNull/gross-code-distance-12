"""E-028: which uniform type assignments (every check of a side the same type) have d_ext = 8 exactly on that side?
Complete W=7 DFS (hook-orbit cases; data-only logicals have weight >= 10) + W=8 witness.
    PYTHONPATH=.:tests uv run python -m search.experiments.e028.uniform7
"""
import json

from search.experiments.e028 import common as C
from search.experiments.e028.dext import dext_dfs, types

res = {}
for kind in "XZ":
    ok = []
    for o in types(kind):
        E = C.ext_general(kind, [o] * C.N2)
        s7, _, c7 = dext_dfs(E, 7, stopfirst=1, workers=2)
        if s7:
            continue
        assert c7
        s8, _, _ = dext_dfs(E, 8, stopfirst=1, workers=2)
        assert s8
        C.verify_logicals(E, s8[:1])
        ok.append(C.name(o))
    res[kind] = ok
    print(kind, len(ok), ok, flush=True)
(C.OUT / "uniform_dext8.json").write_text(json.dumps(res, indent=1))
