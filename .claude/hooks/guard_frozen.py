#!/usr/bin/env python3
"""PreToolUse hook：保护“裁判”文件不被 agent 修改（Edit / Write / NotebookEdit）。

规则：
- research/leaderboard.jsonl 只能由评估器（evaluators.pipeline）追加，agent 永远不能直接编辑。
- 冻结标记与哈希清单（evaluators/FROZEN、evaluators/MANIFEST.sha256、research/evaluator_freeze.*）永远不能由 agent 编辑。
- evaluators/FROZEN 存在时：evaluators/ 下所有文件，以及冻结清单里的其他文件（冻结脚本、本 hook、pyproject.toml、
  uv.lock、评估器测试；列表见 scripts/freeze_evaluator.py 的 EXTRA_FILES，以 research/evaluator_freeze.sha256
  为准）禁止编辑。
解冻只能由人在终端里删除 evaluators/FROZEN。

评估器 v2（auditor G1 F1）：路径先解析符号链接（realpath），再做**大小写不敏感**比较（macOS APFS 默认不区分大小写，
`Evaluators/l0.py` 与 `evaluators/l0.py` 是同一个文件）。
局限：本 hook 只拦截文件编辑工具；Bash 里的写操作不经过它（F2）。冻结后的真正保护是 PI 用文件系统权限锁住
evaluators/（evaluators/README.md §10）和 `scripts/freeze_evaluator.py verify`。
"""
import json
import os
import sys

FALLBACK_EXTRA = (
    "scripts/freeze_evaluator.py", ".claude/hooks/guard_frozen.py", "pyproject.toml", "uv.lock",
    "tests/conftest.py", "tests/memory_builder.py", "tests/schedule_helpers.py", "tests/test_candidate.py",
    "tests/test_codes.py", "tests/test_distance.py", "tests/test_freeze.py", "tests/test_g1_attacks.py",
    "tests/test_l0.py", "tests/test_l2.py", "tests/test_leaderboard.py", "tests/test_noise.py",
    "tests/test_pipeline.py", "tests/test_stats.py",
)
ALWAYS = {"research/leaderboard.jsonl", "evaluators/frozen", "evaluators/manifest.sha256",
          "research/evaluator_freeze.json", "research/evaluator_freeze.sha256"}


def _norm(p: str) -> str:
    return p.replace(os.sep, "/").casefold()


def decide(data: dict, root: str) -> str | None:
    """返回拒绝理由（None = 放行）。"""
    ti = data.get("tool_input", {}) or {}
    path = ti.get("file_path") or ti.get("notebook_path") or ""
    if not path:
        return None
    if not os.path.isabs(path):
        path = os.path.join(data.get("cwd") or os.getcwd(), path)
    real_root = os.path.realpath(root)
    real = os.path.realpath(path)
    rel = os.path.relpath(real, real_root)
    nrel = _norm(rel)
    # 大小写不敏感地判断是否在项目内
    if nrel.startswith("../") or nrel == "..":
        nroot, nreal = _norm(real_root), _norm(real)
        if nreal.startswith(nroot + "/"):
            nrel = nreal[len(nroot) + 1:]
        else:
            return None
    if nrel in ALWAYS:
        return f"{rel} 只能由评估器脚本或人修改。"
    frozen = any(os.path.exists(os.path.join(real_root, d, "FROZEN")) for d in ("evaluators",))
    if not frozen:
        return None
    protected = {_norm(f) for f in FALLBACK_EXTRA}
    ext = os.path.join(real_root, "research", "evaluator_freeze.sha256")
    try:
        with open(ext, encoding="utf-8") as f:
            for line in f:
                if "  " in line:
                    protected.add(_norm(line.rstrip("\n").split("  ", 1)[1]))
    except OSError:
        pass
    try:
        hardlinked = os.path.isfile(real) and os.stat(real).st_nlink > 1
    except OSError:
        hardlinked = False
    if hardlinked:
        return f"评估器已冻结：{rel} 是硬链接（可能指向受保护的文件），禁止编辑。"
    if nrel.startswith("evaluators/") or nrel in protected:
        return ("评估器已冻结（evaluators/FROZEN 存在），禁止修改 evaluators/ 及冻结清单中的文件"
                f"（{rel}）。如果你认为评估器有 bug，把证据写进 research/evaluator_issues.md 交给人裁决。")
    return None


def main() -> int:
    data = json.load(sys.stdin)
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    reason = decide(data, root)
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
