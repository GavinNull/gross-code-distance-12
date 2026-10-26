"""E-039: scegar inside a fixed-prep-time subclass, e.g. 'X=0' (all X checks reset at layer 0, Z free).
usage: uv run python -m search.experiments.e039.subclass W 9 X=0 --static HH,HHM,DDH --lns 10"""
import argparse
import json
import time

from search.experiments.e039.scegar import Driver

ap = argparse.ArgumentParser()
ap.add_argument("cls")
ap.add_argument("P", type=int)
ap.add_argument("spec")
ap.add_argument("--static", default="HH,HHM,DDH")
ap.add_argument("--lns", type=int, default=10)
ap.add_argument("--nfree", type=int, default=3)
ap.add_argument("--tag", default="")
ap.add_argument("--resume", default="")
ap.add_argument("--dump", action="store_true")
a = ap.parse_args()
tag = f"{a.cls}{a.P}_{a.spec.replace('=', '').replace(',', '_').replace('|', '')}{a.tag}"
D = Driver(a.cls, a.P, a.static.split(","), [p for p in a.resume.split(",") if p], tag=tag)
E = D.E
cube = []
for item in a.spec.split(","):
    lhs, v = item.split("=")
    for k in E.ks:
        if f"{k[0]}{k[1]}" == lhs or (lhs in ("X", "Z") and k[0] == lhs):
            if "|" in v:
                E.add([E.pi[k].eq(int(x)) for x in v.split("|")])   # hard clause: pi in the listed set
                continue
            l = E.pi[k].eq(int(v))
            assert l is not False
            if l is not True:
                cube.append(l)
t0 = time.time()
res, info = D.run(cube=cube, nlns=a.lns, nfree=a.nfree)
D.save()
D.logw({"result": res, "spec": a.spec, "patterns": len(D.pats), "sec": round(time.time() - t0, 1)})
if a.dump and res == "UNSAT":
    D.dump(f"results/E-039-bb18-pipe/{tag}.cnf", extra=[[l] for l in cube])
