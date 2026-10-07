# 负面结论的见证存档

`results/` 不进 git，所以支撑负面结论的见证复制到这里。每行一个被淘汰的块顺序或状态，`witness` 字段是标签形式：
`["q", j]` 表示数据比特 j，`["r", [j1, j2, ...]]` 表示覆盖这些数据比特的残余错误。复查：

```bash
PYTHONPATH=. uv run python search/experiments/e015/verify_witnesses.py
```

（脚本读取 `results/E-015-bb-generalization/heur_*_wit.jsonl`；从这里复制回去即可。）

- `e015/`：E-015 中项目 (20,3) [[120,8,12]]（target 11）、[[124,10,10]]（target 10）、[[140,6,14]]（target 13）、WM[[180,8,16]]（target 16）
  两色 LRC 的全部淘汰见证。2026-10-07 复查：320 个全部 H·x = 0 且 L·x ≠ 0，失败 0。
- gross 两色的见证由 auditor 存档：`research/audits/2026-10-05-E-014-E-015-scripts/` 及 `results/E-014-E-015-audit/b8_gross_X_*.json`。
