#!/usr/bin/env python3
"""PreToolUse hook：保护“裁判”文件不被 agent 修改。

规则：
- evaluators/FROZEN 存在时，evaluators/ 下所有文件禁止 Edit/Write。
- research/leaderboard.jsonl 只能由评估器脚本追加，agent 永远不能直接编辑。
- 冻结标记和哈希清单本身永远不能由 agent 编辑。
解冻只能由人在终端里删除 evaluators/FROZEN。
"""
import json
import os
import sys

data = json.load(sys.stdin)
path = data.get("tool_input", {}).get("file_path") or data.get("tool_input", {}).get("notebook_path") or ""
root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
rel = os.path.relpath(os.path.realpath(path), os.path.realpath(root)) if path else ""

ALWAYS = {"research/leaderboard.jsonl", "evaluators/FROZEN", "evaluators/MANIFEST.sha256"}
frozen = os.path.exists(os.path.join(root, "evaluators", "FROZEN"))

reason = None
if rel in ALWAYS:
    reason = f"{rel} 只能由评估器脚本或人修改。"
elif frozen and rel.startswith("evaluators/"):
    reason = ("评估器已冻结（evaluators/FROZEN 存在），禁止修改 evaluators/。"
              "如果你认为评估器有 bug，把证据写进 research/evaluator_issues.md 交给人裁决。")

if reason:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason}}))
sys.exit(0)
