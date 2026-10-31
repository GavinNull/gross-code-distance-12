"""E-041 sanity check of the symmetric ansatz encoding (sym.py): solve legality + ansatz only (several random phases),
decode, and check (1) legality (legal2), (2) invariance tau(g e) = f(tau e) holds in the decoded schedule,
(3) the bulk weight<=3 counts are exchanged between bases for swap ansatz (Z <-> X) / equal per basis for 'p'."""
import json
import random

import numpy as np
from pysat.solvers import Solver

from search.experiments.e038.enc import Enc
from search.experiments.e039.legal2 import legal_any
from search.experiments.e041.fast import count, tau_from_sched
from search.experiments.e041.rand import normalise
from search.experiments.e041.rng_enc import EncRange, enc_n8s6
from search.experiments.e041.sym import add_symmetry, event_map, perms

out = []
for cls, name, C in [("W9r1", "s1R", 8), ("W9r1", "s2R", 8), ("N8s6", "s1R", 9), ("N8s6", "s2R", 9)]:
    for seed in range(3):
        E = EncRange(9, [0] + [-1] * 13, [0] + [1] * 13) if cls == "W9r1" else enc_n8s6()
        add_symmetry(E, name, C=C)
        cl = list(E.cl)
        random.Random(seed).shuffle(cl)
        s = Solver(name="cadical195", bootstrap_with=cl)
        assert s.solve()
        sch = E.decode(s.get_model())
        P = 9
        sch.P = 9 if cls == "W9r1" else 10
        ok = legal_any(sch)[0]
        em = event_map(perms()[name[:-1]], True)
        inv = all(sch.tau[e2] == C - sch.tau[e] for e, e2 in em.items())
        tau = normalise(tau_from_sched(sch), sch.P)
        cz = count(tau, sch.P, 4, bases=("Z",))
        cx = count(tau, sch.P, 4, bases=("X",))
        rec = {"cls": cls, "sym": name, "C": C, "seed": seed, "legal": ok, "invariant": inv, "countZ": cz, "countX": cx}
        out.append(rec)
        print(json.dumps(rec), flush=True)
json.dump(out, open("results/E-041-bb18-p9/check_sym.json", "w"))
