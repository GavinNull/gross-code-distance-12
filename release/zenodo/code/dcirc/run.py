"""Direct minimum-weight search on the full SD6 detector error model (no extended code, no lists, no lift).

    python code/dcirc/run.py quick [--workers P] [--out DIR]
        ccsearch selftest; [[90,8,10]] c16, R = 1, both bases: no undetected logical of weight <= 9, one of weight 10
        found; control u16, R = 1: none of weight <= 8, one of weight 9 found                    (about 1 CPU min)
    python code/dcirc/run.py full [--workers P] [--out DIR]
        quick + c16 R = 2, 3 (weight <= 9: none; weight 10: found) + u16 R = 2 + gross circuit A, R = 1, both bases:
        no undetected logical of weight <= 11, one of weight 12 found                            (about 50 CPU min)
    python code/dcirc/run.py one CIRCUIT BASIS R W [--out DIR]
        a single decide run, e.g. "A Z 2 11" (1.7 CPU h), "A Z 3 11" (4 CPU h), "c16 Z 12 9" (9 CPU min)
Every run is checked: its final status (NONE / FOUND) equals the expected one, every root case was completed
(NONE), every reported solution is re-verified on a freshly built DEM and by circuit-level injection
(code/dcirc/verify.py); the node count is compared with code/dcirc/reference_runs.tsv (reference machine; equal
for identical instances, reported, not required).  CIRCUIT: A, B, C, fig12, u11, u11_control_p10 (gross code) or c11, c12, c13, c16, u16, s16
([[90,8,10]]); e.g. "c11 Z 12 9" (the period-11 circuit, SM S5).
"""
import argparse
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common_cli import Verdict      # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("mode", choices=["quick", "full", "one"])
ap.add_argument("args", nargs="*")
ap.add_argument("--workers", type=int, default=2)
ap.add_argument("--out", default="dcirc_run")
a = ap.parse_args()
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
py = sys.executable
V = Verdict()
binp = out / "ccsearch"
subprocess.run(["cc", "-O3", "-o", str(binp), str(HERE / "ccsearch.c")], check=True)

ref = {}
for line in open(HERE / "reference_runs.tsv"):
    if line.startswith(("#", "circuit")):
        continue
    c, b, R, W, st, norb, nodes, cpu, _ = line.rstrip("\n").split("\t")
    ref[(c, b, int(R), int(W))] = (st, int(nodes), float(cpu))

expect = {}
if a.mode in ("quick", "full"):
    t0 = time.time()
    r = subprocess.run([py, str(HERE / "selftest.py"), str(binp), "300"], capture_output=True, text=True)
    print(r.stdout.strip().splitlines()[-1], f"({time.time() - t0:.0f} s)", flush=True)
    V.bad |= r.returncode != 0
    jobs = []
    for b in "ZX":
        jobs += [("c16", b, 1, 9, "NONE"), ("c16", b, 1, 10, "FOUND"), ("u16", b, 1, 8, "NONE"), ("u16", b, 1, 9, "FOUND")]
    if a.mode == "full":
        for b in "ZX":
            jobs += [("c16", b, R, 9, "NONE") for R in (2, 3)] + [("c16", b, R, 10, "FOUND") for R in (2, 3)]
            jobs += [("u16", b, 2, 8, "NONE"), ("u16", b, 2, 9, "FOUND")]
            jobs += [("A", b, 1, 11, "NONE"), ("A", b, 1, 12, "FOUND")]
else:
    c, b, R, W = a.args[0], a.args[1], int(a.args[2]), int(a.args[3])
    jobs = [(c, b, R, W, ref.get((c, b, R, W), (None,))[0])]

insts = sorted({(c, b, R) for c, b, R, _, _ in jobs})


def export(cbr):
    c, b, R = cbr
    p = out / f"{c}_{b}_R{R}.txt"
    if not p.exists():
        subprocess.run([py, str(HERE / "export.py"), "dem", c, b, str(R), str(p)], check=True, capture_output=True)
    return p


with ThreadPoolExecutor(a.workers) as ex:
    list(ex.map(export, insts))


def run(job):
    c, b, R, W, exp = job
    inst = out / f"{c}_{b}_R{R}.txt"
    log = out / f"{c}_{b}_R{R}_W{W}.txt"
    with open(log, "w") as f:
        subprocess.run([str(binp), str(inst), "decide", str(W)], stdout=f, check=True)
    return job, log


# longest first
order = sorted(jobs, key=lambda j: -ref.get(j[:4], (None, 0, 0.0))[2])
with ThreadPoolExecutor(a.workers) as ex:
    results = list(ex.map(run, order))
for (c, b, R, W, exp), log in sorted(results, key=lambda x: (x[0][0], x[0][2], x[0][1], x[0][3])):
    lines = open(log).read().splitlines()
    inst = next(line for line in lines if line.startswith("INST"))
    norb = int(inst.split("norb=")[1].split()[0])
    done = next((line for line in lines if line.startswith("DONE")), "DONE MISSING")
    status = done.split()[1]
    norbit = sum(1 for line in lines if line.startswith("ORBIT"))
    nodes = int(done.split("nodes ")[1].split()[0]) if "nodes" in done else -1
    cpu = done.split("cpu ")[1] if "cpu" in done else "?"
    ok = (status == exp if exp else status in ("NONE", "FOUND")) and (status != "NONE" or norbit == norb)
    msg = ""
    if status == "FOUND":
        r = subprocess.run([py, str(HERE / "verify.py"), c, b, str(R), str(log), str(W)], capture_output=True,
                           text=True)
        ok = ok and r.returncode == 0
        msg = "; witness: " + r.stdout.strip().splitlines()[-1].split(": ", 1)[1]
    rr = ref.get((c, b, R, W))
    refmsg = f"reference {rr[1]} ({'equal' if rr[1] == nodes else 'DIFFERENT'})" if rr else "no reference"
    V(ok, f"ccsearch {c} {b} basis R={R} decide W={W}: {status} (expected {exp}); root cases {norbit}/{norb}; "
          f"nodes {nodes}, {refmsg}; cpu {cpu}{msg}")
V.exit()
