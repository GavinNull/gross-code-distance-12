"""E-038: stim validation of pattern nogoods (soundness of the clauses that make a class UNSAT).

For each sampled pattern clause C (one choice of data-cut readers f*): ask the SAT solver for a legal schedule of the
class that VIOLATES C (assumptions: all suffix conditions true, all detector parities 0).  Then, independently of the
CNF, on that schedule:
  (a) rebuild the slot mechanisms from model.Bulk (tags D(q, f*, r), H(k, U, r), M(c, r)) and check they cancel with a
      non-trivial observable;
  (b) embed them in the middle of the own periodic stim circuit (R = 10, rounds shifted by 3) and check that every slot
      mechanism's (detector set, observable) is a mechanism of the stim DEM and that their XOR is (empty, non-zero);
  (c) evaluator template DEM (candidate.memory_circuit + noise sd6), R = 6: exact min weight <= |pattern|.
Any failure = unsound clause.
usage: uv run python -m search.experiments.e038.validate_patterns N 7 results/E-038-bb18-d4/cegar_bb18_N7_d4_patterns.json --n 200
"""
import argparse
import itertools
import json
import random
import time

from pysat.solvers import Solver

from search.experiments.e036_audit.core import min_weight_le
from search.experiments.e038.cegar import PatternEncoder
from search.experiments.e038.enc import Enc
from search.experiments.e038.model import Bulk, stim_circuit, stim_mechs
from search.experiments.e038.validate_model import evaluator_check


def load(path):
    out = []
    for b, slots in json.load(open(path)):
        sl = []
        for s in slots:
            if s[0] == "D":
                sl.append(("D", s[1], s[2]))
            elif s[0] == "H":
                sl.append(("H", tuple(s[1]), tuple(s[2]), s[3]))
            else:
                sl.append(("M", tuple(s[1]), s[2]))
        out.append((b, tuple(sl)))
    return out


def check_witness(sch, basis, slots, fstars, R=10, shift=3):
    bk = Bulk(sch, basis, W=R)
    ms = bk.mechs()
    idx = {}
    for d, o, tag in ms:
        if tag[0] == "D":
            idx[("D", tag[1], tag[2], tag[3])] = (d, o)
        elif tag[0] == "H":
            idx[("H", tag[1], tuple(sorted(tag[2])), tag[3])] = (d, o)
        else:
            idx[("M", tag[1], tag[2])] = (d, o)
    sel = []
    fi = 0
    for s in slots:
        if s[0] == "D":
            sel.append(idx[("D", s[1], fstars[fi], s[2] + shift)])
            fi += 1
        elif s[0] == "H":
            sel.append(idx[("H", s[1], s[2], s[3] + shift)])
        else:
            sel.append(idx[("M", s[1], s[2] + shift)])
    D = O = 0
    for d, o in sel:
        D ^= d
        O ^= o
    bulk_ok = (D == 0 and O != 0)
    circ, dets = stim_circuit(sch, basis, R)
    sm = set(stim_mechs(circ))
    tot_d = tot_o = 0
    stim_ok = True
    for d, o in sel:
        sd = 0
        i = 0
        dd = d
        while dd:
            if dd & 1:
                c = bk.readers[i // bk.NJ]
                j = i % bk.NJ - 4
                if not (1 <= j <= R - 1):
                    stim_ok = False
                else:
                    sd |= 1 << dets[(c, j)]
            dd >>= 1
            i += 1
        if (sd, o) not in sm:
            stim_ok = False
        tot_d ^= sd
        tot_o ^= o
    stim_ok = stim_ok and tot_d == 0 and tot_o != 0
    return bulk_ok, stim_ok


def main(cls, arg, path, n, seed, variant):
    rng = random.Random(seed)
    pats = load(path)
    E = Enc(variant, cls, arg)
    PE = PatternEncoder(E)
    items = []
    for p in rng.sample(pats, min(n, len(pats))):
        items.append((p, 0))
    s = Solver(name="cd15", bootstrap_with=E.cl)
    ptr = len(E.cl)
    stats = {"cls": cls, "arg": arg, "variant": variant, "tested": 0, "no_schedule": 0, "bulk_fail": 0,
             "stim_fail": 0, "eval_fail": 0, "seed": seed}
    t0 = time.time()
    for p, ci in items:
        basis, slots = p
        # recompute the clause choice list in the same order as PatternEncoder.clauses
        rev = PE.rev[basis]
        dslots = [x for x in slots if x[0] == "D"]
        choices = list(itertools.product(*[rev[x[1]] for x in dslots]))
        cls_all = []
        for ch in choices:
            one = PE.clauses_for_choice(p, ch)
            if one is not None:
                cls_all.append((ch, one))
        if not cls_all:
            stats["trivial"] = stats.get("trivial", 0) + 1
            continue
        ch, cl = rng.choice(cls_all)
        if any(l is True for l in cl):
            continue
        ass = [-l for l in cl]
        for c_ in E.cl[ptr:]:
            s.add_clause(c_)
        ptr = len(E.cl)
        if not s.solve(assumptions=ass):
            stats["no_schedule"] += 1
            continue
        sch = E.decode(s.get_model())
        fstars = [f for f in ch]
        bo, so = check_witness(sch, basis, slots, fstars)
        _, ecirc = evaluator_check(sch, basis, 6)
        we, _ = min_weight_le(stim_mechs(ecirc), len(slots))
        stats["tested"] += 1
        stats["bulk_fail"] += (not bo)
        stats["stim_fail"] += (not so)
        stats["eval_fail"] += (we is None)
        if not (bo and so and we is not None):
            print("FAIL", repr(p), ch, bo, so, we, json.dumps(sch.to_json()))
        if stats["tested"] % 25 == 0:
            print(json.dumps(stats), round(time.time() - t0, 1), flush=True)
    print(json.dumps(stats))
    with open("results/E-038-bb18-d4/validate_patterns.jsonl", "a") as f:
        f.write(json.dumps(stats) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cls")
    ap.add_argument("arg", type=int)
    ap.add_argument("path")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--variant", default="bb18")
    a = ap.parse_args()
    main(a.cls, a.arg, a.path, a.n, a.seed, a.variant)
