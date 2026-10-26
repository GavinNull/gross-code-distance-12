"""E-039: certificate bookkeeping for a finite_static cube split.  Checks (1) the cubes are exactly all ordered pairs
(a, b), a != b, of layers 1..S for X0's terms 0, 1 (legality forces distinct layers, so they cover every schedule);
(2) every cube CNF is the base CNF plus exactly its unit clauses (byte comparison of the body); (3) every cube has a
drat_many record with 's UNSATISFIABLE' and drat-trim 's VERIFIED' whose cnf_sha256 matches the file.
usage: uv run python -m search.experiments.e039.cover PREFIX --S 7 --jsonl a.jsonl,b.jsonl"""
import argparse
import hashlib
import json

ap = argparse.ArgumentParser()
ap.add_argument("prefix")
ap.add_argument("--S", type=int, default=7)
ap.add_argument("--jsonl", required=True)
a = ap.parse_args()
cubes = json.load(open(a.prefix + "_cubes.json"))
pairs = sorted((c["tau_X0_0"], c["tau_X0_1"]) for c in cubes)
want = sorted((x, y) for x in range(1, a.S + 1) for y in range(1, a.S + 1) if x != y)
base = open(a.prefix + ".cnf").read().split("\n", 1)
nb = int(base[0].split()[3])
recs = {}
for path in a.jsonl.split(","):
    for line in open(path):
        r = json.loads(line)
        recs.setdefault(r["cnf"], []).append(r)
ok_body = ok_cert = 0
bad = []
for i, c in enumerate(cubes):
    p = f"{a.prefix}_cube{i}.cnf"
    txt = open(p).read()
    head, body = txt.split("\n", 1)
    exp = base[1] if base[1].endswith("\n") else base[1] + "\n"
    exp += "".join(f"{u} 0\n" for u in c["units"])
    if body == exp and int(head.split()[3]) == nb + len(c["units"]):
        ok_body += 1
    else:
        bad.append(("body", i))
    h = hashlib.sha256(txt.encode()).hexdigest()
    good = [r for r in recs.get(p, []) if r.get("cadical") == "s UNSATISFIABLE" and r.get("verified") is True
            and r["cnf_sha256"] == h]
    if good:
        ok_cert += 1
    else:
        bad.append(("cert", i))
out = {"prefix": a.prefix, "cubes": len(cubes), "cover_exact": pairs == want, "body_ok": ok_body,
       "verified": ok_cert, "bad": bad,
       "base_sha256": hashlib.sha256(open(a.prefix + ".cnf", "rb").read()).hexdigest()}
print(json.dumps(out))
with open("results/E-039-bb18-pipe/cover.jsonl", "a") as f:
    f.write(json.dumps(out) + "\n")
