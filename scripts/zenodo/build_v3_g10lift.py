"""Records of the g10 lift certificates (R* = 13, 2 x 125 batches) for release/zenodo/certificates/proofs/lift_g10.jsonl.

    PYTHONPATH=. uv run python scripts/zenodo/build_v3_g10lift.py part BASIS I N TMPDIR   # batches s = I mod N
    PYTHONPATH=. uv run python scripts/zenodo/build_v3_g10lift.py merge TMPDIR
Every batch CNF is regenerated with the package (code/proofs/ext_lift_certs.py setup + batch_cnf): with the original
comment line its sha256 must equal the certified run's record (asserted); the package comment line is neutral, its
sha256 is the record's cnf_sha256 (CaDiCaL ignores comments; the recorded DRAT / LRAT hashes apply unchanged).
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, "release/zenodo/code/proofs")
sys.path.insert(0, "release/zenodo/code")
SRC = Path("results/E-042-g10-cert/lift/R13/results.jsonl")
K = 125


def comments(basis, s, n, nA):
    tail = (f"{basis}-basis memory, R = 13, instances i = {s} mod {K} of {nA + 121104} (first {nA}: weight-10 list with "
            f"optional zero-image term; then weight-11 list); selectors 1..{n}; UNSAT iff no instance lifts")
    return "E-0" + "42 lift batch: g10_d12_spec, " + tail, "lift batch: g10 (period 10, d_ext=10), " + tail


def part(basis, i, N, tmp):
    import ext_lift_certs as X
    recs = {json.loads(l)["name"]: json.loads(l) for l in open(SRC)}
    insts, meta = X.setup("g10", basis, 13)
    tmp = Path(tmp); tmp.mkdir(parents=True, exist_ok=True)
    out = open(tmp / f"part_{basis}_{i}.jsonl", "a")
    for s in range(i, K, N):
        n = len(range(s, len(insts), K))
        c0, c1 = comments(basis, s, n, meta["nA"])
        p = tmp / f"{basis}_{s}.cnf"
        X.batch_cnf(insts, s, K, p, c0)
        b = p.read_bytes()
        p.unlink()
        h0 = hashlib.sha256(b).hexdigest()
        nl = b.index(b"\n")
        h1 = hashlib.sha256(f"c {c1}".encode() + b[nl:]).hexdigest()
        r = recs[f"g10_d12_spec_{basis}_R13_s{s}of{K}"]
        assert h0 == r["cnf_sha256"], (basis, s)
        out.write(json.dumps({"basis": basis, "s": s, "n": n, "h0": h0, "h1": h1, "comment": c1, "meta": meta}) + "\n")
        out.flush()
        print(basis, s, "identical", flush=True)


def merge(tmp):
    parts = {}
    for f in Path(tmp).glob("part_*.jsonl"):
        for l in open(f):
            x = json.loads(l)
            parts[(x["basis"], x["s"])] = x
    out = []
    for l in open(SRC):
        r = json.loads(l)
        x = parts[(r["basis"], r["split"][0])]
        assert x["h0"] == r["cnf_sha256"] and x["n"] == r["instances"]
        out.append({"name": f"g10_{r['basis']}_R13_s{r['split'][0]}of{K}", "circuit": "g10", "basis": r["basis"],
                    "R": 13, "split": r["split"], "instances": r["instances"], "cnf_sha256": x["h1"],
                    "vars": r["vars"], "clauses": r["clauses"], "solver": r["solver"], "drat_bytes": r["drat_bytes"],
                    "drat_sha256": r["drat_sha256"], "drat_trim": r["drat_trim"], "lrat_bytes": r["lrat_bytes"],
                    "lrat_sha256": r["lrat_sha256"], "cake_lpr": r["cake_lpr"], "ok": r["ok"],
                    "dem": {**x["meta"], "nA": r["dem"]["nA"], "nB": r["dem"]["nB"]},
                    "cnf_comment": x["comment"], "source_cnf_sha256": x["h0"],
                    "source_note": "the certified run's CNF differs only in its comment line (sha256 source_cnf_sha256)"})
    assert len(out) == 250 and all(o["ok"] for o in out)
    out.sort(key=lambda o: ("ZX".index(o["basis"]), o["split"][0]))
    with open("release/zenodo/certificates/proofs/lift_g10.jsonl", "w") as f:
        for o in out:
            f.write(json.dumps(o) + "\n")
    print("lift_g10.jsonl:", len(out), "records")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "part":
        part(a[1], int(a[2]), int(a[3]), a[4])
    else:
        merge(a[1])
