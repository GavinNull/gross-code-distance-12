"""Rewrite the 'note' field of certificate variable maps with the encoding-specific text of build_certificates.py
(the first jobs of the run used a single generic note).
    PYTHONPATH=.:tests uv run python scripts/zenodo/fix_varmap_notes.py
"""
import ast
import gzip
import json
from pathlib import Path

src = open("scripts/zenodo/build_certificates.py").read()
notes = {}
for node in ast.parse(src).body:
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in ("NOTE_GSAT", "NOTE_TIMESAT"):
        notes[node.targets[0].id] = ast.literal_eval(node.value)
for f in Path("release/zenodo/certificates").rglob("*.varmap.json.gz"):
    d = json.load(gzip.open(f))
    if "order_class_uniqueness" in str(f):
        continue
    timesat = any(v.startswith("('g'") for v in d["variables"].values())
    new = notes["NOTE_TIMESAT" if timesat else "NOTE_GSAT"]
    if d["note"] != new:
        d["note"] = new
        with gzip.open(f, "wt") as g:
            json.dump(d, g, separators=(",", ":"))
        print("fixed", f)
