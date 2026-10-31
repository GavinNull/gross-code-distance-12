"""E-044 (4): IBM gross, lam1 (= evaluator sd6), p = 2e-3, R = 12, BP-OSD IBM parameters -- the task on which E-033
(Z 15/45481) and the E-040 audit (Z 2/60000) disagree.  Same circuit/DEM/decoder (strong_ids reproduced, see
journal).  Preset shots, no stopping on errors; sinter seeds itself from OS entropy (as in both earlier runs).
  uv run python -m search.experiments.e044.anomaly run   ;   ... summary"""
import sys

import sinter

from search.experiments.e044.common import IBM_BPOSD, OUT, noisy

CSV = OUT / "anomaly_ibm_2e-3.csv"
SHOTS = {"Z": 100000, "X": 50000}


def run():
    from stimbposd import SinterDecoder_BPOSD
    tasks = [sinter.Task(circuit=noisy("ibm", b, 0.002, "lam1"), json_metadata=dict(circ="ibm", basis=b, p=0.002, R=12, noise="lam1", exp="E-044"),
                         collection_options=sinter.CollectionOptions(max_shots=n)) for b, n in SHOTS.items()]
    sinter.collect(num_workers=1, tasks=tasks, decoders=["bposd"],
                   custom_decoders={"bposd": SinterDecoder_BPOSD(**IBM_BPOSD)},
                   save_resume_filepath=str(CSV), max_errors=10**9)


def summary():
    agg = {}
    for s in sinter.read_stats_from_csv_files(str(CSV)):
        a = agg.setdefault(s.json_metadata["basis"], [0, 0, 0.0])
        a[0] += s.shots; a[1] += s.errors; a[2] += s.seconds
    for b, (n, k, sec) in agg.items():
        print(b, n, k, round(sec))


if __name__ == "__main__":
    run() if sys.argv[1] == "run" else summary()
