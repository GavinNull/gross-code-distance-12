"""攻击 F：冻结机制（scripts/freeze_evaluator.py + .claude/hooks/guard_frozen.py）。
全部在临时目录的项目副本里做，不碰真实的 evaluators/。

  F1  hook 的路径比较区分大小写，macOS（APFS 默认不区分大小写）上 "Evaluators/l0.py" 绕过
  F2  hook 只拦 Edit/Write/NotebookEdit，Bash 写文件不经过它（这里只演示 hook 不处理 Bash 工具的输入）
  F3  哈希只覆盖 evaluators/**/*.py：__pycache__ 里伪造的 .pyc（与源文件 mtime/size 一致）改变行为，
      verify 仍通过、leaderboard 记录的哈希与 FROZEN 一致
  F4  同目录下的扩展模块（.so）优先于 .py 被导入，且不在哈希里（只演示导入优先级，用一个 .py 以外的文件名检查覆盖面）
  F5  scripts/freeze_evaluator.py 自身不在哈希里：leaderboard 用它算哈希，改它的 combined_hash 即可让任何
      被改过的评估器报告“与 FROZEN 一致”
  F6  依赖库版本（stim/ldpc/pymatching/sinter，pyproject 未锁版本）不在哈希里

用法：uv run python a_freeze.py
"""
import importlib.util
import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def copy_project() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="g1freeze_")).resolve()
    for d in ("evaluators", "scripts", ".claude"):
        shutil.copytree(ROOT / d, tmp / d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "MANIFEST.sha256",
                                                                           "FROZEN"))
    return tmp


def run(cmd, cwd, env=None, inp=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env, input=inp)


def main():
    proj = copy_project()
    print("copy at", proj)
    out = run([sys.executable, "scripts/freeze_evaluator.py", "freeze"], proj)
    print("freeze:", out.stdout.strip())

    # F1 / F2: hook
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(proj))
    for p in ("evaluators/l0.py", "Evaluators/l0.py", "EVALUATORS/noise.py", "research/Leaderboard.jsonl",
              "evaluators/FROZEN", "Evaluators/FROZEN"):
        payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(proj / p)}})
        o = run([sys.executable, str(proj / ".claude/hooks/guard_frozen.py")], proj, env, payload)
        dec = json.loads(o.stdout)["hookSpecificOutput"]["permissionDecision"] if o.stdout.strip() else "allow"
        print(f"F1 hook decision for Edit {p!r}: {dec}  (exists: {(proj / p).exists()})")
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "sed -i '' s/x/y/ evaluators/l0.py"}})
    o = run([sys.executable, str(proj / ".claude/hooks/guard_frozen.py")], proj, env, payload)
    print("F2 hook decision for Bash sed on evaluators/l0.py:", "deny" if o.stdout.strip() else "allow",
          "(and settings.json only routes Edit|Write|NotebookEdit to the hook)")

    # F3: forged pyc for evaluators/stats.py
    src = proj / "evaluators" / "stats.py"
    st = src.stat()
    probe = "from evaluators.stats import likelihood_factor_to_sigma as f; print(f(1000))"
    print("F3 before:", run([sys.executable, "-c", probe], proj).stdout.strip())
    evil = proj / "evil_stats.py"
    evil.write_text(src.read_text() + "\n\ndef likelihood_factor_to_sigma(f):\n    return 42.0\n")
    # 让伪造源与原文件 size 相同不是必须的：pyc 头里记录的是原文件的 mtime 与 size，下面直接写原文件的值
    pyc = Path(importlib.util.cache_from_source(str(src)))
    pyc.parent.mkdir(exist_ok=True)
    py_compile.compile(str(evil), cfile=str(pyc), dfile=str(src),
                       invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
    data = bytearray(pyc.read_bytes())
    data[8:12] = int(st.st_mtime).to_bytes(4, "little")
    data[12:16] = (st.st_size & 0xFFFFFFFF).to_bytes(4, "little")
    pyc.write_bytes(bytes(data))
    evil.unlink()
    print("F3 after forged pyc:", run([sys.executable, "-c", probe], proj).stdout.strip())
    print("F3 verify:", run([sys.executable, "scripts/freeze_evaluator.py", "verify"], proj).stdout.strip())
    o = run([sys.executable, "-c", "from evaluators.leaderboard import evaluator_hash; print(evaluator_hash())"], proj)
    print("F3 leaderboard evaluator_hash():", o.stdout.strip() or o.stderr[-300:])
    shutil.rmtree(pyc.parent)

    # F4: 哈希覆盖面
    sys.path.insert(0, str(proj))
    spec = importlib.util.spec_from_file_location("fz", proj / "scripts" / "freeze_evaluator.py")
    fz = importlib.util.module_from_spec(spec); spec.loader.exec_module(fz)
    tracked = [str(p.relative_to(proj)) for p in fz.tracked_files()]
    print("F4 hashed files:", tracked)
    import importlib.machinery as m
    print("F4 import order per directory (first wins):", m.EXTENSION_SUFFIXES[:2], "before", m.SOURCE_SUFFIXES,
          "-> an evaluators/noise.cpython-312-darwin.so would shadow noise.py and is not hashed")

    # F5: 改 scripts/freeze_evaluator.py
    (proj / "evaluators" / "stats.py").write_text(src.read_text() + "\n# tampered\n")
    print("F5 verify after tampering stats.py:", run([sys.executable, "scripts/freeze_evaluator.py", "verify"],
                                                     proj).stdout.strip().splitlines()[0])
    fsrc = (proj / "scripts" / "freeze_evaluator.py").read_text()
    frozen = (proj / "evaluators" / "FROZEN").read_text().split("=")[1].strip()
    fsrc = fsrc.replace("def combined_hash(hashes):", f"def combined_hash(hashes):\n    return {frozen!r}\n\ndef _orig(hashes):")
    fsrc = fsrc.replace("    if bad:", "    if False:")
    (proj / "scripts" / "freeze_evaluator.py").write_text(fsrc)
    print("F5 verify after also editing scripts/freeze_evaluator.py:",
          run([sys.executable, "scripts/freeze_evaluator.py", "verify"], proj).stdout.strip())
    o = run([sys.executable, "-c", "from evaluators.leaderboard import evaluator_hash; print(evaluator_hash())"], proj)
    print("F5 leaderboard evaluator_hash():", o.stdout.strip() or o.stderr[-300:])

    # F6: 库版本
    from importlib.metadata import version
    print("F6 library versions (not in the evaluator hash; pyproject has no pins):",
          {p: version(p) for p in ("stim", "sinter", "ldpc", "pymatching", "ortools", "numpy")})
    print("F6 uv.lock exists:", (ROOT / "uv.lock").exists())
    shutil.rmtree(proj)


if __name__ == "__main__":
    main()
