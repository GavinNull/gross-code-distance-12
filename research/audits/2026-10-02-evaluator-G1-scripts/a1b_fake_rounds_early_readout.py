"""攻击 A1b：假轮次 + 数据比特提前读出（见 common.fake_rounds_early_readout）。
用法：uv run python a1b_fake_rounds_early_readout.py [d] [rounds] [--l2]
"""
import sys

from common import cons_for, fake_early_pair, honest

from evaluators.l0 import check_l0
from evaluators.l2 import DecoderConfig, StopRule, sample_l2


def main():
    d = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    R = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    code, data, fake = fake_early_pair(d, R)
    _, _, hon = honest(d, R)
    cons = cons_for(data, {**{f'f{b}': c for b, c in fake.items()}, **hon}, R, min_circuit_distance=d)
    rep = check_l0(fake, code, "both", cons)
    print(f"=== FAKE-EARLY: L0 passed={rep.passed} d_circ={rep.d_circ}")
    print("\n".join(l for l in rep.to_text().splitlines() if "[PASS]" not in l or "distance" in l))
    if "--l2" in sys.argv:
        stop = StopRule(max_shots=2_000_000, max_errors=1000, min_sector_errors=300, batch_size=10000)
        res = sample_l2(code, fake, data, p=0.005, rounds=R, boundary="paper",
                        decoder=DecoderConfig("pymatching"), seed=20261002, stop=stop, num_workers=3)
        print("=== FAKE-EARLY L2")
        print(res.summary())


if __name__ == "__main__":
    main()
