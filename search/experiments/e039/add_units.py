"""E-039: CNF + unit clauses fixing prep times.  spec: 'X=0' (all X checks pi = 0), 'Z=d', or 'X0=0,Z5=3,...'.
usage: uv run python -m search.experiments.e039.add_units base.cnf out.cnf SPEC"""
import json
import sys

base, out, spec = sys.argv[1:4]
mp = json.load(open(base.replace(".cnf", "_map.json")))["pi_eq"]
units = []
for item in spec.split(","):
    lhs, v = item.split("=")
    names = [n for n in mp if (n == lhs or (lhs in ("X", "Z") and n[0] == lhs))]
    for n in names:
        lit = mp[n][str(int(v))] if str(int(v)) in mp[n] else None
        if lit is True or lit is None:
            if lit is None:
                raise SystemExit(f"{n}={v} outside range")
            continue
        if lit is False:
            raise SystemExit(f"{n}={v} impossible")
        units.append(lit)
lines = open(base).read().split("\n", 1)
h = lines[0].split()
with open(out, "w") as f:
    f.write(f"p cnf {h[2]} {int(h[3]) + len(units)}\n")
    f.write(lines[1])
    if not lines[1].endswith("\n"):
        f.write("\n")
    for u in units:
        f.write(f"{u} 0\n")
print(len(units), "units")
