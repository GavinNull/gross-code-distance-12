# search/llm_evolve：LLM 进化搜索框架

FunSearch / AlphaEvolve 风格的内循环：LLM 改写程序，评估器打分，岛模型做进化选择。
框架**与具体问题解耦**，问题只通过 `Problem` 接口接入；框架不 import 任何评估器内部函数。

同一个接口下还有一个**不用 LLM** 的模拟退火对照（`baseline.py`），评估次数口径一致，
用来回答“LLM 相对经典启发式的增量在哪里”（CLAUDE.md 铁律 5）。

## 架构

```
                 ┌──────────────────────── EvolutionEngine (engine.py) ────────────────────────┐
                 │                                                                              │
 Problem ──────▶ │  ProgramDatabase (database.py)        build_prompt (prompt.py)               │
 (problem.py)    │  ┌ island 0 ┐ ┌ island 1 ┐ …   ──▶  任务说明 + 2-3 个父代(分数+诊断)  ──┐      │
  description()  │  └──────────┘ └──────────┘          按分数升序，最好的在最后           │      │
  seed_programs()│     ▲   每 reset_interval 次评估                                        ▼      │
  evaluate(src)  │     │   最差岛 ← 最好岛的精英             LLMClient (llm.py)                  │
       ▲         │     │                                  ├ AnthropicClient  快/强模型按比例    │
       │         │     │                                  └ MockClient       离线、确定性       │
       │         │  add(valid)                                      │ 回复                        │
       │         │     │                                            ▼                             │
       │         │  CachedEvaluator (runlog.py)  ◀── extract_program：取最后一个定义了目标函数的代码块 │
       └─────────┼── 规范化源码哈希去重；命中缓存不再评估、不计评估次数                              │
                 │                                                                              │
                 │  预算：token_budget（预扣 prompt 估计 + max_tokens）/ max_evals / max_llm_calls │
                 │  日志：results/<run-id>/{config,state,summary}.json, llm_calls.jsonl,          │
                 │        evaluations.jsonl, best_program.py                                     │
                 └──────────────────────────────────────────────────────────────────────────────┘

 Problem.evaluate 内部（由问题实现，框架不关心）：
   run_in_sandbox(src, func, calls)  ──▶  python -I -B _sandbox_runner.py（临时目录、超时、内存、audit hook）
        └─ 只返回候选函数的 JSON 输出；校验与打分在父进程里由问题代码完成
```

| 文件 | 内容 |
|---|---|
| `problem.py` | `Problem`、`EvalResult`、可选的 `SolutionSpace` 协议 |
| `sandbox.py` / `_sandbox_runner.py` | 子进程执行候选程序 |
| `database.py` | `ProgramDatabase`（岛模型、选择、重置）、`normalize_source` / `program_hash` |
| `prompt.py` | `build_prompt`、`extract_program` |
| `llm.py` | `LLMClient` 协议、`AnthropicClient`、`MockClient`、费用估算 |
| `engine.py` | `EvolutionConfig`、`EvolutionEngine`（主循环、预算、断点续跑） |
| `baseline.py` | `AnnealingSearch` + `ProgramMutator` / `SolutionSpaceMutator` |
| `mutation.py` | AST 级数值字面量 / 运算符变异（Mock 与基线共用） |
| `runlog.py` | JSONL 日志、原子写断点、`CachedEvaluator`、`best_so_far_curve` |
| `toy.py` | 玩具问题 `CircleTSPProblem`（已知最优解） |
| `decoder_problem.py` | 解码器问题 `DecoderProblem`（H-005，见下文“解码器问题”），评估全部交给评估器的公开入口 |
| `cli.py` | 命令行入口 |

## 接口

```python
class Problem(ABC):
    name: str
    function_name: str                       # 候选程序必须定义的入口函数
    def description(self) -> str             # 放进 prompt 的任务说明（签名、约束、可用库）
    def seed_programs(self) -> list[str]     # ≥1 个合法种子
    def evaluate(self, program_src: str) -> EvalResult
    def fingerprint(self) -> dict            # 续跑时校验是不是同一个问题（建议加上实例参数）

@dataclass
class EvalResult:
    valid: bool          # invalid 的程序不进数据库
    score: float         # 越大越好；valid 时必须有限
    metrics: dict        # 任意 JSON 指标，写日志
    diagnostics: str     # 给 LLM 看的诊断（会被截断到 max_diag_chars）
```

