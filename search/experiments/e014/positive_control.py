"""E-014 阳性对照：在实例的扩展码上用启发式找一个权重 11 的逻辑错误，算出它的最小轨道 o，
再让 DFS 在情形 o、W=11 下运行，必须找到解（证明 W=10 的“找不到”不是程序空转）。"""
import subprocess
import sys

import numpy as np

from search.noninterleaved.heur import heur_min

D = "results/E-014-gross-dcirc11-proof"
kind = sys.argv[1]
lines = open(f"{D}/inst_{kind}.txt").read().split("\n")
r, N, NO = map(int, lines[0].split())
He = np.zeros((r, N), dtype=np.uint8)
Le = np.zeros((30, N), dtype=np.uint8)
orb = []
for j in range(N):
    lo, hi, lm, o = map(int, lines[1 + j].split())
    h = lo | (hi << 64)
    for i in range(r):
        He[i, j] = (h >> i) & 1
    for i in range(30):
        Le[i, j] = (lm >> i) & 1
    orb.append(o)
Le = Le[Le.any(1)]
for sd in range(1, 6):
    w, x, _ = heur_min(He, Le, trials=600, seed=sd, lns_starts=16, stop_at=11)
    if w is not None and w <= 11:
        break
print(f"{kind}: heuristic logical weight {w}")
assert w == 11, "expected exactly 11 (DFS proved no <=10)"
o = min(orb[j] for j in x)
print(f"{kind}: witness min orbit {o}; running DFS W=11 case {o}")
out = subprocess.run([f"{D}/dfs128", f"{D}/inst_{kind}.txt", "11", str(o)], capture_output=True, text=True).stdout
print(f"{kind}: DFS FOUND lines = {out.count('FOUND')}; {out.strip().splitlines()[-1]}")
