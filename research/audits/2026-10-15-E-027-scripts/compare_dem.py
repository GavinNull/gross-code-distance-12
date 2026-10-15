"""Compare the auditor's DEM groups (indep_lift.py) with the package's gross12.ext.dem_groups, key by key."""
import json, sys, time
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import indep_lift as IL
from common_cli import circuit, load_code
from gross12 import ext as E

circ, basis, R = sys.argv[1], sys.argv[2], int(sys.argv[3])
t = time.time()
eff = IL.faults_and_effects(circ, R, basis)
cols, mine, st = IL.my_groups(eff, basis)
t1 = time.time() - t
theirs, tst = E.dem_groups(circuit(circ), load_code(), R, basis)
same_keys = set(theirs) == {k for k, v in mine.items() if v}
diff = 0; dup = 0
for k in theirs:
    a = set(theirs[k]); b = set(mine.get(k, {}))
    dup += len(theirs[k]) - len(a)
    if a != b:
        diff += 1
print(json.dumps(dict(circuit=circ, basis=basis, R=R, mine=st, theirs=tst, same_key_set=same_keys,
                      groups_differing=diff, duplicate_patterns_in_theirs=dup,
                      their_terms_nonzero_image=sum(len(v) for v in theirs.values()), my_secs=round(t1, 1))))
