"""Auditor E-033 claim 5: independent minimum-weight check on MY OWN DEM (mylib circuit, own logicals, SD6 lam=1,
columns merged by (detector set, observable mask)), NOT using ccsearch or the experimenter's instances.
  (i)  SAT: exists x with D x = 0, L x != 0, |x| <= W-1 ?   (expect UNSAT)
  (ii) enumerate all x with D x = 0, L x != 0, |x| = W by SAT + blocking clauses (stop at CAP), report count.
XOR rows via Tseitin chains; cardinality via pysat.card (seqcounter / totalizer).
  uv run python e1_sat_count.py <circ> <basis> <R> <W> [CAP]"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pysat.solvers import Cadical153
from pysat.card import CardEnc, EncType
from pysat.formula import IDPool
import mylib
SPEC = {"u11": "search/experiments/e032/u11_spec.json", "ibm": "search/experiments/e033/ibm_gross_spec.json",
        "fig12": "search/experiments/e033/fig12_gross_spec.json"}
ROOT = "/Users/ephemeral/Desktop/qec-ai-search/"
circ, basis, R, W = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
CAP = int(sys.argv[5]) if len(sys.argv) > 5 else 100000
c = mylib.memory_circuit(mylib.load_spec(ROOT + SPEC[circ]), basis, R, p=1e-3, lam=1.0)
terms, nd, no = mylib.dem_terms(c)
cols = {}
for dm, om, pr in terms:
    cols.setdefault((dm, om), 0)
keys = list(cols)
n = len(keys)
pool = IDPool(start_from=n + 1)
cl = []
def xor_eq(vars_, rhs_var=None):
    """constrain XOR(vars_) == 0 (rhs_var None) or == rhs_var; returns nothing"""
    if not vars_:
        if rhs_var is not None: cl.append([-rhs_var])
        return
    acc = vars_[0]
    for v in vars_[1:]:
        t = pool.id()
        cl.extend([[-t, acc, v], [-t, -acc, -v], [t, -acc, v], [t, acc, -v]])
        acc = t
    if rhs_var is None:
        cl.append([-acc])
    else:
        cl.extend([[-acc, rhs_var], [acc, -rhs_var]])
for i in range(nd):
    xor_eq([j + 1 for j, (dm, om) in enumerate(keys) if dm >> i & 1])
ob = []
for k in range(no):
    o = pool.id(); ob.append(o)
    xor_eq([j + 1 for j, (dm, om) in enumerate(keys) if om >> k & 1], o)
cl.append(ob)
xs = list(range(1, n + 1))
out = dict(circ=circ, basis=basis, R=R, W=W, ndet=nd, ncols=n)
# (i) |x| <= W-1
t0 = time.time()
card = CardEnc.atmost(xs, bound=W - 1, top_id=pool.top, encoding=EncType.seqcounter)
s = Cadical153(bootstrap_with=cl + card.clauses)
r = s.solve(); out["sat_le_W-1"] = r; out["t_le"] = round(time.time() - t0, 1)
if r:
    out["witness_weight"] = sum(1 for v in s.get_model()[:n] if v > 0)
s.delete()
print(json.dumps(out), flush=True)
# (ii) enumerate |x| == W
pool.occupy(pool.top + 1, card.nv)
t0 = time.time()
card2 = CardEnc.equals(xs, bound=W, top_id=max(pool.top, card.nv), encoding=EncType.seqcounter)
s = Cadical153(bootstrap_with=cl + card2.clauses)
cnt = 0
sols = []
while cnt < CAP and s.solve():
    m = s.get_model()
    sel = [j for j in range(n) if m[j] > 0]
    sols.append(sel); cnt += 1
    s.add_clause([-(j + 1) for j in sel])
out["count_eq_W"] = cnt; out["capped"] = cnt >= CAP; out["t_enum"] = round(time.time() - t0, 1)
print(json.dumps(out), flush=True)
json.dump(dict(out, sols=sols), open(ROOT + f"results/E-033-audit/e1_{circ}_{basis}_R{R}_W{W}.json", "w"))
