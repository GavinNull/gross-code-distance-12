"""Audit E-026: per-round idle census by role, harmful vs harmless (ancilla between meas and next prep)."""
import numpy as np
from search.experiments.e026.common import spec, code, PERIOD
for name in ("p18", "fig12", "ibm"):
    s = spec(name); D = s.period
    win, gaps_in, gaps_out, firsts, lasts = [], 0, 0, [], []
    for c in list(s.x_checks) + list(s.z_checks):
        dm, offs = c.offsets(D)
        o = [x for x, _ in offs]
        win.append(dm)
        gaps_in += dm - 1 - 6          # idle between prep and meas (harmful)
        gaps_out += D - dm - 1         # idle between meas and next prep (harmless)
        firsts.append(o[0]); lasts.append(dm - o[-1])
    # data idle per round
    use = np.zeros((D, code().n), int)
    for c in list(s.x_checks) + list(s.z_checks):
        for a, t in c.cnots: use[t % D, a] += 1
    data_idle = int((use == 0).sum())
    print(name, "D", D, "window dm distinct", sorted(set(win)), "anc harmful idle", gaps_in,
          "anc harmless idle", gaps_out, "data idle", data_idle, "total", gaps_in + gaps_out + data_idle,
          "prep->first CX offsets", sorted(set(firsts)), "lastCX->meas", sorted(set(lasts)))
