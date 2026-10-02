import stim, sinter
from baselines.surface import per_round
def gen(basis,d,p):
    return stim.Circuit.generated(f"surface_code:rotated_memory_{basis}",distance=d,rounds=d,
        after_clifford_depolarization=p,before_round_data_depolarization=p,before_measure_flip_probability=p,after_reset_flip_probability=p)
def add_idle(c, p):
    # add DEPOLARIZE1(p) on qubits not touched by any gate/measure/reset in each TICK-delimited layer
    allq=set(range(c.num_qubits)); used=set()
    for i in c.flattened(): 
        if i.name=="QUBIT_COORDS": used.update(t.value for t in i.targets_copy())
    allq=used
    out=stim.Circuit(); layer=set()
    def flush():
        idle=sorted(allq-layer)
        if idle: out.append("DEPOLARIZE1",idle,p)
    for i in c.flattened():
        if i.name=="TICK":
            flush(); layer.clear(); out.append(i); continue
        if i.name in ("CX","H","R","M","MR"):
            layer.update(t.value for t in i.targets_copy())
        out.append(i)
    flush()
    return out
def main():
    tasks=[]
    for d in [3,5,7]:
        for p in [0.001,0.005]:
            tasks.append(sinter.Task(circuit=gen("x",d,p),json_metadata=dict(v="memory_x",d=d,p=p)))
            tasks.append(sinter.Task(circuit=add_idle(gen("z",d,p),p),json_metadata=dict(v="z+idle",d=d,p=p)))
    for p in [0.006,0.007,0.008,0.009,0.010]:
        for d in [3,5,7]:
            tasks.append(sinter.Task(circuit=add_idle(gen("z",d,p),p),json_metadata=dict(v="z+idle",d=d,p=p)))
    st=sinter.collect(num_workers=3,tasks=tasks,decoders=["pymatching"],max_errors=300,max_shots=20_000_000)
    for s in sorted(st,key=lambda s:(s.json_metadata['v'],s.json_metadata['p'],s.json_metadata['d'])):
        m=s.json_metadata; f=sinter.fit_binomial(num_shots=s.shots,num_hits=s.errors,max_likelihood_factor=1000)
        print(m['v'],m['d'],m['p'],s.shots,s.errors,f"{per_round(f.best,m['d']):.3e} [{per_round(f.low,m['d']):.2e},{per_round(f.high,m['d']):.2e}]")
    # sanity: idle circuit distance
    c=add_idle(gen("z",5,0.001),0.001); print("idle d5 graphlike dist",len(c.shortest_graphlike_error()))
if __name__=='__main__':
    main()
