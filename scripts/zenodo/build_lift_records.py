"""Build the extended-lift certificate records of release/zenodo/certificates/proofs/ (version 2.0).

    uv run python scripts/zenodo/build_lift_records.py
Inputs: results/E-031-xor-certificates/lift/{u11,c16,c11,control}/ and results/E-034-veripb3-u11/lift/{c11,c11_cake,
c12,c13}/ (results.jsonl and the checker logs in work/).  For c11, R = 13..19, the E-031 batches were checked by
drat-trim only and re-done in E-034 with cake_lpr (same CNF and DRAT sha256, asserted); the E-034 records are used.
Outputs: lift_{u11,c11,c12,c13,c16}.jsonl, lift_controls.jsonl, lift_instance_order.json, logs/lift_<circuit>_logs.txt.gz.
Record names use the package circuit names; `cnf_comment` is the comment line written into the batch CNF (part of its
sha256), reconstructed here exactly as the generator wrote it.
"""
import gzip
import json
import pickle
import re
import sys
from pathlib import Path

sys.path.insert(0, "release/zenodo/code")
from p11 import common as C                 # noqa: E402

OUT = Path("release/zenodo/certificates/proofs")
R31 = Path("results/E-031-xor-certificates/lift")
R34 = Path("results/E-034-veripb3-u11/lift")
REL = {"u11_spec": "u11", "c16_spec": "c16", "c11_spec": "c11", "c12_spec": "c12", "c13_spec": "c13",
       "u16_spec": "u16", "ctl_p10_spec": "u11_control_p10"}
KEEP = ("cnf_sha256", "vars", "clauses", "solver", "drat_bytes", "drat_sha256", "drat_trim", "lrat_bytes", "lrat_sha256",
        "cake_lpr", "ok")


def scrub(text):
    return re.sub(r"(/[^\s'\"]*)/([^/\s'\"]+)", r"\2", text)


def load(p):
    return [json.loads(l_) for l_ in open(p)]


def convert(r):
    circ = REL[r["circuit"]]
    D, nA, nB = r["dem"]["D"], r["dem"]["nA"], r["dem"]["nB"]
    s, K = r["split"]
    comment = (f"lift batch: {r['circuit']} ({r['family']}, d_ext={D}), {r['basis']}-basis memory, R = {r['R']}, "
               f"instances i = {s} mod {K} of {nA + nB} (first {nA}: weight-{D} list with optional zero-image term; "
               f"then weight-{D + 1} list); selectors 1..{r['instances']}; UNSAT iff no instance lifts")
    out = {"name": f"{circ}_{r['basis']}_R{r['R']}_s{s}of{K}", "circuit": circ, "basis": r["basis"], "R": r["R"],
           "split": [s, K], "instances": r["instances"]}
    out.update({k: r[k] for k in KEEP if k in r})
    out["dem"] = r["dem"]
    out["cnf_comment"] = comment
    out["source_name"] = r["name"]
    return out


sets = {"u11": [R31 / "u11"], "c16": [R31 / "c16"], "c11": [R31 / "c11", R34 / "c11"], "c12": [R34 / "c12"],
        "c13": [R34 / "c13"]}
