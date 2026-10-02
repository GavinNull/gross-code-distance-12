---
name: gate-review
description: 到达关卡（G0-G3）时写关卡报告并停下来等人决策。lead agent 判断已满足某个关卡的进入条件时使用。
---

# 关卡报告

关卡定义见 `CLAUDE.md`。

## 步骤
1. 对照进入条件逐条核对，并给出证据链接（journal、audit、leaderboard 行）。有任何一条不满足就不是关卡，回去继续做。
2. 写 `research/gates/G<n>-YYYY-MM-DD.md`：

```markdown
# G<n> 关卡报告
## 一句话结论
## 进入条件核对
| 条件 | 是否满足 | 证据 |
## 关键结果（数字 + 置信区间 + 对比 baseline）
## 已知弱点与风险（主动说，不要等人问）
## 需要人决定的事
1. ...（给出你的建议和理由）
## 如果批准，下一步计划
```

3. 在 `research/STATE.md` 的“待人决策”里加一条，指向这份报告。
4. 提交 git，然后**停止推进主线**。可以继续做不依赖本关卡决定的辅助工作（如文献调研）。

G1 的特殊要求：报告里必须包含 auditor 对评估器的攻击测试报告。人批准后由人执行
`uv run python scripts/freeze_evaluator.py freeze`，agent 不得自己冻结或解冻。