约定：

* `evaluate` 必须**确定性**（同一源码同一结果）。需要随机性（例如 sinter 采样）时由问题固定种子。
  否则哈希缓存、可复现性和断点续跑的语义都不成立。
* `evaluate` 不应抛异常；框架兜底把异常记为 `valid=False, metrics.evaluator_error=True`
  （这通常意味着评估器 bug，应按 CLAUDE.md 记进 `research/evaluator_issues.md`）。
* `evaluate` 会被线程池并发调用（`concurrency`），实现须线程安全（`run_in_sandbox` 本身是）。
* 可选：实现 `SolutionSpace`（`initial_solution(rng)` / `neighbor(sol, rng)` / `solution_to_program(sol)`，
  解须可 JSON 序列化），经典基线就能直接在解空间上退火，且仍然走同一个 `evaluate`。

## 用法

```python
from search.llm_evolve import EvolutionEngine, EvolutionConfig, MockClient, AnthropicClient
from search.llm_evolve.toy import CircleTSPProblem

problem = CircleTSPProblem()
cfg = EvolutionConfig(run_id="toy-mock", seed=0, max_evals=200, token_budget=2_000_000)
summary = EvolutionEngine(problem, MockClient(presets=problem.mock_presets()), cfg).run()

# 断点续跑（可调大预算；其他配置不允许改）
summary = EvolutionEngine.resume("toy-mock", problem, MockClient(...), max_evals=400).run()
```

命令行：

```bash
uv run python -m search.llm_evolve.cli llm    --problem search.llm_evolve.toy:CircleTSPProblem --client mock --run-id toy-mock --max-evals 200
uv run python -m search.llm_evolve.cli anneal --problem search.llm_evolve.toy:CircleTSPProblem --mutator program  --run-id toy-sa  --max-evals 200
uv run python -m search.llm_evolve.cli anneal --problem search.llm_evolve.toy:CircleTSPProblem --mutator solution --run-id toy-sa2 --max-evals 200
uv run python -m search.llm_evolve.cli compare results/toy-mock results/toy-sa --at 50 100 200
uv run pytest tests -q -k llm_evolve
```

`--client anthropic` 会真实调用 API、产生费用，需要环境变量 `ANTHROPIC_API_KEY`（代码不读 `.env`）。

## 如何接入新问题

1. 写一个 `Problem` 子类（放在问题自己的模块里，不要放进本目录）。
2. `description()`：写清函数签名、输入的数据结构、输出格式、硬约束、可用库、时间限制、分数含义。
   描述越精确，LLM 产出的合法率越高。
3. `seed_programs()`：至少一个合法且“有改进空间”的种子（通常就是已知 baseline 的程序化表达）。
4. `evaluate()`：
   1. `run_in_sandbox(src, self.function_name, calls, timeout_s=..., mem_mb=...)` 拿到候选函数的**纯数据输出**；
   2. 在父进程里校验输出（格式、L0 合法性），不合法返回 `EvalResult.invalid(诊断)`；
   3. 调用评估器的**公开入口**打分，把对 LLM 有用的信息写进 `diagnostics`。
   候选程序永远拿不到评估器对象，只交出数据，所以“伪造分数”等价于“真的输出那个解”。
5. 可选：实现 `SolutionSpace`，给经典基线一个直接解空间。
6. 写 `experiments/<id>.yaml`：问题参数、`EvolutionConfig`、预算、种子、复现命令。
7. 对照：同样的 `max_evals` 跑 `AnnealingSearch`（`ProgramMutator` 和/或 `SolutionSpaceMutator`），
   用 `best_so_far_curve` / `cli compare` 在相同评估次数下比较。

## 解码器问题（`DecoderProblem`，H-005）

