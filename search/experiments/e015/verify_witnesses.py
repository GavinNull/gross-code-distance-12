"""独立复查 E-015 负面结论的见证（auditor 2026-10-05 问题 1）。

对 heur_*_wit.jsonl 里每个保存的见证（标签形式：('q', 数据比特) 或 ('r', 残余覆盖的数据比特)），
直接从码的校验矩阵重算：x = Σ 列，要求 H·x = 0 且 L·x ≠ 0，并且权重 < target。不经过合并列或任何搜索代码。

    PYTHONPATH=. uv run python search/experiments/e015/verify_witnesses.py
"""
import glob
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import HL, OUT, get_code  # noqa: E402

ok = bad = 0
summary = {}
for path in sorted(glob.glob(str(OUT / "heur_*_wit.jsonl"))):
    m = re.search(r"heur_(\w+?)_(\d+)_([XZ])_T(\d+)_wit\.jsonl", Path(path).name)
    codekey, hk, kind, target = m.group(1), m.group(2), m.group(3), int(m.group(4))
    code = get_code(codekey)
    H, L = (np.asarray(a, dtype=np.uint8) % 2 for a in HL(code, kind))
    n_ok = n_bad = n_nowit = 0
    for line in open(path):
        r = json.loads(line)
        if r.get("w") is None or r["w"] >= target:
            continue
        if "witness" not in r:
            n_nowit += 1
            continue
        cols = []
        for typ, val in r["witness"]:
            cols.append(H[:, [val]].sum(1) if typ == "q" else H[:, val].sum(1))
        hx = (np.sum(cols, axis=0) % 2) if cols else None
        lcols = [L[:, [val]].sum(1) if typ == "q" else L[:, val].sum(1) for typ, val in r["witness"]]
        lx = np.sum(lcols, axis=0) % 2
        good = hx is not None and not hx.any() and lx.any() and len(r["witness"]) == r["w"] < target
        n_ok += good
        n_bad += not good
    summary[Path(path).name] = {"verified": n_ok, "failed": n_bad, "kills_without_witness": n_nowit}
    ok += n_ok
    bad += n_bad
print(json.dumps(summary, indent=1))
print(f"TOTAL verified {ok}, failed {bad}")
(OUT / "verify_witnesses.json").write_text(json.dumps(summary, indent=1))
