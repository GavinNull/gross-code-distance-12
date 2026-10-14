"""CNF encoding of the Lemma 2 lift instances and their DRAT-checked refutation.

Instance (circuit, basis, R, logical S): S is one of the 4224 weight-11 extended logicals (11 columns).  Group g
(g = 1..11) holds the DEM mechanisms whose image is column S_g.  Question: is there a choice of exactly one
mechanism per group such that every detector is flipped an even number of times?  (Same model as the CP-SAT lift
of SM S6.)  CNF: one variable per mechanism of the 11 groups (in group order, mechanisms in DEM order);
  * exactly one per group: one at-least-one clause, at-most-one pairwise (group size <= 6) or by a Sinz ladder;
  * for every detector touched by some mechanism of the groups: XOR of the mechanisms that flip it = 0
    (Tseitin-cut into pieces of <= 5 literals).
Detectors touched by no mechanism of the 11 groups give the constraint 0 = 0 and are omitted.

To amortise process start-up, the instances of one (circuit, basis, R) are batched into one plain CNF as a
disjunction: selector t_i per logical i, clause (t_1 v ... v t_4224), and every clause of
instance i gets the extra literal -t_i (instances use disjoint variables).  The batch CNF is UNSAT iff every
instance is UNSAT.  --split K writes K batch CNFs (logicals i = s mod K for s = 0..K-1) instead of one.

    python lift_cnf.py write CIRCUIT BASIS R OUTDIR [--split K]      # writes OUTDIR/<circuit>_<basis>_R<R>[_s<k>].cnf
    python lift_cnf.py single CIRCUIT BASIS R I OUT.cnf              # instance of logical I alone
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "release" / "zenodo" / "code"))
from common_cli import circuit, load_code       # noqa: E402
from gross12 import ext as E                    # noqa: E402


class Builder:
    def __init__(self):
        self.n = 0
        self.clauses = []

    def new(self):
        self.n += 1
        return self.n

    def xor0(self, lits, guard):
        k = len(lits)
        for m in range(1 << k):
            if bin(m).count("1") % 2 == 1:
                self.clauses.append(guard + [-l if (m >> i) & 1 else l for i, l in enumerate(lits)])

    def xor_chain(self, lits, guard, chunk=4):
        lits = list(lits)
        while len(lits) > chunk + 1:
            head, lits = lits[:chunk], lits[chunk:]
            t = self.new()
            self.xor0(head + [t], guard)
            lits.append(t)
        self.xor0(lits, guard)

    def exactly_one(self, xs, guard):
        self.clauses.append(guard + list(xs))
        if len(xs) <= 6:
            for a in range(len(xs)):
                for b in range(a + 1, len(xs)):
                    self.clauses.append(guard + [-xs[a], -xs[b]])
        else:
            s = [self.new() for _ in xs[:-1]]       # s_i: some x_0..x_i is true
            for i, x in enumerate(xs):
                if i < len(xs) - 1:
                    self.clauses.append(guard + [-x, s[i]])
                if i > 0:
                    self.clauses.append(guard + [-x, -s[i - 1]])
                    if i < len(xs) - 1:
                        self.clauses.append(guard + [-s[i - 1], s[i]])

    def instance(self, S_keys, groups, guard):
        det = {}
        for key in S_keys:
            vs = []
            for dets in groups[key]:
                v = self.new()
                vs.append(v)
                for d in dets:
                    det.setdefault(d, []).append(v)
            self.exactly_one(vs, guard)
        for d in sorted(det):
            self.xor_chain(det[d], guard)


def setup(circ, basis, R):
    code = load_code()
    spec = circuit(circ)
    keys = E.ext_keys_from_file(code, basis)
    lists = [[keys[j] for j in S] for S in E.load_w11(basis)]
    assert len(lists) == 4224
    groups, st = E.dem_groups(spec, code, R, basis)
    assert st["telescoping_bad"] == 0 and st["bad_obs"] == 0 and set(groups) == set(keys), st
    return lists, groups, st


def write(path, b, comments):
    with open(path, "w") as f:
        for c in comments:
            f.write(f"c {c}\n")
        f.write(f"p cnf {b.n} {len(b.clauses)}\n")
        f.write("".join(" ".join(map(str, c)) + " 0\n" for c in b.clauses))


def batch(lists, groups, idx):
    b = Builder()
    sel = [b.new() for _ in idx]
    b.clauses.append(list(sel))
    for t, i in zip(sel, idx):
        b.instance(lists[i], groups, [-t])
    return b


def main(argv):
    cmd, circ, basis, R = argv[0], argv[1], argv[2], int(argv[3])
    lists, groups, st = setup(circ, basis, R)
    if cmd == "single":
        i, out = int(argv[4]), argv[5]
        b = Builder()
        b.instance(lists[i], groups, [])
        write(out, b, [f"lift instance: circuit {circ}, {basis}-basis memory, R = {R}, weight-11 logical {i}"])
        print(out, b.n, len(b.clauses))
        return
    outdir = Path(argv[4])
    outdir.mkdir(parents=True, exist_ok=True)
    K = int(argv[argv.index("--split") + 1]) if "--split" in argv else 1
    for s in range(K):
        idx = list(range(s, len(lists), K))
        b = batch(lists, groups, idx)
        name = f"{circ}_{basis}_R{R}" + (f"_s{s}of{K}" if K > 1 else "")
        write(outdir / f"{name}.cnf", b,
              [f"lift batch: circuit {circ}, {basis}-basis memory, R = {R}, weight-11 logicals i = {s} mod {K} "
               f"({len(idx)} instances); selector variables 1..{len(idx)} in that order; UNSAT iff no instance lifts",
               f"DEM: {st['mechanisms']} mechanisms, {st['detectors']} detectors, {st['image_keys']} image columns"])
        print(name, b.n, len(b.clauses), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