```python
from search.llm_evolve import EvolutionEngine, EvolutionConfig, MockClient, AnnealingSearch, AnnealingConfig, SolutionSpaceMutator
from search.llm_evolve.decoder_problem import DecoderProblem

problem = DecoderProblem("bb72-dec-p3e-3", shots=20000, num_workers=3)     # mp_rule 任务："bb72-mp-p3e-3"
cfg = EvolutionConfig(run_id="dec-mock", seed=0, max_evals=20, concurrency=1, batch_size=2)
EvolutionEngine(problem, MockClient(presets=problem.mock_presets()), cfg).run()
AnnealingSearch(problem, SolutionSpaceMutator(problem), AnnealingConfig(run_id="dec-sa", max_evals=20)).run()
```

- 评估：`evaluators.decoder_eval.evaluate_decoder(task, src, split="search", submit=False)`（评估器的公开入口；候选在评估器的
  沙箱里运行，这里不执行候选代码）。分数 = −P_any（搜索集），超时 / 异常 / 格式错误的 shot 已按失败计入；搜索阶段永不写榜，
  正式分数只在留出集上由评估器给出（`split="holdout"`，需要 PI 的密钥文件）。
- 诊断（给 LLM）：失败计数与区间、每类失败的分解、CPU/shot（均值 / 中位 / p99 / 最大）与参考之比、**与 Relay-BP 失败的重叠**
  （双方都错 / 只有候选错 / 只有参考错）、失败 shot 的特征（syndrome 权重分布、按轮次的 detector 触发比例、按权重分箱的
  “只有候选错”）。
- 种子程序：Relay-BP（论文参数）与一个弱化的 Relay-BP（S=1、30 段）；description 给出接口、可用库、速度预算，以及
  “BP + 后处理”模板（`BP_POSTPROCESS_TEMPLATE`，只是模板，评估器始终接收完整程序）。mp_rule 任务的种子是 Relay 规则。
- 经典对照（铁律 5）：`SolutionSpace` = Relay-BP 类参数空间（γ0、γ 区间下端与宽度、第 0 段迭代数、每段迭代数、段数、S），
  解经 `solution_to_program` 变成同一个评估入口的程序。
- 每次评估本身已用 `num_workers`（≤3）个进程；`evaluate` 内部加锁串行化，引擎的 `concurrency` 建议设 1。
- 速度预算按 CPU 时间判定，机器负载会让临界 shot 的超时判定抖动，所以 `evaluate` 不是严格确定性的（缓存按源码哈希，
  同一源码只评一次）。
- 测试：`tests/test_llm_evolve_decoder.py`（自检任务的公开 split，MockClient 端到端 + 退火，约 1.5 分钟）。

## 预算控制

| 项 | 含义 | 行为 |
|---|---|---|
| `token_budget` | 输入 + 输出 token 总数（输出含 thinking；输入含 cache 读写） | 每次调用**前**预扣 `ceil(len(prompt)/2.5) + max_tokens`，放不下就不发起调用；因此实际用量不会超过预算（除非 prompt 估计严重偏低） |
| `max_evals` | 唯一评估次数（含种子；缓存命中不计） | 每个 batch 规划的调用数 ≤ 剩余评估次数，不会超出 |
| `max_llm_calls` | LLM 调用次数（可选） | 同上 |
| `max_consecutive_llm_errors` | 连续 API 错误次数 | 达到即停止（网络断、key 失效时不会空转） |

预算耗尽时：`stop_reason` 写入 `summary.json` 和 `state.json`，断点已保存；用 `resume(..., token_budget=更大)`
即可继续。`summary.json` 里有按模型价格表估算的美元费用 `usage.cost_usd_est`（价格表在 `llm.py`，仅作参考，
预算按 token 执行）。CLAUDE.md 铁律 8 要求预算写进 `experiments/<id>.yaml`，运行脚本应从那里读这些字段。

## 可复现与断点续跑

* 所有随机决策（选岛、选父代、快/强模型、每次调用的 `request.seed`）来自 `random.Random(config.seed)`。
* 每个 batch 结束后原子写 `state.json`：RNG 状态、数据库、哈希缓存、计数器、预算用量，以及两个 JSONL
  的**字节偏移**。崩溃后续跑先把 JSONL 截断到偏移处（丢掉未提交的半个 batch），再从同一 RNG 状态重做。
  测试 `test_crash_and_resume_matches_uninterrupted_run` 验证：MockClient 下“崩溃 + 续跑”与“不中断”
  的日志逐条一致。
