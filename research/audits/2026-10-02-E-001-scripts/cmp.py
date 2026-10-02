import json, math, csv, sinter
from baselines.surface import per_round
def load(p): return {(r['d'],r['p']):r for r in json.load(open(p))}
def sid(p):
    s={}
    for r in csv.DictReader(open(p), skipinitialspace=True):
        m=json.loads(r['json_metadata']); s.setdefault((m['d'],m['p']),set()).add(r['strong_id'])
    return s
zs=[]
for a,b in [("results/E-001-surface-baseline","results/E-001-audit"),("results/E-001b-surface-threshold","results/E-001b-audit")]:
    A,B=load(a+"/summary.json"),load(b+"/summary.json")
    SA,SB=sid(a+"/stats.csv"),sid(b+"/stats.csv")
    print(a, "strong_id all match:", all(SA[k]==SB[k] and len(SA[k])==1 for k in SA), len(SA))
    for k in sorted(A):
        x,y=A[k],B[k]
        p1=x['errors']/x['shots']; p2=y['errors']/y['shots']
        pp=(x['errors']+y['errors'])/(x['shots']+y['shots'])
        se=math.sqrt(pp*(1-pp)*(1/x['shots']+1/y['shots']))
        z=(p1-p2)/se; zs.append(z)
        print(f"d={k[0]} p={k[1]:.3f} orig={x['p_round']:.3e} audit={y['p_round']:.3e} ratio={x['p_round']/y['p_round']:.3f} z={z:+.2f}")
print("n=",len(zs)," max|z|=",max(abs(z) for z in zs), " #|z|>2:",sum(abs(z)>2 for z in zs), " chi2=",sum(z*z for z in zs))
# formula check vs sinter
for ps in [1e-4,0.05,0.27]:
    for r in [3,7]:
        print(ps,r,per_round(ps,r), sinter.shot_error_rate_to_piece_error_rate(ps,pieces=r))
# interval coverage
f=sinter.fit_binomial(num_shots=235793,num_hits=200,max_likelihood_factor=1000)
g=sinter.fit_binomial(num_shots=235793,num_hits=200,max_likelihood_factor=math.exp(3.8415/2))
print("factor1000",f, "\n95%",g, "sqrt chi2 for 1000:", math.sqrt(2*math.log(1000)))
# Lambda
for name,path in [("orig","results/E-001-surface-baseline"),("audit","results/E-001-audit")]:
    S=load(path+"/summary.json")
    for p in [0.001,0.002,0.003]:
        r3,r5,r7=[S[(d,p)] for d in (3,5,7)]
        L35=r3['p_round']/r5['p_round']; L57=r5['p_round']/r7['p_round']
        # rough log-normal CI from relative SE 1/sqrt(errors)
        e35=math.sqrt(1/r3['errors']+1/r5['errors']); e57=math.sqrt(1/r5['errors']+1/r7['errors'])
        print(f"{name} p={p} L35={L35:.2f} [{L35*math.exp(-1.96*e35):.1f},{L35*math.exp(1.96*e35):.1f}] L57={L57:.2f} [{L57*math.exp(-1.96*e57):.1f},{L57*math.exp(1.96*e57):.1f}]")
