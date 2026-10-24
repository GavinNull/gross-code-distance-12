# Interleaving recovers the full circuit distance of the gross and [[90,8,10]] bivariate-bicycle codes

**Release v2.0** (paper PDF, arXiv source, full data/reproduction package): https://github.com/GavinNull/gross-code-distance-12/releases/tag/v2.0 — period-11 circuits; v1.0 (period 18) is superseded.

This repository contains the code, data pointers, paper source and the complete research record behind

> **Guancheng Pan**, *A single-ancilla syndrome circuit with circuit distance 12 for the gross code* (2026), arXiv:[to appear].

**Result.** The gross code [[144,12,12]] admits a single-ancilla, CNOT-based, interleaved syndrome-extraction circuit with circuit distance 12, under SD6 circuit-level noise, in both memory bases and for any number of rounds. This answers the open question in Sec. IV.3 of Strikis, Browne and Beverland (arXiv:2603.05481). The circuit has a period of 18 time steps per round, compared with 8 for the depth-8 circuits. Along the way we prove that their Fig. 12 circuit has circuit distance exactly 11, and that within colour-symmetric schedules of this class, 18 is the minimum period. The logical error rate of the new circuit is not evaluated.

**Where to look**

| What | Where |
|---|---|
| Paper source and figures | [`paper/draft.tex`](paper/draft.tex), [`paper/figures/`](paper/figures/); arXiv bundle in [`release/arxiv/`](release/arxiv/) |
| The period-18 circuit (Table I) | [`search/experiments/e024a/cs_P18_H24.json`](search/experiments/e024a/cs_P18_H24.json) |
| Self-contained data + reproduction package | built in `release/zenodo/` (code and docs in this repo; certificates/witnesses in the Zenodo archive, DOI: [to appear]) |
| One-command reproduction of every theorem | [`scripts/reproduce_theorems.sh`](scripts/reproduce_theorems.sh) (e.g. `--skip-base --with-gross12-p18`) |
| Independent audit reports | [`research/audits/`](research/audits/) |

**How this research was done (AI-native).** The project was run as an "AI-native" research workflow. AI agents (Claude, Anthropic) proposed hypotheses, wrote and ran the search and verification code, worked out the constructions and proofs, and wrote the paper drafts. Every claim was re-checked by a separate "auditor" agent using independently written code before it was accepted. The human author acted as PI: he set directions at decision gates, made all decisions and takes full responsibility for the content. The full record is public and mostly in Chinese: the state file [`research/STATE.md`](research/STATE.md), the hypothesis ledger, per-experiment journals in [`research/journal/`](research/journal/), audits, decisions and the agent rules in [`CLAUDE.md`](CLAUDE.md). It includes refuted hypotheses, mistakes and their corrections. Results not in the paper, such as the morphing-circuit analysis, are recorded there as work in progress.

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
