"""CP-SAT MLE 与暴力穷举最小权重对比（小问题）。注意：每 trial 用新 CpSatMLE 以避开 id() 缓存回收。"""
import numpy as np, scipy.sparse as sp, itertools
from evaluators.decoder_mle import CpSatMLE
class P: pass
rng=np.random.default_rng(1); keep=[]; mism=0; opt=0; trials=60
for t in range(trials):
    mle=CpSatMLE(time_limit_s=10.0)
    nd=int(rng.integers(4,8)); M=int(rng.integers(6,14))
    cols=[sorted(rng.choice(nd,size=min(int(rng.integers(1,4)),nd),replace=False).tolist()) for _ in range(M)]
    rows=[r for c in cols for r in c]; cidx=[j for j,c in enumerate(cols) for _ in c]
    H=sp.csc_matrix((np.ones(len(rows),np.uint8),(rows,cidx)),shape=(nd,M))
    L=sp.csr_matrix((np.ones(M,np.uint8),(np.zeros(M,int),np.arange(M))),shape=(1,M))
    pri=np.clip(rng.uniform(0.001,0.2,M),1e-15,0.5-1e-12)
    pr=P(); pr.H=H; pr.L=L; pr.priors=pri; keep.append(pr)
    w=np.log((1-pri)/pri); Hd=H.toarray().astype(np.uint8)
    s=(Hd@(rng.uniform(size=M)<pri).astype(np.uint8))%2
    best=min((w[np.array(b,bool)].sum() for b in itertools.product([0,1],repeat=M) if np.array_equal((Hd@np.array(b,np.uint8))%2,s)),default=None)
    r=mle.decode(pr,s); opt+=int(r.optimal)
    if r.weight is None or round(1000*r.weight)>round(1000*best)+2:
        mism+=1; print(f"[MISMATCH] t{t} mle={r.weight} brute={best} opt={r.optimal}")
print(f"trials={trials} weight_mismatches={mism} proved_optimal={opt}  (expect 0 mism, {trials} opt)")
