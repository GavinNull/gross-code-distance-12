"""Collect the direct-DEM search runs (ccsearch) into release/zenodo/logs/dcirc/ and write the reference table
release/zenodo/code/dcirc/reference_runs.tsv (status, root cases, nodes, CPU seconds per run).

Run from the repository root:
    uv run python scripts/zenodo/build_dcirc_logs.py

Sources (internal): results/E-029-direct-dcirc/runs/ (circuit A = cs_P18_H24, c16, u16);
results/E-030-bb90-period-ler/runs/ (c11, c12, c13, decide mode); results/E-032-gross-short-period/cc/ (u11 and the
period-10 control).  The instances of the latter were checked byte-identical to the package exporter (c11 R = 1, 12;
c12, c13 R = 1; u11 R = 1, 2; control R = 1).  Runs that were split over
several processes by root-case ranges are merged: for every root case the ORBIT line is taken once; the merged log
must cover every root case exactly once.  Instances are checked to be byte-identical to the ones written by the
package exporter (release/zenodo/code/dcirc/export.py) for R = 1 (circuit A) and R = 1, 3, 12 (c16): done separately
by the experimenter; the node counts of the package quick run equal the reference.
"""
import glob
import re
from pathlib import Path

OUT = Path("release/zenodo/logs/dcirc")
OUT.mkdir(parents=True, exist_ok=True)
SRC = [("results/E-029-direct-dcirc/runs/*.txt", re.compile(r"^(A|c16|u16)_([ZX])_R(\d+)_decide(\d+)(_o\d+-\d+)?\.txt$")),
       ("results/E-030-bb90-period-ler/runs/*.txt", re.compile(r"^(c11|c12|c13)_([ZX])_R(\d+)_decide(\d+)()\.txt$")),
       ("results/E-032-gross-short-period/cc/*.out", re.compile(r"^(u11|ctlp10)_([ZX])_R(\d+)_W(\d+)()\.out$"))]
REN = {"ctlp10": "u11_control_p10"}
cases = {}
for globpat, pat in SRC:
    for f in sorted(glob.glob(globpat)):
        m = pat.match(Path(f).name)
        if not m:
            continue
        c, b, R, W = REN.get(m.group(1), m.group(1)), m.group(2), int(m.group(3)), int(m.group(4))
        cases.setdefault((c, b, R, W), []).append(f)

rows = []
ORD = ["A", "c16", "u16", "c11", "c12", "c13", "u11", "u11_control_p10"]
for (c, b, R, W), files in sorted(cases.items(), key=lambda x: (ORD.index(x[0][0]), x[0][2], x[0][1], x[0][3])):
    orbit_lines, sols, inst, dones, ranges = {}, [], None, [], []
    for f in files:
        for line in open(f):
            line = line.rstrip("\n")
            if line.startswith("INST"):
                mm = re.search(r"nr=(\d+) nc=(\d+) nobs=(\d+) norb=(\d+) wmax=(\d+)", line)
                inst = tuple(int(x) for x in mm.groups())
                ranges.append(re.search(r"orbits=(\[\d+,\d+\))", line).group(1))
            elif line.startswith("ORBIT"):
                o = int(line.split()[1])
                orbit_lines.setdefault(o, line)
            elif line.startswith("SOL"):
                sols.append(line)
            elif line.startswith("DONE"):
                dones.append(line)
    nr, nc, nobs, norb, wmax = inst
    status = "FOUND" if sols else "NONE"
    if status == "FOUND":
        # decide mode stops at the first solution: the root cases after it are not run
        assert len(files) == 1 and dones and dones[0].startswith("DONE FOUND"), files
        nodes = int(dones[0].split("nodes ")[1].split()[0])
        cpu = float(dones[0].split("cpu ")[1].rstrip("s"))
        covered = f"{len(orbit_lines)} (stopped at the first solution)"
    else:
        assert sorted(orbit_lines) == list(range(norb)), (c, b, R, W, len(orbit_lines), norb)
        assert all(" sols 0 " in line for line in orbit_lines.values())
        nodes = sum(int(line.split("nodes ")[1].split()[0]) for line in orbit_lines.values())
        cpu = sum(float(line.split("cpu ")[1].rstrip("s")) for line in orbit_lines.values())
        covered = f"{norb}/{norb}"
    name = f"{c}_{b}_R{R}_W{W}.txt"
    circ = {"A": "gross circuit A", "c16": "[[90,8,10]] c16", "u16": "[[90,8,10]] u16 (control)",
            "c11": "[[90,8,10]] c11 (period 11)", "c12": "[[90,8,10]] c12 (period 12)", "c13": "[[90,8,10]] c13 (period 13)",
            "u11": "gross circuit u11 (period 11)", "u11_control_p10": "gross period-10 control circuit"}[c]
    with open(OUT / name, "w") as fo:
        fo.write(f"# ccsearch decide W={W} on the SD6 DEM of {circ}, {b}-basis memory, R={R}\n")
        fo.write(f"# instance: {nr} detectors, {nc} mechanisms, {nobs} observables, {norb} root cases (orbits), "
                 f"max mechanism weight {wmax}\n")
        fo.write(f"# runs: {len(files)} process(es) over root-case ranges {' '.join(ranges)}; ORBIT lines merged, "
                 f"one per root case\n")
        for o in sorted(orbit_lines):
            fo.write(orbit_lines[o] + "\n")
        for s in sols:
            fo.write(s + "\n")
        fo.write(f"# result: {status}; root cases {covered}; nodes {nodes}; cpu {cpu:.1f} s\n")
    rows.append((c, b, R, W, status, norb, nodes, round(cpu, 1), name))
    print(name, status, covered, nodes, round(cpu, 1))

with open("release/zenodo/code/dcirc/reference_runs.tsv", "w") as f:
    f.write("# reference runs of ccsearch (decide mode) on the reference machine; logs in logs/dcirc/\n")
    f.write("circuit\tbasis\tR\tW\tstatus\troot_cases\tnodes\tcpu_s\tlog\n")
    for r in rows:
        f.write("\t".join(map(str, r)) + "\n")
print(len(rows), "runs")
