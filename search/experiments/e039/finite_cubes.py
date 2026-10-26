"""E-039: split a finite_static N(S) CNF into the S*(S-1) cubes "tau(X0, term0) = a, tau(X0, term1) = b" (a != b;
legality forces distinct layers, so the cubes cover every schedule).  Units in the order encoding: v = t  <->
le(t) & ~le(t-1).  Writes PREFIX_cube{i}.cnf and PREFIX_cubes.json.
usage: uv run python -m search.experiments.e039.finite_cubes results/E-039-bb18-pipe/finite_static_N7_R1.cnf --S 7"""
import argparse
import json

from search.experiments.e038.enc import Enc

ap = argparse.ArgumentParser()
ap.add_argument("cnf")
ap.add_argument("--S", type=int, default=7)
a = ap.parse_args()
E = Enc("bb18", "N", a.S)        # same construction order as finite_static -> identical tau variables
k0 = E.ks[0]
base = open(a.cnf).read().split("\n", 1)
h = base[0].split()
cubes = []
for x in range(1, a.S + 1):
    for y in range(1, a.S + 1):
        if x == y:
            continue
        units = []
        for e, t in (((k0, 0), x), ((k0, 1), y)):
            iv = E.tau[e]
            for l, pos in ((iv.le(t), True), (iv.le(t - 1), False)):
                if l is True or l is False:
                    assert l == pos
                    continue
                units.append(l if pos else -l)
        cubes.append({"tau_X0_0": x, "tau_X0_1": y, "units": units})
pre = a.cnf[:-4]
for i, c in enumerate(cubes):
    with open(f"{pre}_cube{i}.cnf", "w") as f:
        f.write(f"p cnf {h[2]} {int(h[3]) + len(c['units'])}\n")
        f.write(base[1] if base[1].endswith("\n") else base[1] + "\n")
        for u in c["units"]:
            f.write(f"{u} 0\n")
json.dump(cubes, open(f"{pre}_cubes.json", "w"))
print(len(cubes))
