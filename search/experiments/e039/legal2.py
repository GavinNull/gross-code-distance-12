"""E-039: legality for W(P) (separate reset / measurement layers: mu - pi <= P - 1) and Mg(P) (merged
measure+reset layer: mu - pi <= P).  Same conditions as e038.model.legal except the window bound."""
from search.experiments.e036_audit.core import support


def legal_any(s, merged=False):
    P = s.P
    gap = P if merged else P - 1
    for k in s.ks:
        ts = [s.tau[(k, a)] for a in range(6)]
        if len(set(ts)) != 6:
            return False, f"{k} repeated"
        if not all(s.pi[k] < t < s.mu[k] for t in ts) or s.mu[k] - s.pi[k] > gap:
            return False, f"{k} window"
    onq = {}
    for k in s.ks:
        for a, q in enumerate(support(k)):
            onq.setdefault(q, []).append(s.tau[(k, a)] % P)
    for q, rs in onq.items():
        if len(set(rs)) != len(rs):
            return False, f"qubit {q} collision"
    for kx in s.ks:
        if kx[0] != "X":
            continue
        for kz in s.ks:
            if kz[0] != "Z":
                continue
            sx, sz = support(kx), support(kz)
            sh = [q for q in sx if q in sz]
            for i in range(-4, 5):
                if sum(s.tau[(kx, sx.index(q))] < s.tau[(kz, sz.index(q))] + i * P for q in sh) % 2:
                    return False, f"{kx},{kz} parity {i}"
    return True, ""
