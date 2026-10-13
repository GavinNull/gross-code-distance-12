"""CaDiCaL (PySAT) wrapper that records every clause, and a DIMACS writer."""
from __future__ import annotations

import gzip

from pysat.solvers import Cadical153


class RecordingSolver(Cadical153):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.clauses = []
        self.nfamily = None

    def add_clause(self, cl, no_return=True):
        self.clauses.append([int(x) for x in cl])
        return super().add_clause(cl, no_return)

    def solve(self, assumptions=[]):
        if self.nfamily is None:
            self.nfamily = len(self.clauses)
        assert not assumptions
        return super().solve()


def dimacs_body(clauses):
    """'p cnf' line and the clauses, exactly as in the certificate files (after their comment header)."""
    nv = max((abs(x) for c in clauses for x in c), default=0)
    return f"p cnf {nv} {len(clauses)}\n" + "\n".join(" ".join(map(str, c)) + " 0" for c in clauses) + "\n"


def write_cnf(path, clauses, comments=()):
    text = "".join(f"c {c}\n" for c in comments) + dimacs_body(clauses)
    with gzip.open(path, "wt") as f:
        f.write(text)
