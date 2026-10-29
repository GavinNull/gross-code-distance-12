"""helpers for check_maps*: layer insertion, time reversal, bulk mechanisms + exact min weight."""
from search.experiments.e038.model import Sched, Bulk
from search.experiments.e036_audit.core import min_weight_le
def insert(s, beta):
    f = lambda t: t + (t - beta) // s.P + 1        # number of inserted layers at beta + jP <= t, shifted
    return Sched(s.variant, s.P + 1, {k: f(v) for k, v in s.pi.items()}, {k: f(v) for k, v in s.mu.items()},
                 {e: f(v) for e, v in s.tau.items()})

def reverse(s):
    C = max(s.mu.values()) + 1
    return Sched(s.variant, s.P, {k: C - s.mu[k] for k in s.ks}, {k: C - s.pi[k] for k in s.ks},
                 {e: C - v for e, v in s.tau.items()})

def mw(s, b):
    ms = Bulk(s, b, 6).mechs()
    w, wits = min_weight_le(ms, 3, want_all=True, limit=5000)
    return w, len(wits), sorted((m[0], m[1]) for m in ms)

