"""C7: validate adfs (mine) and dfsw (lead's) against brute force on small instances with known answers.
Instance family: code-capacity X errors on BB codes ([[72,12,6]]: l=m=6; [[90,8,10]] is too big for brute
force; use [[72,12,6]] and the direct sum of two copies with rows shifted past 64 / 128 bits).
Brute force: meet in the middle over all column subsets (no pruning, no symmetry).
Writes instances in both formats; prints the expected counts; the shell driver runs both programs.
"""
import itertools, json, sys
import numpy as np
sys.path.insert(0, "/Users/ephemeral/Desktop/qec-ai-search/research/audits/2026-10-08-E-017-scripts")
from common import nullspace, rank

OUT = "/Users/ephemeral/Desktop/qec-ai-search/results/E-017-audit/val"
import os
os.makedirs(OUT, exist_ok=True)


def bb(l, m, A, B):
    n = l * m
    def pm(poly):
        M = np.zeros((n, n), np.uint8)
        for i in range(l):
            for j in range(m):
                for a, b in poly:
                    M[i * m + j, ((i + a) % l) * m + (j + b) % m] ^= 1
        return M
    Am, Bm = pm(A), pm(B)
    return np.concatenate([Am, Bm], 1), np.concatenate([Bm.T, Am.T], 1)


def logicals(Hs, Ho):
    K = nullspace(Ho); out = []; cur = Hs.copy(); rk = rank(cur)
    for v in K:
        t = np.vstack([cur, v])
        if rank(t) > rk:
            out.append(v); cur = t; rk += 1
    return np.array(out)


def write_mine(path, H, L, orb):
    R, C = H.shape
    with open(path, "w") as f:
        f.write(f"{R} {C} {max(orb)+1}\n")
        for c in range(C):
            rr = np.nonzero(H[:, c])[0].tolist()
            lm = int(sum(1 << b for b in np.nonzero(L[:, c])[0]))
            f.write(f"{orb[c]} {lm} {len(rr)} " + " ".join(map(str, rr)) + "\n")


def write_lead(path, H, L, orb):
    R, C = H.shape
    reps = [min(c for c in range(C) if orb[c] == o) for o in range(max(orb) + 1)]
    with open(path, "w") as f:
        f.write(f"{R} {C} {max(orb)+1}\n")
        for c in range(C):
            words = []
            for k in range(5):
                v = 0
                for b in range(64):
                    i = 64 * k + b
                    if i < R and H[i, c]:
                        v |= 1 << b
                words.append(f"{v:x}")
            lm = int(sum(1 << b for b in np.nonzero(L[:, c])[0]))
            f.write(" ".join(words) + f" {lm} {orb[c]}\n")
        f.write(" ".join(map(str, reps)) + "\n")


def brute(H, L, wmax):
    """number of sets of each weight <= wmax with H x = 0 and L x != 0 (MITM over halves)."""
    C = H.shape[1]
    hv = [int("".join(map(str, H[::-1, c])), 2) for c in range(C)]
    lv = [int("".join(map(str, L[::-1, c])), 2) if L.shape[0] else 0 for c in range(C)]
    counts = {}
    # enumerate subsets of size a, store syndrome -> list of (lmask, set)
    for w in range(1, wmax + 1):
        a = w // 2; b = w - a
        tab = {}
        for S in itertools.combinations(range(C), a):
            s = 0; lm = 0
            for c in S:
                s ^= hv[c]; lm ^= lv[c]
            tab.setdefault(s, []).append((lm, S))
        found = set()
        for S in itertools.combinations(range(C), b):
            s = 0; lm = 0
            for c in S:
                s ^= hv[c]; lm ^= lv[c]
            for lm2, S2 in tab.get(s, []):
                if lm ^ lm2 and not set(S) & set(S2):
                    found.add(tuple(sorted(S + S2)))
        counts[w] = found
    return counts


res = {}
HX, HZ = bb(6, 6, [(3, 0), (0, 1), (0, 2)], [(0, 3), (1, 0), (2, 0)])
LZ = logicals(HZ, HX)      # Z logicals (detect X errors)
H, L = HZ, LZ              # X errors: syndrome HZ, logical flips LZ
C = H.shape[1]
cnt = brute(H, L, 6)
res["bb72"] = {w: len(v) for w, v in cnt.items()}
print("bb72", res["bb72"])
# no symmetry
write_mine(f"{OUT}/bb72_nosym.txt", H, L, list(range(C)))
write_lead(f"{OUT}/bb72_nosym_lead.txt", H, L, list(range(C)))
# translation symmetry: orbits = left / right halves (36 each); expected per case = sets containing rep with min orbit
orb = [0] * 36 + [1] * 36
write_mine(f"{OUT}/bb72_sym.txt", H, L, orb)
write_lead(f"{OUT}/bb72_sym_lead.txt", H, L, orb)
reps = [0, 36]
exp_sym = {o: sum(1 for S in cnt[6] if reps[o] in S and min(orb[c] for c in S) == o) for o in (0, 1)}
res["bb72_sym_expected_W6"] = exp_sym
exp_nosym_case = {c: sum(1 for S in cnt[6] if min(S) == c) for c in range(C)}
res["bb72_nosym_expected_W6_total"] = sum(exp_nosym_case.values())
# direct sum with rows shifted: copy 1 rows 0..35, copy 2 rows 150..185 (third word), columns 144
R2 = 186
H2 = np.zeros((R2, 2 * C), np.uint8); L2 = np.zeros((24, 2 * C), np.uint8)
H2[:36, :C] = H; H2[150:186, C:] = H; L2[:12, :C] = L; L2[12:, C:] = L
res["sum_expected_W6"] = 2 * len(cnt[6])
write_mine(f"{OUT}/sum_nosym.txt", H2, L2, list(range(2 * C)))
write_lead(f"{OUT}/sum_nosym_lead.txt", H2, L2, list(range(2 * C)))
orb2 = [0] * 36 + [1] * 36 + [2] * 36 + [3] * 36
write_mine(f"{OUT}/sum_sym.txt", H2, L2, orb2)
write_lead(f"{OUT}/sum_sym_lead.txt", H2, L2, orb2)
json.dump(dict(res=res, exp_nosym_case=exp_nosym_case,
               bb72_W6_sets=sorted(cnt[6])), open(f"{OUT}/expected.json", "w"))
print(json.dumps(res))
