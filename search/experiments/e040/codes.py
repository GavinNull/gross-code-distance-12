"""E-040 code access: the two BB codes through the audited E-028 ([[90,8,10]]) and E-032 (gross) common modules
(read-only use; their DFS temp files and binaries are redirected to results/E-040-min-period)."""
from __future__ import annotations

from pathlib import Path

from search.experiments.e028 import common as C90
from search.experiments.e032 import common as CG

OUT = Path("results/E-040-min-period")
OUT.mkdir(parents=True, exist_ok=True)
for _C in (C90, CG):
    _C.OUT = OUT
    _C.BIN = OUT / "dfs_first"
    _C.BINALL = OUT / "dfs128_all"

MOD = {"bb90": C90, "gross": CG}
DCODE = {"bb90": 10, "gross": 12}
TASK = {"bb90": "bb90-dcirc", "gross": "gross-dcirc"}
