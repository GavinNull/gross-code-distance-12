"""Audit E-023 priority (a), test 1b: decode in the experimenter's detector basis (H) vs the sparsified basis (H' = A H).
mode 'diag'  : re-decode the experimenter's 17 weight-2 failures (diag_lowfail json) on H and H'.
mode 'mc'    : fixed-weight MC, own sampler (P(S) ∝ prod q/(1-q), tilted rejection), own seed, both bases decoded on
               the *same* samples.   args: prob sector w n seed
"""
import sys, json, time
import numpy as np, scipy.sparse as sp
sys.path.insert(0, '.')
from search.experiments.e023.common import sectors
from search.decoders.common import IBM_BPOSD
from search.decoders.decoders import RELAY
from ldpc import BpOsdDecoder
import relay_bp

def decoders(H, q):
    Hc = sp.csc_matrix(H)
    b = BpOsdDecoder(Hc, error_channel=list(q), **IBM_BPOSD)
    r = relay_bp.RelayDecoderF64(sp.csr_matrix(H), error_priors=np.asarray(q, np.float64), seed=777, **RELAY["relay5"])
    return {"bposd": lambda s: np.asarray(b.decode(s), np.uint8),
            "relay": lambda s: np.asarray(r.decode_detailed(s).decoding, np.uint8)}

def fw_sample(q, w, n, rng):
    r = q / (1 - q); lo, hi = 1e-12, 1e12
    for _ in range(200):
        lm = np.sqrt(lo * hi)
        if (lm * r / (1 + lm * r)).sum() > w: hi = lm
        else: lo = lm
    qq = lm * r / (1 + lm * r); out = []
    while len(out) < n:
        B = rng.random((512, len(qq))) < qq
        for row in np.flatnonzero(B.sum(1) == w):
            out.append(np.flatnonzero(B[row]))
            if len(out) == n: break
    return out

def get(prob, label):
    sec = [s for s in sectors(prob, "sd6", 1e-3) if s.label == label][0]
    Hs = np.load(f"results/E-023-audit/a2_Hsparse_{prob}_{label}.npz")["H"]
    return sec, {"orig": sec.H.toarray().astype(np.uint8), "sparse": Hs}

def run(sec, Hs, sets, tag):
    L = sec.L.toarray().astype(np.uint8)
    out = {}
    for bn, H in Hs.items():
        D = decoders(H, sec.q)
        for dn, d in D.items():
            fails, t0 = [], time.process_time()
            for S in sets:
                e = np.zeros(sec.ncol, np.uint8); e[S] = 1
                s = (H @ e % 2).astype(np.uint8)
                eh = d(s)
                ok_syn = bool(((H @ eh) % 2 == s).all())
                fl = bool(((L @ eh) % 2 != (L @ e) % 2).any()) or not ok_syn
                fails.append(fl)
            out[f"{bn}_{dn}"] = dict(nfail=int(sum(fails)), n=len(sets), cpu=time.process_time() - t0,
                                     fail_idx=[int(i) for i in np.flatnonzero(fails)][:200])
            print(tag, bn, dn, out[f"{bn}_{dn}"]["nfail"], "/", len(sets), round(out[f"{bn}_{dn}"]["cpu"]), flush=True)
    return out

if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "diag":
        d = json.load(open("results/E-023-ler-benefit/diag_lowfail_m54_repo_sd6_w2.json"))
        sec, Hs = get("m54_repo", "X")
        sets = [r["cols"] for r in d]
        res = run(sec, Hs, sets, "diag")
        res["rows"] = [dict(cols=r["cols"], dec=r["dec"]) for r in d]
        json.dump(res, open("results/E-023-audit/a3_diag17.json", "w"), indent=1)
    else:
        prob, label, w, n, seed = sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6])
        sec, Hs = get(prob, label)
        rng = np.random.default_rng(seed)
        sets = fw_sample(sec.q, w, n, rng)
        res = run(sec, Hs, sets, f"{prob} {label} w{w}")
        res["sets_failing_any"] = sorted({int(i) for v in res.values() for i in v["fail_idx"]})
        res["sets"] = {str(i): [int(x) for x in sets[i]] for i in res["sets_failing_any"]}
        json.dump(res, open(f"results/E-023-audit/a3_mc_{prob}_{label}_w{w}_s{seed}.json", "w"), indent=1)
