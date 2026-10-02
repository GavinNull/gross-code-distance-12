import sinter, math
import stim
def gen(basis,d,p):
    return stim.Circuit.generated(f"surface_code:rotated_memory_{basis}",distance=d,rounds=d,after_clifford_depolarization=p,before_round_data_depolarization=p,before_measure_flip_probability=p,after_reset_flip_probability=p)
from baselines.surface import per_round
def main():
    tasks=[sinter.Task(circuit=gen(b,d,p),json_metadata=dict(b=b,d=d,p=p)) for b in "xz" for d in (3,5,7) for p in (0.003,0.005)]
    st=sinter.collect(num_workers=3,tasks=tasks,decoders=["pymatching"],max_errors=1500,max_shots=20_000_000)
    R={(s.json_metadata['b'],s.json_metadata['d'],s.json_metadata['p']):s for s in st}
    for d in (3,5,7):
        for p in (0.003,0.005):
            x,z=R['x',d,p],R['z',d,p]
            px,pz=x.errors/x.shots,z.errors/z.shots
            se=math.sqrt(1/x.errors+1/z.errors)
            print(f"d={d} p={p} X={per_round(px,d):.3e}({x.errors}) Z={per_round(pz,d):.3e}({z.errors}) X/Z={per_round(px,d)/per_round(pz,d):.3f} ln-ratio z={math.log(px/pz)/se:+.1f}")
    c=gen("x",3,0.001); import collections; print(collections.Counter(i.name for i in c.flattened()))
if __name__=='__main__': main()
