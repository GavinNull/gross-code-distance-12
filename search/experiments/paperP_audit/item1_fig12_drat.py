"""Item 1: re-solve every Fig.12 retiming CNF (all-logical + len2only) with CaDiCaL,
check the DRAT proof with drat-trim, and compare CNF sha256 with the release records."""
import gzip, hashlib, json, os, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
CAD = f"{ROOT}/tools/cadical/build/cadical"; DT = f"{ROOT}/tools/drat-trim/drat-trim"
REL = f"{ROOT}/release/zenodo"
TMP = sys.argv[1]
recs = {json.loads(l)["name"]: json.loads(l) for l in open(f"{REL}/certificates/proofs/certificates_proofs.jsonl")}

def run(name):
    r = recs[name]
    raw = gzip.open(f"{REL}/{r['cnf']}").read()
    sha = hashlib.sha256(raw).hexdigest()
    cnf = os.path.join(TMP, name + ".cnf"); open(cnf, "wb").write(raw)
    drat = os.path.join(TMP, name + ".drat")
    t = time.time()
    p = subprocess.run([CAD, "-q", "--no-binary", cnf, drat], capture_output=True, text=True)
    ans = "UNSAT" if p.returncode == 20 else ("SAT" if p.returncode == 10 else f"rc{p.returncode}")
    v = "skip"
    if ans == "UNSAT":
        q = subprocess.run([DT, cnf, drat, "-t", "20000"], capture_output=True, text=True)
        v = "VERIFIED" if "s VERIFIED" in q.stdout else "FAIL"
    os.remove(drat); os.remove(cnf)
    return dict(name=name, sha_match=(sha == r["cnf_sha256"]), solver=ans, drat_trim=v, wall=round(time.time()-t, 1))

names = [n for n in recs if n.startswith("fig12_retimings")]
with ThreadPoolExecutor(4) as ex:
    out = list(ex.map(run, names))
for o in out: print(json.dumps(o))
ok = sum(o["sha_match"] and o["solver"] == "UNSAT" and o["drat_trim"] == "VERIFIED" for o in out)
print(f"SUMMARY {ok}/{len(out)} ok; len2only {sum(1 for o in out if 'len2only' in o['name'] and o['drat_trim']=='VERIFIED' and o['sha_match'])}/25")
