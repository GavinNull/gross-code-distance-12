"""E-034: check a planted-test answer: the set found by the search is a weight-W extended logical (independent
re-check through e031/certify.verify_solution), lies in the given lists, and lies in the dropped orbit of block #I.
    uv run python search/experiments/e034/check_planted.py KIND W DROP_INDEX LIST1 [LIST2] -- c1 c2 ...
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "search/experiments/e031"))
from build import build                      # noqa: E402
from certify import verify_solution          # noqa: E402
from u11 import load_u11                     # noqa: E402

i = sys.argv.index("--")
kind, W, drop = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
lists = sys.argv[4:i]
cols = sorted(int(x) for x in sys.argv[i + 1:])
blocks = []
for f in lists:
    blocks += [tuple(sorted(e["columns"])) for e in json.load(open(f))["logicals"]]
I = build(load_u11(kind), W, ())
orbit = {tuple(sorted(int(P[j]) for j in blocks[drop])) for P in I["perms"]}
ok, contains_other = verify_solution("u11", kind, cols, W, [b for b in blocks if b not in orbit])
print(json.dumps({"solution": cols, "valid_logical": ok, "contains_a_kept_block": contains_other,
                  "in_lists": tuple(cols) in set(blocks), "in_dropped_orbit": tuple(cols) in orbit,
                  "dropped_orbit_size": len(orbit)}))
