"""Audit E-024b (s1): slab structure of the wrapping p18w circuit + the extra premise the split lemma needs.
Slab k = [min start of round k, max measurement of round k] (same definition as anyR_wrap.py).
Split lemma (gap = one fault-free slab k+1) needs, for F_< (faults before slab k+1) alone, that every round-(k+1)
measurement sees the FINAL data frame. Data frame of the relevant type changes after T1 = start(slab k+1) only via
round-k 'spreading' CNOTs (X-check CNOTs for X errors / Z-basis; Z-check CNOTs for Z errors / X-basis) at t >= T1.
Premise (A): for every data qubit q, every such late round-k spreading CNOT on q precedes every round-(k+1)
'reading' CNOT on q (Z-check for X errors, X-check for Z errors).
    SPEC=... PYTHONPATH=.:tests uv run python research/audits/2026-10-11-E-024b-scripts/s1_slab.py
"""
import json, os, sys
sys.path.insert(0, "tests")
from evaluators.tasks import build_code, get_task
from evaluators.candidate import parse_schedule, unroll
code, _ = build_code(get_task("gross-dcirc"), None)
spec = parse_schedule(json.load(open(os.environ["SPEC"]))).canonical()
R = int(os.environ.get("R", "8")); D = spec.period
U = unroll(spec, code, R)
typ = {}
for t, lst in U.preps.items():
    for q, ty in lst: typ[q] = ty
ev = []  # (t, data q, anc type, round)
for t, lst in U.cnots.items():
    for a, b in lst:
        anc = a if a in U.start else b; dq = b if anc == a else a
        ev.append((t, dq, typ[anc], (t - U.start[anc]) // D, anc))
st = {j: min(U.start[q] + D * j for q in U.start) for j in range(R)}
en = {}
for t, lst in U.meas.items():
    for q, ty, j in lst: en[j] = max(en.get(j, -1), t)
info = {"slabs": [(st[j], en[j]) for j in range(R)], "starts_mod": sorted({s % D for s in U.start.values()})}
for basis, spread, read in (("Z", "X", "Z"), ("X", "Z", "X")):
    viol = []
    for k in range(R - 1):
        T1 = st[k + 1]
        for q in range(144):
            late = [t for t, dq, ty, j, _ in ev if dq == q and ty == spread and j == k and t >= T1]
            rd = [t for t, dq, ty, j, _ in ev if dq == q and ty == read and j == k + 1]
            if late and rd and min(rd) < max(late):
                viol.append((k, q, sorted(late), sorted(rd)[:3]))
    info[f"premiseA_{basis}_violations"] = len(viol)
    info[f"premiseA_{basis}_examples"] = viol[:6]
    # also: does any round-(k+1) reading CNOT happen before the end of slab k at all?
    info[f"{basis}_reads_of_round_k+1_before_end_slab_k"] = sum(
        1 for t, dq, ty, j, _ in ev if ty == read and 1 <= j < R and t <= en[j - 1])
    info[f"{basis}_spreads_of_round_k_after_start_slab_k+1"] = sum(
        1 for t, dq, ty, j, _ in ev if ty == spread and j < R - 1 and t >= st[j + 1])
print(json.dumps(info, indent=1, default=str))
os.makedirs("results/E-024b-audit/p18w", exist_ok=True)
json.dump(info, open("results/E-024b-audit/" + os.environ.get("TAG","p18w") + "/s1_slab.json", "w"), indent=1, default=str)
