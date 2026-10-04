"""诊断：同一份论文参数程序，只换 relay_bp 的 seed（以及单改 γ0=0.1），走评估器（同样的 search split、速度预算）。
用来量化“逐 shot CPU 上限”对随机 γ 轨迹的惩罚（与调参无关的噪声底）。"""
import json
import sys

from search.experiments.e007 import common as C

C.use_temp_secret()
from evaluators.decoder_eval import evaluate_decoder  # noqa: E402
from evaluators.decoder_refs import program_for  # noqa: E402
from evaluators.tasks import get_task  # noqa: E402

task = sys.argv[1]
variants = json.loads(sys.argv[2])          # list of param overrides
base = get_task(task).decoder["reference"]["params"]
out = []
for v in variants:
    rep = evaluate_decoder(task, program_for("relay_bp", dict(base, **v)), split="search", shots=C.SHOTS[task],
                           submit=False, num_workers=3, with_features=False)
    d = {"override": v, "counts": rep.counts, "ref_counts": rep.reference["counts"], "speed": rep.speed,
         "sectors": {s: {k: st[k] for k in ("failures", "wrong", "timeout", "budget", "cpu_total_s")}
                     for s, st in rep.sectors.items()}, "P_any": rep.rates["P_any"]}
    print(json.dumps(d), flush=True)
    out.append(d)
json.dump(out, open(str(C.RESULTS / f"seedcheck-{task.split('-')[0]}.json"), "w"), indent=1)
