"""攻击 A1：“假轮次”——1 轮真提取 + 反复重测同一批辅助比特，冒充 rounds 轮。

用法：uv run python research/audits/2026-10-02-evaluator-G1-scripts/a1_fake_rounds.py [d] [rounds] [--l2]
"""
import sys

from common import cons_for, fake_pair, honest

from evaluators.l0 import check_l0
from evaluators.l2 import DecoderConfig, StopRule, sample_l2


def main():
    d = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    R = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    do_l2 = "--l2" in sys.argv

    code, data, fake = fake_pair(d, R)
    _, _, hon = honest(d, R)
    print(f"fake Z circuit: {fake['Z'].num_ticks} ticks, honest: {hon['Z'].num_ticks} ticks")
    cons = cons_for(data, {**{f'f{b}': c for b, c in fake.items()}, **{f'h{b}': c for b, c in hon.items()}}, R,
                    min_circuit_distance=d)
    for name, circs in (("honest", hon), ("FAKE", fake)):
        rep = check_l0(circs, code, "both", cons)
        print(f"=== {name}: L0 passed={rep.passed} d_circ={rep.d_circ}")
        print(rep.to_text())

    if do_l2:
        stop = StopRule(max_shots=1_000_000, max_errors=1000, min_sector_errors=300, batch_size=5000)
        for name, circs in (("honest", hon), ("FAKE", fake)):
            res = sample_l2(code, circs, data, p=0.005, rounds=R, noise_model="sd6", boundary="paper",
                            decoder=DecoderConfig("pymatching"), seed=20261002, stop=stop, num_workers=3)
            print(f"=== {name} L2")
            print(res.summary())


if __name__ == "__main__":
    main()
