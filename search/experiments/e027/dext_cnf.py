"""CNF encoding of "an extended logical of weight <= w exists": H x = 0, L x != 0, |x| <= w (SAT third method for
d_ext = 11 and for the completeness of the 4224 weight-11 logicals).

Variables 1..n are the n = 360 extended-code columns x_j (column order of data/extended_code/*.json).
  * H x = 0: for each of the 72 check rows, XOR of its columns = 0, cut into chunks with fresh Tseitin variables
    (chunk XORs of <= CHUNK+1 literals written out directly: 2^CHUNK clauses each).
  * L x != 0: for each of the 12 logical rows, p_r <-> XOR of its columns (Tseitin, both directions), and the
    clause (p_1 v ... v p_12).
  * |x| <= w: Sinz sequential counter (s_{i,j} = "at least j of x_1..x_i"), only the clauses of the
    "at most" direction; every x of weight <= w extends to a model.
  * optional unit clauses (symmetry-breaking cases, see --case) and blocking clauses (one clause
    (not x_a1 v ... v not x_a11) per given logical; it excludes exactly the solutions that contain that set; for
    |x| <= 11 that is exactly that logical).
Every x with Hx = 0, Lx != 0, |x| <= w extends to a model, and every model restricted to 1..n is such an x: the
encoding is exact on the x variables.

    python dext_cnf.py BASIS W OUT.cnf [--block LOGICALS.json] [--case K] [--chunk C]
--case K (0 <= K < 15): add x_{c_K} = 1 for the representative c_K (smallest column) of orbit K, and x_j = 0 for every
column of orbits 0..K-1 (orbit order of the data file).  The 15 cases cover all solutions up to the 24 translations
(see check_symmetry.py); used only if the unsplit instance is too hard.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "release" / "zenodo" / "data"


def load(basis):
    d = json.load(open(DATA / "extended_code" / f"extended_code_{basis}_memory.json"))
    cols = d["columns"]
    assert [c["index"] for c in cols] == list(range(len(cols)))
    return d, cols


class CNF:
    def __init__(self, nvars):
        self.n = nvars
        self.clauses = []

    def new(self):
        self.n += 1
        return self.n

    def add(self, c):
        self.clauses.append(list(c))

    def xor_eq(self, lits, rhs):
        """XOR of lits = rhs, written out directly (2^(k-1) clauses)."""
        k = len(lits)
        for m in range(1 << k):
            # forbid assignment m (bit i = value of lits[i]) if its parity != rhs
            if bin(m).count("1") % 2 != rhs:
                self.add([-l if (m >> i) & 1 else l for i, l in enumerate(lits)])

    def xor_chain(self, lits, rhs, chunk=4):
        """XOR(lits) = rhs, Tseitin-cut into pieces of <= chunk+1 literals."""
        lits = list(lits)
        while len(lits) > chunk + 1:
            head, lits = lits[:chunk], lits[chunk:]
            t = self.new()                      # t = XOR(head)  <=>  XOR(head + [t]) = 0
            self.xor_eq(head + [t], 0)
            lits.append(t)
        self.xor_eq(lits, rhs)

    def xor_def(self, lits, chunk=4):
        """fresh p with p <-> XOR(lits)."""
        p = self.new()
        self.xor_chain(list(lits) + [p], 0, chunk)
        return p

    def at_most(self, xs, w):
        """Sinz sequential counter, at-most-w direction."""
        n = len(xs)
        if w >= n:
            return
        if w == 0:
            for x in xs:
                self.add([-x])
            return
        s = [[self.new() for _ in range(w)] for _ in range(n)]      # s[i][j]: >= j+1 true among xs[0..i]
        for i, x in enumerate(xs):
            self.add([-x, s[i][0]])
            if i > 0:
                for j in range(w):
                    self.add([-s[i - 1][j], s[i][j]])
                for j in range(1, w):
                    self.add([-x, -s[i - 1][j - 1], s[i][j]])
                self.add([-x, -s[i - 1][w - 1]])

    def write(self, path, comments=()):
        with open(path, "w") as f:
            for c in comments:
                f.write(f"c {c}\n")
            f.write(f"p cnf {self.n} {len(self.clauses)}\n")
            for c in self.clauses:
                f.write(" ".join(map(str, c)) + " 0\n")


def build_data(basis, w, block=(), case=None, chunk=4):
    """Second form: e = M x (e_q = XOR of the columns whose support contains data qubit q), H_code e = 0,
    L_code e != 0.  Equivalent because H_ext = H_code M and L_ext = L_code M (checked by check_identity)."""
    d, cols = load(basis)
    g = json.load(open(DATA / "code" / "gross_code.json"))
    n = len(cols)
    f = CNF(n)
    byq = [[] for _ in range(144)]
    for c in cols:
        for q in c["support"]:
            byq[q].append(c["index"] + 1)
    e = [f.xor_def(byq[q], chunk) for q in range(144)]
    for row in g["H" + basis]:
        f.xor_chain([e[q] for q in row], 0, chunk)
    ps = [f.xor_def([e[q] for q in row], chunk) for row in g["L" + basis]]
    f.add(ps)
    _tail(f, d, n, w, block, case)
    return f, n


def _tail(f, d, n, w, block, case):
    f.at_most(list(range(1, n + 1)), w)
    if case is not None:
        orbits = d["orbits"]
        rep = min(orbits[case])
        f.add([rep + 1])
        for o in orbits[:case]:
            for j in o:
                f.add([-(j + 1)])
    for s in block:
        f.add([-(j + 1) for j in s])


def build(basis, w, block=(), case=None, chunk=4):
    d, cols = load(basis)
    n = len(cols)
    nh, nl = d["num_checks"], d["num_logicals"]
    rows_h = [[] for _ in range(nh)]
    rows_l = [[] for _ in range(nl)]
    for c in cols:
        for i in c["H"]:
            rows_h[i].append(c["index"] + 1)
        for r in c["L"]:
            rows_l[r].append(c["index"] + 1)
    f = CNF(n)
    for r in rows_h:
        f.xor_chain(r, 0, chunk)
    ps = [f.xor_def(r, chunk) for r in rows_l if r]
    f.add(ps)
    f.at_most(list(range(1, n + 1)), w)
    if case is not None:
        orbits = d["orbits"]
        rep = min(orbits[case])
        f.add([rep + 1])
        for o in orbits[:case]:
            for j in o:
                f.add([-(j + 1)])
    for s in block:
        f.add([-(j + 1) for j in s])
    return f, n


def main(argv):
    basis, w, out = argv[0], int(argv[1]), argv[2]
    block, case, chunk = [], None, 4
    if "--block" in argv:
        block = [lg["columns"] for lg in json.load(open(argv[argv.index("--block") + 1]))["logicals"]]
    if "--case" in argv:
        case = int(argv[argv.index("--case") + 1])
    if "--chunk" in argv:
        chunk = int(argv[argv.index("--chunk") + 1])
    f, n = (build_data if "--data" in argv else build)(basis, w, block, case, chunk)
    f.write(out, [f"extended code of Fig. 12, {basis}-basis memory: exists x in F_2^{n} (vars 1..{n} = columns) with "
                  f"H x = 0, L x != 0, |x| <= {w}",
                  f"XOR chunk {chunk}; Sinz counter; case {case}; {len(block)} blocking clauses (last clauses)"])
    print(f"{out}: {f.n} vars, {len(f.clauses)} clauses")


if __name__ == "__main__":
    main(sys.argv[1:])