* 真实 API 没有采样种子（且这些模型不接受 temperature），重跑不会得到相同回复；可复现性依赖
  `llm_calls.jsonl` 里完整记录的 prompt / 回复 / 程序 / 评估结果——任何结果都可以从日志里的源码重新评估。
* 因“预算耗尽”而停、再调大预算续跑的运行，与一开始就给大预算的运行**不保证**逐条一致（batch 边界不同）。

## 隔离：做到了什么，做不到什么

做到（`sandbox.py`）：

* `python -I -B` 子进程：忽略 `PYTHON*` 环境变量、用户 site，脚本目录/cwd 不在 `sys.path`，不能直接 `import evaluators`；
* 环境变量白名单：子进程**拿不到** `ANTHROPIC_API_KEY` 等任何密钥；
* 每次评估一个全新的临时目录作为 cwd 和 HOME，结束后删除；
* 墙钟超时后 `SIGKILL` 整个进程组；另设 `RLIMIT_CPU`、`RLIMIT_FSIZE`、禁 core dump；
* 内存：先尝试 `RLIMIT_AS`；失败时（**macOS 不支持 RLIMIT_AS/RLIMIT_DATA，本机就是这种情况**）
  启用峰值 RSS 看门狗线程，超限即 `os._exit`；
* Python audit hook：禁止写临时目录以外的任何路径；禁止读/列项目目录（venv 与标准库除外，因此评估器源码读不到）；
  禁止 socket、subprocess、`os.system`、`fork`/`exec`/`posix_spawn`、`ctypes` 动态加载、`os.kill`；
* 候选程序的 `print` 被重定向到 stderr，不能污染结果通道；traceback 截断后作为诊断。

做不到（如实说明）：

* **没有真正的网络隔离、也没有内核级文件系统隔离。** audit hook 是 Python 层的拦截，运行在同一进程里，
  原则上可以被 C 扩展（例如 numpy 以外的已编译模块、`_posixsubprocess` 之类的内部模块）或解释器漏洞绕过。
  它防的是“LLM 写出不小心的/投机取巧的代码”，不是对抗性攻击者。要更强隔离需要容器 / `sandbox-exec`
  （macOS，已废弃）/ nsjail / 独立虚拟机，目前未做。
* audit hook 拦截了读项目目录，但**不拦截读家目录等其他位置**；能读到的内容虽然无法直接走网络外传，但可能通过函数返回值 / 诊断进入日志，进而进入下一轮发给 LLM API 的 prompt。
* macOS 上的内存限制是“事后”的：看门狗每 20 ms 查一次峰值 RSS，一次性的大分配会先发生再被杀，
  瞬时内存可能远超上限（测试中 2 GB 分配在 256 MB 限制下被杀）。Linux 上 `RLIMIT_AS` 是硬限制。
* 不限制 CPU 核数（已设 `OMP_NUM_THREADS=1` 等，但候选程序自己开线程不受限）；没有磁盘配额以外的 I/O 限制。
* 候选程序可以无限递归、做大量计算——只能靠超时兜底。
* 每次评估都新起一个解释器并预导入 numpy，固定开销约 50 ms（玩具问题里占主要时间）。

## 已知局限（框架本身）

* 去重只做 AST 规范化（去注释/空白/docstring），不做变量重命名等价，语义相同但写法不同的程序会被重复评估。
* 多样性度量是 token 集合 Jaccard，比较粗；没有 FunSearch 那种按“分数签名”聚类。
* 评估是单层的：`evaluate` 返回一个分数。L0/L1/L2 分层（只给精英跑昂贵 L2）目前需要问题在 `evaluate` 内部自己实现
  （例如 L1 分数达标才跑小规模 L2），框架还没有“对精英重评估”的钩子。
* 同步 batch：一个 batch 里最慢的 LLM 调用决定 batch 时长；没有异步流水线。
* `MockClient` 只用于验证管道（变异、缓存、预算、续跑），它在玩具问题上的分数**不说明任何关于 LLM 的事情**。
