"""Auditor: independent enumeration of all extended logicals of weight <= WMAX (own columns, own MITM in C),
closed under the translation group, compared with (i) the E-031 OPB instances (models: every found logical, with
q / digits computed here, satisfies every constraint of the E-031 .opb unless it contains a blocked set; and the
instance is UNSAT exactly when nothing unblocked is found) and (ii) the release lists.

    uv run python enum.py SOURCE BASIS WMAX       SOURCE: bb90 | bb72 (IBM BB72 extended code; supports from e031's
                                                  load_ibm, everything else own)
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from alib import DATA, ROOT, col_vec, ext_code, rank2  # noqa: E402

OUT = ROOT / "results/E-031-audit/enum"
BIN = ROOT / "results/E-031-audit/bin/mitm"


def bb72(basis):
    sys.path.insert(0, str(ROOT / "search/experiments/e031"))
    from build import load_ibm  # supports, H, L only
    src = load_ibm("bb72", basis)
    H, L = src["H"], src["L"]
    n = H.shape[1]

    def key(S):
        v = np.zeros(n, dtype=np.uint8); v[list(S)] = 1
        return (H.astype(int) @ v % 2).astype(np.uint8).tobytes() + (L.astype(int) @ v % 2).astype(np.uint8).tobytes()
    cols, keys = [], {}
    for S in src["sups"]:
        k = key(S)
        if k.strip(b"\x00") and k not in keys:
            keys[k] = len(cols); cols.append(tuple(S))
    perms = []
    for a in range(6):
        for b in range(6):
            g = np.array([((x + a) % 6) * 6 + (y + b) % 6 for x in range(6) for y in range(6)])
            dp = np.concatenate([g, g + 36])
            perms.append(np.array([keys[key(tuple(dp[list(S)]))] for S in cols]))
    N = len(cols)
    Hc = np.array([[int(H[i, list(S)].sum() % 2) for S in cols] for i in range(H.shape[0])], dtype=np.uint8)
    return dict(N=N, Hc=Hc, cols=cols, perms=perms, H=H, L=L)


_CACHE = {}


def _parse(path):
    if path not in _CACHE:
        cons, blocks = [], set()
        for line in open(path):
            if line.startswith("*"):
                continue
            m = re.fullmatch(r"\s*(.*?)\s*(>=|=)\s*(-?\d+)\s*;\s*", line)
            t = m.group(1).split()
            terms = [(int(t[i]), t[i + 1]) for i in range(0, len(t), 2)]
            if m.group(2) == ">=" and all(v.startswith("~x") and c == 1 for c, v in terms) and int(m.group(3)) == 1:
                blocks.add(frozenset(int(v[2:]) - 1 for c, v in terms))     # clause "not all of B"
            else:
                cons.append((terms, m.group(2), int(m.group(3))))
        _CACHE[path] = (cons, blocks)
    return _CACHE[path]


def opb_check(path, x):
    """evaluate the OPB file at the point given by column set x (q, digits computed here).
    returns (all non-clause constraints hold, x violates some blocking clause i.e. contains a blocked set)."""
    from itertools import combinations
    cons, blocks = _parse(path)
    xs = {f"x{j + 1}" for j in x}
    val = {}
    for terms, rel, rhs in cons:      # set q, then digits
        if rel == "=":
            s = sum(c for c, v in terms if v in xs)
            q = [v for c, v in terms if v.startswith("q")]
            if q:
                val[q[0]] = s % 2; s += s % 2
            half = s // 2
            for c, v in terms:
                if v[0] in "ab":
                    k = int(v.split("_")[1]); val[v] = (half >> k) & 1
    for terms, rel, rhs in cons:
        lhs = 0
        for c, v in terms:
            if v.startswith("~"):
                lit = 0 if v[1:] in xs else 1
            elif v.startswith("x"):
                lit = 1 if v in xs else 0
            else:
                lit = val.get(v, 0)
            lhs += c * lit
        if not (lhs == rhs if rel == "=" else lhs >= rhs):
            return False, None
    sizes = {len(b) for b in blocks}
    blocked = any(frozenset(c) in blocks for k in sizes if k <= len(x) for c in combinations(sorted(x), k))
    return True, blocked


def main():
    src, basis, wmax = sys.argv[1], sys.argv[2], int(sys.argv[3])
    OUT.mkdir(parents=True, exist_ok=True)
    if not BIN.exists():
        subprocess.run(["cc", "-O2", "-o", str(BIN), str(HERE / "mitm.c")], check=True)
    if src == "bb90":
        E = ext_code("bb90", DATA / "circuits/bb90_c16.json", basis,
                     DATA / f"extended_code/bb90_extended_code_{basis}_memory.json")
        Lc = np.array([col_vec(E, r) for r in E["L"]], dtype=np.uint8)
    else:
        E = bb72(basis)
        Lc = np.array([[int(r[list(S)].sum() % 2) for S in E["cols"]] for r in E["L"]], dtype=np.uint8)
    N, Hc, perms = E["N"], E["Hc"], E["perms"]
    assert Hc.shape[0] <= 64 and Lc.shape[0] <= 64
    lines = [str(N)] + [f"{sum(int(Hc[i, j]) << i for i in range(Hc.shape[0])):x} "
                        f"{sum(int(Lc[i, j]) << i for i in range(Lc.shape[0])):x}" for j in range(N)]
    seen, reps = set(), []
    for j in range(N):
        if j not in seen:
            reps.append(j); seen |= {int(P[j]) for P in perms}
    found = {}
    for w in range(1, wmax + 1):
        p = subprocess.run([str(BIN), str(w)] + [str(r) for r in reps], input="\n".join(lines) + "\n",
                           capture_output=True, text=True, check=True)
        sets = {tuple(int(t) for t in l.split(":")[1].split()) for l in p.stdout.splitlines() if l[0].isdigit()}
        closed = {tuple(sorted(int(P[j]) for j in s)) for s in sets for P in perms}
        found[w] = closed
        print(json.dumps({"src": src, "basis": basis, "w": w, "count": len(closed), "tail": p.stdout.splitlines()[-1]}), flush=True)
    for w, S in found.items():           # recheck
        for s in S:
            v = np.zeros(N, dtype=np.uint8); v[list(s)] = 1
            assert not (Hc.astype(int) @ v % 2).any() and (Lc.astype(int) @ v % 2).any() and len(set(s)) == w
    res = {"src": src, "basis": basis, "counts": {w: len(S) for w, S in found.items()}, "orbit_reps": len(reps)}
    if src == "bb90":
        for w in (8, 9):
            if w in found:
                rel = {tuple(sorted(e["columns"])) for e in json.load(open(
                    DATA / f"logicals/bb90_weight{w}_logicals_{basis}_memory.json"))["logicals"]}
                res[f"release_w{w}_equal"] = rel == found[w]
        # models against the E-031 files
        R = ROOT / "results/E-031-xor-certificates/bb90"
        for name, W in ((f"bb90_{basis}_W7", 7), (f"bb90_{basis}_W8_list", 8), (f"bb90_{basis}_W9_lists", 9)):
            if W > wmax:
                continue
            allx = [s for w in found if w <= W for s in found[w]]
            nm = nb = 0
            for s in allx:
                ok, blk = opb_check(str(R / f"{name}.opb"), s)
                if not ok:
                    raise SystemExit(f"logical {s} violates a non-clause constraint of {name}")
                if blk:
                    nb += 1
                else:
                    nm += 1
            res[name] = {"logicals_weight_le_W": len(allx), "unblocked_models": nm, "blocked": nb,
                         "own_verdict": "UNSAT" if nm == 0 else "SAT"}
    else:
        R = ROOT / "results/E-031-xor-certificates/validation"
        for name, W in ((f"bb72_{basis}_W4", 4), (f"bb72_{basis}_W5", 5)):
            allx = [s for w in found if w <= W for s in found[w]]
            okc = sum(opb_check(str(R / f"{name}.opb"), s)[0] for s in allx)
            res[name] = {"logicals_weight_le_W": len(allx), "models": okc, "own_verdict": "UNSAT" if not allx else "SAT"}
        if basis == "Z":
            lst = {tuple(sorted(e["columns"])) for e in json.load(open(R / "bb72_Z_w5_list.json"))["logicals"]}
            res["e031_w5_list_equal"] = lst == found.get(5)
    print(json.dumps(res))
    with open(OUT / "enum.jsonl", "a") as f:
        f.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
