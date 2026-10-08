"""C8: end-cycle codes (x, repo): instances for (a) code distance, (b) minimum stabiliser weight; translation
symmetry checked; and (c) injection of weight-12 logicals into my noiseless memory circuits.
usage: c8_endcycle.py build            -> writes instances results/E-017-audit/ec/*.txt
       c8_endcycle.py witness <file>   -> parses FOUND lines (adfs output, end-cycle X/Z instances) and injects
"""
import json, os, pickle, sys
import numpy as np
import stim
from common import N, HOMS, gid, l as LL, m as MM, rank, nullspace, memory

OUT = "/Users/ephemeral/Desktop/qec-ai-search/results/E-017-audit"
os.makedirs(f"{OUT}/ec", exist_ok=True)
f = HOMS["x"]
K = [(i, j) for i in range(LL) for j in range(MM) if f((i, j)) == 0]


def logicals(Hs, Ho):
    Kn = nullspace(Ho); out = []; cur = Hs.copy(); rk = rank(cur)
    for v in Kn:
        t = np.vstack([cur, v])
        if rank(t) > rk:
            out.append(v); cur = t; rk += 1
    return np.array(out)


def tperm(s):
    return [gid((q // MM) + s[0], (q % MM) + s[1]) for q in range(N)]


def write(path, H, L, orb, nrow=None):
    with open(path, "w") as fo:
        fo.write(f"{H.shape[0]} {H.shape[1]} {max(orb)+1}\n")
        for c in range(H.shape[1]):
            rr = np.nonzero(H[:, c])[0].tolist()
            lm = int(sum(1 << b for b in np.nonzero(L[:, c])[0])) if L is not None else 0
            fo.write(f"{orb[c]} {lm} {len(rr)} " + " ".join(map(str, rr)) + "\n")


def build():
    info = {}
    orb = [f((q // MM, q % MM)) for q in range(N)]   # cosets of K
    for c in (0, 1):
        z = np.load(f"{OUT}/endcycle_x_repo_c{c}.npz")
        HXe, HZe = z["HX"], z["HZ"]
        LX, LZ = logicals(HXe, HZe), logicals(HZe, HXe)
        assert len(LX) == len(LZ) == 12
        sym = []
        for s in K:
            p = tperm(s)
            okc = all(rank(np.vstack([Hm, Hm[:, np.argsort(p)]])) == rank(Hm) for Hm in (HXe, HZe))
            # logical classes: [H;L] rowspace invariant
            okl = all(rank(np.vstack([Hm, Lm])) == rank(np.vstack([Hm, Lm, Hm[:, np.argsort(p)], Lm[:, np.argsort(p)]]))
                      for Hm, Lm in ((HZe, LZ), (HXe, LX)))
            sym.append(okc and okl)
        info[f"c{c}"] = dict(sym_all_K=all(sym), n=len(sym))
        # (a) distance instances: X errors: H = HZe, L = LZ ; Z errors: H = HXe, L = LX
        write(f"{OUT}/ec/dist_c{c}_Xerr.txt", HZe, LZ, orb)
        write(f"{OUT}/ec/dist_c{c}_Zerr.txt", HXe, LX, orb)
        # (b) min weight of nonzero element of rowspace(HXe): G v = 0 with G = basis of ker(HXe)
        for name, Hm in (("X", HXe), ("Z", HZe)):
            G = nullspace(Hm)
            assert G.shape[0] == N - rank(Hm)
            write(f"{OUT}/ec/stabw_c{c}_{name}.txt", G, None, orb)
        np.savez(f"{OUT}/ec/logicals_c{c}.npz", LX=LX, LZ=LZ)
    print(info)
    json.dump(info, open(f"{OUT}/ec/build.json", "w"))


def witness(files):
    """files: adfs outputs with FOUND lines on dist_c{c}_{X,Z}err instances. Inject the logical as Pauli
    errors with probability 1 on left qubits right after the R layer of round t (= one component of the sd6
    idle DEPOLARIZE1 there; for t = 1 the reset flip of the initial left reset) of my noiseless T-round memory
    circuit, T = 4, 5, and evaluate all my detectors (c2 blocks) and observables."""
    out = {}
    for fn in files:
        c = int(fn.split("dist_c")[1][0]); typ = "X" if "Xerr" in fn else "Z"
        sets = [list(map(int, ln.split("cols:")[1].split())) for ln in open(fn) if ln.startswith("FOUND")]
        if not sets:
            continue
        sup = sets[0]
        z = np.load(f"{OUT}/endcycle_x_repo_c{c}.npz")
        Hm = z["HZ"] if typ == "X" else z["HX"]
        v = np.zeros(N, np.uint8); v[sup] = 1
        assert not np.any((Hm.astype(int) @ v) % 2)
        basis = "Z" if typ == "X" else "X"
        mop = "M" if basis == "Z" else "MX"
        res = []
        for T in (4, 5):
            P = pickle.load(open(f"{OUT}/c2_x_repo_{basis}_T{T}.pkl", "rb"))
            D = np.vstack([P["blocks"][k] for k in sorted(P["blocks"])])
            OBS = P["OBS"]; cols_all = P["cols_all"]
            C, gates, meas = memory("x", "repo", T, basis)
            nrec = C.nrec
            ann = stim.Circuit()
            for v in D:
                ann.append("DETECTOR", [stim.target_rec(cols_all[j] - nrec) for j in np.nonzero(v)[0]])
            for k, v in enumerate(OBS):
                ann.append("OBSERVABLE_INCLUDE", [stim.target_rec(cols_all[j] - nrec) for j in np.nonzero(v)[0]], k)
            for t in range(1, T + 1):
                if 1 - ((t - 1 + 0) % 2) != c:   # code at the start of round t: C_end of round p(t)
                    continue
                li = [i for i, (ops, tg) in enumerate(C.layers) if tg == (t, "R")][0]
                inj = stim.Circuit()
                inj.append("X_ERROR" if typ == "X" else "Z_ERROR", sup, 1.0)
                circ = C.stim({li: inj}) + ann
                det, ob = circ.compile_detector_sampler().sample(2, separate_observables=True)
                dets = int(det[0].sum()); obs = int(ob[0].sum())
                res.append(dict(T=T, t=t, detectors_fired=dets, observables_flipped=obs))
        out[fn] = dict(weight=len(sup), support=sup, results=res,
                       ok=all(r["detectors_fired"] == 0 and r["observables_flipped"] > 0 for r in res))
    print(json.dumps(out))
    json.dump(out, open(f"{OUT}/ec/witness.json", "w"), indent=1)


if __name__ == "__main__":
    if sys.argv[1] == "build":
        build()
    else:
        witness(sys.argv[2:])
