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
