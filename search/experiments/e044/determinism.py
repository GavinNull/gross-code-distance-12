"""E-044 (4): is the BP-OSD decoder (stimbposd + ldpc, IBM parameters) a pure function of the syndrome?
Same 3000 sampled shots (IBM gross Z, lam1, 2e-3, R = 12, fixed stim seed) decoded by (A) a fresh decoder in order,
(B) a second fresh decoder in reverse order, (C) decoder A again in a shuffled order.  Any disagreement => the
prediction depends on decoder history.
  uv run python -m search.experiments.e044.determinism"""
import numpy as np
from stimbposd import BPOSD

from search.experiments.e044.common import IBM_BPOSD, jdump, noisy, sinter_dem

c = noisy("ibm", "Z", 0.002, "lam1")
dem = sinter_dem(c)
det, obs = c.compile_detector_sampler(seed=4401).sample(3000, separate_observables=True)
A, B = BPOSD(dem, **IBM_BPOSD), BPOSD(dem, **IBM_BPOSD)
pa = np.array([A.decode(s) for s in det])
pb = np.array([B.decode(det[i]) for i in range(len(det))[::-1]])[::-1]
perm = np.random.default_rng(1).permutation(len(det))
pc = np.empty_like(pa)
for i in perm:
    pc[i] = A.decode(det[i])
fa = (pa != obs).any(1)
jdump(dict(test="determinism", shots=len(det), disagree_AB=int((pa != pb).any(1).sum()),
           disagree_AC=int((pa != pc).any(1).sum()), fails_A=int(fa.sum()),
           fails_B=int((pb != obs).any(1).sum()), fails_C=int((pc != obs).any(1).sum())), "determinism.jsonl")
