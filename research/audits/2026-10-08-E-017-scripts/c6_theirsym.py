"""C6: translation symmetry on the experimenter's single-round instance, recomputed independently via the
fault correspondence (stim explain locations -> projected fault components -> translated components),
compared with their orbit partition; writes the instance in my DFS format with MY orbits.
usage: c6_theirsym.py <hom> <order> <basis>
"""
import json, sys
sys.path.insert(0, "/Users/ephemeral/Desktop/qec-ai-search")
import numpy as np
from common import N, HOMS, gid, l as LL, m as MM, rank
from search.experiments.e017 import dfs_inst
OUT = "/Users/ephemeral/Desktop/qec-ai-search/results/E-017-audit"
hom, order, basis = sys.argv[1], sys.argv[2], sys.argv[3]
inst = dfs_inst.build(hom, order == "paper", basis, 1, 0)
c = inst["circuit"]; keep, rows, He, Le, corb = inst["keep"], inst["rows"], inst["He"], inst["Le"], inst["corb"]
dpos = {keep[r]: i for i, r in enumerate(rows)}
coords = c.get_detector_coordinates()
want = 1 if basis == "Z" else 0
colkey = {He[:, j].tobytes() + Le[:, j].tobytes(): j for j in range(He.shape[1])}
proj = ("X", "Y") if basis == "Z" else ("Z", "Y")
ex = c.explain_detector_error_model_errors(reduce_to_one_representative_error=False)
comp2col = {}
bad = 0
for e in ex:
    hv = np.zeros(He.shape[0], np.uint8); lv = np.zeros(Le.shape[0], np.uint8)
    for t in e.dem_error_terms:
        d = t.dem_target
        if d.is_relative_detector_id() and int(coords[d.val][2]) == want:
            hv[dpos[d.val]] ^= 1
        elif d.is_logical_observable_id():
            lv[d.val] ^= 1
    if not (hv.any() or lv.any()):
        continue
    j = colkey[hv.tobytes() + lv.tobytes()]
    for loc in e.circuit_error_locations:
        tick = loc.tick_offset; name = loc.instruction_targets.gate
        comp = []
        for t in loc.flipped_pauli_product:
            q = t.gate_target.value
            pc = "X" if t.gate_target.is_x_target else ("Y" if t.gate_target.is_y_target else "Z")
            if pc in proj:
                pre = name in ("X_ERROR", "Z_ERROR") and tick % 8 == 7
                pt = tick + (0 if pre else 1)
                if q < N and pt % 8 == 7:   # left qubit just before M == just after M
                    pt += 1
                comp.append((pt, q))
        comp = tuple(sorted(comp))
        if comp in comp2col and comp2col[comp] != j:
            bad += 1
        comp2col[comp] = j
f = HOMS[hom]
def tq(q, s):
    i, j = (q % N) // MM, (q % N) % MM
    return (N if q >= N else 0) + gid(i + s[0], j + s[1])
ncol = He.shape[1]
perms = []; okall = True
for s in [(i, j) for i in range(LL) for j in range(MM) if f((i, j)) == 0]:
    pi = {}
    for comp, j in comp2col.items():
        im = tuple(sorted((pt, tq(q, s)) for pt, q in comp))
        if im not in comp2col:
            okall = False; break
        k = comp2col[im]
        if pi.setdefault(j, k) != k:
            okall = False; break
    if not okall or sorted(pi.values()) != list(range(ncol)):
        okall = False; break
    perm = [pi[j] for j in range(ncol)]
    Hp, Lp = He[:, perm], Le[:, perm]
    if not (rank(He) == rank(Hp) == rank(np.vstack([He, Hp])) and
            rank(np.vstack([He, Le])) == rank(np.vstack([Hp, Lp])) == rank(np.vstack([He, Le, Hp, Lp]))):
        okall = False; break
    perms.append(perm)
orb = [-1] * ncol; no = 0
for j in range(ncol):
    if orb[j] < 0:
        for p in perms:
            orb[p[j]] = no
        no += 1
# compare partitions
same_partition = all((orb[a] == orb[b]) == (corb[a] == corb[b]) for a in range(ncol) for b in range(ncol))
res = dict(comp_to_col_conflicts=bad, n_perms=len(perms), ok=okall, n_orbits=no,
           orbit_sizes=sorted(set(orb.count(o) for o in range(no))), same_partition_as_lead=bool(same_partition),
           rows=int(He.shape[0]), cols=int(ncol), maxw=int(He.sum(0).max()))
print(res)
with open(f"{OUT}/their_{hom}_{order}_{basis}.txt", "w") as fo:
    fo.write(f"{He.shape[0]} {ncol} {no}\n")
    for j in range(ncol):
        rr = np.nonzero(He[:, j])[0].tolist()
        lm = int(sum(1 << b for b in np.nonzero(Le[:, j])[0]))
        fo.write(f"{orb[j]} {lm} {len(rr)} " + " ".join(map(str, rr)) + "\n")
json.dump(res, open(f"{OUT}/c6_{hom}_{order}_{basis}.json", "w"))
