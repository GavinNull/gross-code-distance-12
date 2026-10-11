"""E-024b control: store the E-018 (audited) Fig. 12 weight-11 lists in w11.py's key format under the Fig. 12 class
tag for colouring (3,1,1), so gen.py / gsat.py can be run on the Fig. 12 class as a control.

    PYTHONPATH=. uv run python -m search.experiments.e024b.fig12list
"""
import pickle

from search.experiments.e018 import common as C18
from search.experiments.e021.mono import fig12_labels
from search.experiments.e024b.common import OUT, colour, ext_general, labord, name, type_key, types
from search.experiments.e024b.w11 import tag_of

f = fig12_labels()
for kind in "XZ":
    TY = types(kind)
    per = {}
    for i in range(72):
        per.setdefault(colour((3, 1, 1), i), set()).add(type_key(f[kind][i]))
    assert all(len(v) == 1 for v in per.values())
    orders = tuple(next(o for o in TY if type_key(o) == next(iter(per[c]))) for c in range(3))
    s = ",".join(name(o) for o in orders)
    E = ext_general(kind, labord((3, 1, 1), orders))
    E0 = C18.ext(kind)
    assert set(E["He"][:, j].tobytes() + E["Le"][:, j].tobytes() for j in range(E["N"])) == set(E0["keys"])
    keys = [[E0["keys"][j] for j in S] for S in C18.load_logicals(kind)]
    pickle.dump({"keys": keys, "meta": {"source": "E-018 stage a (audited)", "orders": s}},
                open(OUT / f"w11_{tag_of(kind, (3, 1, 1), s)}.pkl", "wb"))
    print(kind, s, len(keys))
