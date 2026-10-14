"""Positive control of the lift CNF encoding: every single-logical instance of a circuit at R must be SAT (Fig. 12:
all 4224 weight-11 logicals lift at R = 1), and each CaDiCaL model is decoded and checked directly (one mechanism
per group, every detector sum zero).

    python lift_control.py CIRCUIT BASIS R
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import certify as C            # noqa: E402
import lift_cnf as LC          # noqa: E402

circ, basis, R = sys.argv[1], sys.argv[2], int(sys.argv[3])
lists, groups, st = LC.setup(circ, basis, R)
sat = 0
for i, S in enumerate(lists):
    b = LC.Builder()
    b.instance(S, groups, [])
    text = f"p cnf {b.n} {len(b.clauses)}\n" + "".join(" ".join(map(str, c)) + " 0\n" for c in b.clauses)
    p = subprocess.run([C.CADICAL, "-q"], input=text.encode(), capture_output=True)
    if p.returncode != 10:
        continue
    model = {int(t) for l in p.stdout.decode().splitlines() if l.startswith("v") for t in l.split()[1:]}
    # variables 1.. are allocated group by group, mechanisms in order (before any auxiliary variable of the group)
    v, ok, flips = 0, True, set()
    for key in S:
        chosen = []
        for dets in groups[key]:
            v += 1
            if v in model:
                chosen.append(dets)
        if len(groups[key]) > 6:
            v += len(groups[key]) - 1        # ladder variables of the exactly-one constraint
        ok &= len(chosen) == 1
        for d in (chosen[0] if chosen else ()):
            flips ^= {d}
    ok &= not flips
    sat += ok
print(("PASS" if sat == len(lists) else "FAIL"), f"{circ} {basis} R={R}: {sat}/{len(lists)} single instances SAT "
      f"with a directly verified lift")
sys.exit(0 if sat == len(lists) else 1)
