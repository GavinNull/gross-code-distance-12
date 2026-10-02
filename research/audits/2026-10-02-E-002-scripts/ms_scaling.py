"""Empirically determine what ms_scaling_factor=0 means in ldpc 2.4.1 (C++ source not shipped).
Compare posterior LLRs after a fixed number of min-sum iterations for alpha in {0, 0.5, 0.75, 0.875, 1}.
If alpha=0 were literal, check->bit messages would vanish and LLRs would equal priors."""
import numpy as np
from ldpc import BpDecoder
from ldpc.codes import hamming_code
H = hamming_code(3)
H = np.vstack([H, H[[0]] ^ H[[1]]]) if False else H
syn = np.array([1, 0, 1], dtype=np.uint8)
prior = np.log((1 - 0.1) / 0.1)
for it in (1, 2, 3):
    row = {}
    for a in (0, 0.5, 0.75, 0.875, 0.9375, 1.0):
        d = BpDecoder(H, error_rate=0.1, max_iter=it, bp_method="minimum_sum", ms_scaling_factor=a)
        d.decode(syn)
        row[a] = np.round(np.array(d.log_prob_ratios), 4).tolist()
    print(f"iters={it} prior_llr={prior:.4f}")
    for a, v in row.items():
        print(f"  alpha={a}: {v}")

# Part 2: a non-converging instance (larger random LDPC), compare alpha=0 against constants per iteration count.
from baselines.bb_code import gross_code
Hx = gross_code().HX
rng = np.random.default_rng(1)
e = (rng.random(Hx.shape[1]) < 0.12).astype(np.uint8)
s = (Hx.astype(int) @ e % 2).astype(np.uint8)
print("\nPart 2: gross HX, random weight", e.sum())
for it in (1, 2, 3, 4):
    ref = {}
    for a in (0, 0.5, 0.75, 0.875, 1.0):
        d = BpDecoder(Hx, error_rate=0.05, max_iter=it, bp_method="minimum_sum", ms_scaling_factor=a)
        d.decode(s)
        ref[a] = (np.array(d.log_prob_ratios), d.converge)
    msg = {a: float(np.abs(ref[0][0] - v[0]).max()) for a, v in ref.items() if a != 0}
    print(f"iters={it} converged(alpha=0)={ref[0][1]}  max|LLR(alpha=0)-LLR(alpha=c)| = {msg}")