cake = {r["name"]: r for r in load(R34 / "c11_cake/results.jsonl")}
for circ, dirs in sets.items():
    recs = {}
    for d in dirs:
        for r in load(d / "results.jsonl"):
            if r["name"] in cake:
                c = cake[r["name"]]
                assert c["e031_cnf_sha256_equal"] and c["e031_drat_sha256_equal"] and c["ok"]
                assert c["cnf_sha256"] == r["cnf_sha256"] and c["drat_sha256"] == r["drat_sha256"]
                r = c
            q = convert(r)
            recs[q["name"]] = (q, r["name"], d if r["name"] not in cake else R34 / "c11_cake")
    lst = sorted(recs.values(), key=lambda t: (t[0]["basis"] != "Z", t[0]["R"], t[0]["split"][0]))
    # completeness: every (basis, R) has batches 0..K-1, instance counts add up, every batch UNSAT + both checkers
    byk = {}
    for q, _, _ in lst:
        byk.setdefault((q["basis"], q["R"]), []).append(q)
    for (b, R), qs in byk.items():
        K = qs[0]["split"][1]
        assert sorted(q["split"][0] for q in qs) == list(range(K)) and all(q["split"][1] == K for q in qs), (circ, b, R)
        assert sum(q["instances"] for q in qs) == qs[0]["dem"]["nA"] + qs[0]["dem"]["nB"]
        for q in qs:
            assert q["ok"] and q["solver"]["answer"] == "UNSAT" and q["drat_trim"]["verdict"] == "VERIFIED"
            assert q["cake_lpr"]["verdict"] == "VERIFIED UNSAT", (q["name"], q["cake_lpr"])
    Rs = sorted({R for _, R in byk})
    assert Rs == list(range(1, Rs[-1] + 1)) and {b for b, _ in byk} == {"Z", "X"}
    with open(OUT / f"lift_{circ}.jsonl", "w") as f:
        for q, _, _ in lst:
            f.write(json.dumps(q) + "\n")
    nlog = 0
    with gzip.GzipFile(OUT / "logs" / f"lift_{circ}_logs.txt.gz", "wb", mtime=0) as gz:
        for q, src_name, d in lst:
            for tool in ("cadical", "drat-trim", "cake_lpr"):
                lg = d / "work" / f"{src_name}.{tool}.log"
                if lg.exists():
                    gz.write((f"==> {q['name']}.{tool}.log\n" + scrub(lg.read_text())).encode())
                    nlog += 1
    print(circ, len(lst), "batches, R =", Rs[0], "..", Rs[-1], "both bases, all UNSAT + drat-trim + cake_lpr;",
          nlog, "logs;", round(sum(q["drat_bytes"] for q, _, _ in lst) / 1e9, 1), "GB of DRAT")

ctl = [convert(r) for r in load(R31 / "control/results.jsonl")]
assert all(q["solver"]["answer"] == "SAT" and q["ok"] for q in ctl)
with open(OUT / "lift_controls.jsonl", "w") as f:
    for q in ctl:
        f.write(json.dumps(q) + "\n")
print("controls", len(ctl), "batches, all SAT:", sorted({q["circuit"] for q in ctl}))

# instance order: research list order (pickles) -> index in the package list files
order = {}
for fam, pk in (("bb90", "results/E-028-bb90-interleaved/w{w}_{k}_all_A1A2A3B2B1B3.pkl"),
                ("gross", "results/E-032-gross-short-period/w{w}_{k}_all_A1A2A3B3B1B2.pkl")):
    code = C.load_code(fam)
    D = C.FAMILY[fam]["dext"]
    order[fam] = {}
    for basis, kind in (("Z", "X"), ("X", "Z")):
        keys = C.ext_keys_from_file(code, fam, basis)
        kidx = {k: j for j, k in enumerate(keys)}
        order[fam][basis] = {}
        for w in (D, D + 1):
            lst = C.load_list(fam, w, basis)
            pos = {tuple(S): i for i, S in enumerate(lst)}
            d = pickle.load(open(pk.format(w=w, k=kind), "rb"))
            perm = [pos[tuple(sorted(kidx[k] for k in S))] for S in d["keys"]]
            assert sorted(perm) == list(range(len(lst)))
            order[fam][basis][str(w)] = None if perm == list(range(len(lst))) else perm
        print(fam, basis, {w: ("data-file order" if v is None else "permutation") for w, v in order[fam][basis].items()})
json.dump({"description": "Instance order of the extended-lift batch CNFs: for each family and memory basis, the "
                          "weight-d_ext list and then the weight-(d_ext+1) list; entry i of a permutation is the index, in "
                          "the data file data/logicals/..., of the i-th instance; null = the order of the data file.",
           **order}, open(OUT / "lift_instance_order.json", "w"), separators=(",", ":"))
