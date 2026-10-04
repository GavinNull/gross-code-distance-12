"""E-012：用两两兼容表回溯枚举六色着色的全部合法状态。lead。

合法性是两两约束（同一槽位不能有两个 CNOT 落在同一数据比特上），所以
proper(state) ⟺ 每个颜色类自身合法，且任意两个颜色类之间兼容。
"""
import itertools
import json

from search.noninterleaved.colour_search import order_terms
from search.noninterleaved.run import OUT, neighbours
from search.noninterleaved.six_colour import KIND, ctx


def slots(c, b):
    cx = ctx()
    o = order_terms(KIND, *cx["ok"][b])
    return {(neighbours(cx["code"], KIND, i, t), k) for i in range(cx["code"].n2) if cx["colour"][i] == c
            for k, t in enumerate(o)}


def main():
    cx = ctx()
    nok = len(cx["ok"])
    S = {(c, b): slots(c, b) for c in range(6) for b in range(nok)}
    # 每个颜色类自身合法：同一槽位不重复（集合大小 = 校验数 × 6）
    n_per = {c: sum(1 for i in range(cx["code"].n2) if cx["colour"][i] == c) for c in range(6)}
    self_ok = {(c, b) for (c, b), s in S.items() if len(s) == 6 * n_per[c]}
    comp = {}
    for (c1, b1), (c2, b2) in itertools.combinations(sorted(self_ok), 2):
        if c1 < c2:
            comp[(c1, b1, c2, b2)] = not (S[(c1, b1)] & S[(c2, b2)])
    states = []

    def rec(prefix):
        c = len(prefix)
        if c == 6:
            states.append(tuple(prefix))
            return
        for b in range(nok):
            if (c, b) not in self_ok:
                continue
            if all(comp[(pc, pb, c, b)] for pc, pb in enumerate(prefix)):
                rec(prefix + [b])

    rec([])
    print(f"self-proper per colour: {[sum(1 for b in range(nok) if (c, b) in self_ok) for c in range(6)]}")
    print(f"proper six-colour states: {len(states)}")
    (OUT / "e012_proper_states.json").write_text(json.dumps(states))


if __name__ == "__main__":
    main()
