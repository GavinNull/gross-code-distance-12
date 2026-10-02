"""E-001：旋转表面码 memory 实验 baseline（stim 生成电路 + sinter 采样 + pymatching 解码）。

    uv run python -m baselines.surface --config experiments/E-001-surface-baseline.yaml
"""
import argparse
import json
from pathlib import Path

import sinter
import stim
import yaml


def make_circuit(d: int, rounds: int, p: float) -> stim.Circuit:
    # 均匀电路级去极化：Clifford 门后、每轮数据比特、测量前、复位后均为 p
    return stim.Circuit.generated(
        "surface_code:rotated_memory_z",
        distance=d,
        rounds=rounds,
        after_clifford_depolarization=p,
        before_round_data_depolarization=p,
        before_measure_flip_probability=p,
        after_reset_flip_probability=p,
    )


def per_round(p_shot: float, rounds: int) -> float:
    # 每轮逻辑错误率：1 - (1 - 2·p_shot)^(1/rounds)，再除以 2（按独立翻转模型换算）
    return (1 - (1 - 2 * p_shot) ** (1 / rounds)) / 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", help="输出目录，默认 results/<id>。注意：目录里已有 stats.csv 时 sinter 会续跑而不是重算，独立复现请指定新目录")
    args = ap.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text())
    out = Path(args.out) if args.out else Path("results") / cfg["id"]
    out.mkdir(parents=True, exist_ok=True)

    max_errors, max_shots = cfg["max_errors"], cfg.get("max_shots", 20_000_000)
    tasks = []
    for d in cfg["distances"]:
        rounds = d if cfg["rounds"] == "d" else int(cfg["rounds"])
        for p in cfg["noise"]["p"]:
            tasks.append(sinter.Task(
                circuit=make_circuit(d, rounds, p),
                json_metadata={"d": d, "rounds": rounds, "p": p},
            ))

    stats = sinter.collect(
        num_workers=cfg["budget"]["num_workers"],
        tasks=tasks,
        decoders=[cfg["decoder"]],
        max_errors=max_errors,
        max_shots=max_shots,
        save_resume_filepath=str(out / "stats.csv"),
        print_progress=False,
    )

    rows = []
    for s in sorted(stats, key=lambda s: (s.json_metadata["d"], s.json_metadata["p"])):
        m = s.json_metadata
        fit = sinter.fit_binomial(num_shots=s.shots, num_hits=s.errors, max_likelihood_factor=1000)
        rows.append({
            "d": m["d"], "rounds": m["rounds"], "p": m["p"],
            "shots": s.shots, "errors": s.errors,
            "p_shot": fit.best, "p_shot_lo": fit.low, "p_shot_hi": fit.high,
            "p_round": per_round(fit.best, m["rounds"]),
            "p_round_lo": per_round(fit.low, m["rounds"]),
            "p_round_hi": per_round(fit.high, m["rounds"]),
            "seconds": s.seconds,
        })
    (out / "summary.json").write_text(json.dumps(rows, indent=2))
    for r in rows:
        print(f"d={r['d']} p={r['p']:.3f} shots={r['shots']:>9} errors={r['errors']:>4} "
              f"p_round={r['p_round']:.2e} [{r['p_round_lo']:.2e}, {r['p_round_hi']:.2e}]")


if __name__ == "__main__":
    main()
