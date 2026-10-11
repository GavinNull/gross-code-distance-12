"""E-025 method (B'), variant of exact_sat: 'blocked' encoded through EXPLICIT simple cycles of the qubit graph
(e025.cyc): blocked_pairing <-> OR_C neg_C, neg_C -> sum_terms <= -1 (term = s * (1 + floor(dt/P)) =
s * (const + sum indicators)), each cycle condition by a small one-directional totalizer.  Exact (cycle list complete,
cross-checked against Bellman-Ford in test_cyc.py)."""
from search.experiments.e025.cyc import pairing_classes, cycles_of
from search.experiments.e025.exact_sat import ExactSAT


class ExactCyc(ExactSAT):
    def add_cycle(self, terms, guard):
        """guard -> sum <= -1.  returns False if the cycle can never be negative (then guard is forced false)."""
        pos, neg, const = [], [], 0
        for s, i1, i2 in terms:
            c, ls = self.indicators(i1, i2)
            const += s * c
            (pos if s == 1 else neg).extend(ls)
        # const + #pos - #neg <= -1  <=>  #pos + #(not neg) <= -1 - const + len(neg)
        K = -1 - const + len(neg)
        lits = pos + [-x for x in neg]
        if K < 0:
            self.add([-guard]); return False
        if K >= len(lits):
            return True
        L = self.tot_up(lits, K + 1)
        self.add([-guard, -L[K]])
        return True

    def add_logical(self, k, r):
        g = self.pool.id(("sel", k))
        self.sel[k] = g
        for cls in pairing_classes(r):
            gs = []
            for terms in cycles_of(self.F, r, cls):
                c = self.new()
                if self.add_cycle(terms, c):
                    gs.append(c)
            self.add([-g] + gs)
        return g
