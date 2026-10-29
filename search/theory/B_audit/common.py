"""Auditor (theory B) common helpers.  Independent of search/theory/B: only evaluator public API + project code builders.

Bulk timing conventions (derived from the qec-schedule/v1 spec alone):
  check timing unrolled from its prep p: CNOT at T = p + ((t - p) mod P), meas at p + ((m - p) mod P).
  Instance j of a check acts at T + j P.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
for p in (str(ROOT), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

TASK = {"gross": "gross-dcirc", "bb90": "bb90-dcirc", "bb108": "bb108-dcirc", "bb72": "bb72-dcirc"}


def get_code(name):
    if name.startswith("kunlun-"):
        from search.experiments.e036.common import code
        return code(name.split("-", 1)[1])
    from evaluators.tasks import build_code, get_task
    return build_code(get_task(TASK[name]), None)[0]


def load_spec_dict(path):
    return json.loads((ROOT / path).read_text())


def mats(code, basis):
    """(H_reader, L) for the memory basis: Z basis -> X errors seen by HZ, LZ."""
    f = lambda M: (np.asarray(M, np.int64) % 2).astype(np.uint8)
    return (f(code.HZ), f(code.LZ)) if basis == "Z" else (f(code.HX), f(code.LX))


class Bulk:
    """Bulk (infinite-round) timing data of a schedule for one memory basis."""

    def __init__(self, spec: dict, code, basis: str):
        P = self.P = int(spec["period"])
        W, Rd = (spec["x_checks"], spec["z_checks"]) if basis == "Z" else (spec["z_checks"], spec["x_checks"])
        self.H, self.L = mats(code, basis)
        self.n = self.H.shape[1]

        def un(ch):
            p = int(ch["prep"]) % P
            ev = sorted((p + ((int(t) - p) % P), int(q)) for q, t in ch["cnots"])
            return [q for _, q in ev], {q: t for t, q in ev}
        self.wr = [un(c) for c in W]          # writer: (order, time)
        self.rd = [un(c) for c in Rd]         # reader
        # sanity: reader supports = rows of H (same order)
        for z, (o, _) in enumerate(self.rd):
            assert sorted(o) == sorted(np.flatnonzero(self.H[z]).tolist())
        self.zof = [[] for _ in range(self.n)]
        for z, (o, _) in enumerate(self.rd):
            for q in o:
                self.zof[q].append(z)

    def sig(self, z, q, u):
        """bulk step index: min{t : rho + tP > u} (u never equals a read time on q)."""
        rho = self.rd[z][1][q]
        assert u != rho
        return int(np.floor((u - rho) / P_(self))) + 1

    # realisations -----------------------------------------------------------------------------
    def data_patterns(self, q):
        """distinct item patterns {z: index} of a data error on q, modulo a common integer shift."""
        out = []
        P = self.P
        for u2 in range(1, 2 * P, 2):
            u = u2 / 2
            pat = {z: self.sig(z, q, u) for z in self.zof[q]}
            m = min(pat.values())
            pat = tuple(sorted((z, v - m) for z, v in pat.items()))
            if pat not in out:
                out.append(pat)
        return out

    def hook_items(self, c, k):
        """hook of writer c (instance 0), ancilla error after its (k-1)-th CNOT, k=1..6 (1-based):
        list of (z, index) items (unreduced) and the suffix."""
        order, tm = self.wr[c]
        suf = order[k - 1:]
        items = []
        for q in suf:
            for z in self.zof[q]:
                items.append((z, self.sig(z, q, tm[q])))
        return items, suf

    def key(self, qs):
        v = np.zeros(self.n, np.uint8)
        for q in qs:
            v[q] ^= 1
        h = (self.H.astype(np.int64) @ v % 2).astype(np.uint8)
        lv = (self.L.astype(np.int64) @ v % 2).astype(np.uint8)
        return h.tobytes() + lv.tobytes()


def P_(b):
    return b.P


def reduce_items(items):
    """cancel equal (z, index) items in pairs (they pair within one fault)."""
    from collections import Counter
    c = Counter(items)
    return tuple(sorted(it for it, m in c.items() if m % 2))
