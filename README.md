# Minimum period of distance-preserving syndrome extraction for bivariate-bicycle codes

**Current version: revision P of the paper** (this repository, `main`). It supersedes Release
[v2.0](https://github.com/GavinNull/gross-code-distance-12/releases/tag/v2.0) (period-11 circuits) and v1.0 (period
18); a release with the paper PDF, arXiv source and data/reproduction package for this revision is in preparation.

> **Guancheng Pan**, *Minimum period of distance-preserving syndrome extraction for bivariate-bicycle codes* (2026), arXiv:[to appear].

**Result.** Single-ancilla syndrome-extraction circuits for the gross code [[144,12,12]] and the [[90,8,10]]
bivariate-bicycle code lose circuit distance unless overlapping X and Z checks are interleaved; how short a
distance-preserving circuit can be was open (Strikis, Browne and Beverland, arXiv:2603.05481). Within the class T(P)
of translation-invariant single-ancilla circuits of period P (all checks of one type share one CNOT timing), under
SD6 circuit-level noise, the shortest period with circuit distance equal to the code distance is **10 for the gross
code and 11 for [[90,8,10]]**, and the best circuit distance at every shorter period is known:

| period P | 8 | 9 | 10 | 11 |
|---|---|---|---|---|
| gross, best d_circ in T(P) | 11 (g8; IBM's depth-8 circuit: 10) | 11 (g9) | **12** (g10) | 12 (u11) |
| [[90,8,10]], best d_circ in T(P) | 8 (IBM's depth-8 circuit) | 9 (b9) | 9 (b10) | **10** (c11) |

The circuits reach these values for every number of rounds and both memory bases; the impossibility results hold for
sufficiently many rounds. The mechanism is an integer cochain of round offsets between overlapping X and Z checks: a
circuit can be re-timed into a non-interleaved one exactly when the cochain is a coboundary, a light extended-code
logical is blocked when difference constraints along its hooks form a negative cycle, and at period 8 a flat
two-qubit hook costs one unit of distance because every pair of check qubits lies in a minimum-weight logical. The
price is idling: under standard idle noise the full-distance circuits have a higher logical error rate than IBM's
depth-8 circuits at all directly resolvable error rates.

**Where to look**

| What | Where |
|---|---|
| Paper source and figure | [`paper/draft.tex`](paper/draft.tex), [`paper/figures/fig1_P.pdf`](paper/figures/fig1_P.pdf); arXiv bundle in [`release/arxiv/`](release/arxiv/) |
| g10, gross, period 10, d_circ = 12 (Table II) | [`search/experiments/e040/g10_d12_spec.json`](search/experiments/e040/g10_d12_spec.json) |
| c11, [[90,8,10]], period 11, d_circ = 10 (Table II) | [`search/experiments/e030/c11_spec.json`](search/experiments/e030/c11_spec.json) |
| u11, gross, period 11, d_circ = 12 | [`search/experiments/e032/u11_spec.json`](search/experiments/e032/u11_spec.json) |
| g8 (gross, P = 8, 11), g9 (gross, P = 9, 11), b9, b10 ([[90,8,10]], P = 9, 10, 9) | [`search/experiments/e040/g8_d11_spec.json`](search/experiments/e040/g8_d11_spec.json), [`search/experiments/e043/`](search/experiments/e043/) |
| Impossibility proofs (class enumeration, fault patterns, CNFs, DRAT checks) and the g10 certificates | code in [`search/experiments/e040/`](search/experiments/e040/), [`e042/`](search/experiments/e042/), [`e043/`](search/experiments/e043/); journals in [`research/journal/`](research/journal/) (E-040 to E-045) |
| Independent audit reports | [`research/audits/`](research/audits/) (2026-10-29 to 2026-11-04 for this revision) |
| Self-contained data + reproduction package | built in `release/zenodo/` (version 3.0; circuits, lists, patterns, certificate records and reproduction scripts; DOI: [to appear]) |

**How this research was done (AI-native).** The project was run as an "AI-native" research workflow. AI agents (Claude, Anthropic) proposed hypotheses, wrote and ran the search and verification code, worked out the constructions and proofs, and wrote the paper drafts. Every claim was re-checked by a separate "auditor" agent using independently written code before it was accepted. The human author, Guancheng Pan, acted as PI, set directions at decision gates, made all decisions and takes full responsibility for the content. The full record is public and mostly in Chinese: the state file [`research/STATE.md`](research/STATE.md), the hypothesis ledger, per-experiment journals in [`research/journal/`](research/journal/), audits, decisions and the agent rules in [`CLAUDE.md`](CLAUDE.md). It includes refuted hypotheses, mistakes and their corrections. Results not in the paper, such as the morphing-circuit analysis, are recorded there as work in progress.

**Licence.** Code: MIT ([`LICENSE`](LICENSE)). Text, figures and data: CC-BY 4.0.

---

# qec-ai-search

用 AI（LLM 进化搜索 / 强化学习）搜索新的量子纠错码与容错电路。

课题的完整说明见 [docs/课题说明.md](docs/课题说明.md)，里面有背景、子方向、路线图、评估设计和参考文献。

本项目采用 **AI 原生**研究流程：agent 做研究，人当 PI 在关卡拍板。流程见 [docs/AI原生研究流程.md](docs/AI原生研究流程.md)，agent 的规则见 [CLAUDE.md](CLAUDE.md)，当前进度见 [research/STATE.md](research/STATE.md)。

## 环境

- Python 3.12（uv 管理，虚拟环境在 `.venv/`）
- 核心依赖：stim / sinter / pymatching / ldpc / stimbposd / beliefmatching / galois / anthropic / gymnasium / torch

```bash
uv sync                               # 安装或更新依赖
uv run python scripts/check_env.py    # 环境自检
uv run jupyter lab                    # 打开 notebook（kernel 选 qec-ai-search）
```

LLM 搜索需要 API key：把 `.env.example` 复制成 `.env`，然后填入 key。

## 目录

| 目录 | 用途 |
|---|---|
| `docs/` | 课题说明、AI 原生流程说明 |
| `research/` | 研究状态、决定、假设、实验日志、审计、关卡报告 |
| `.claude/` | agent 角色、skill、评估器保护 hook |
| `baselines/` | 复现文献中的标准码和标准调度（P0） |
| `evaluators/` | 分层评估器 L0 合法性、L1 代理、L2 sinter（P1） |
| `search/llm_evolve/` | LLM 进化搜索框架 |
| `search/rl/` | 强化学习环境和策略 |
| `experiments/` | 每次实验的配置（yaml） |
| `results/` | 实验输出（不进 git） |
| `notebooks/` | 分析和画图 |
| `references/` | 论文 PDF 和笔记 |
| `scripts/` | 工具脚本 |
