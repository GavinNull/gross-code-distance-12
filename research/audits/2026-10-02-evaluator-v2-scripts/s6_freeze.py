"""S6 冻结机制（全部在临时目录的项目副本里做，不碰真实的 evaluators/、不创建真实的 FROZEN）。

回归：F1（hook 大小写）、F3（伪造 .pyc）、F4（.so）、F5（改冻结脚本 / 清单）、F6（库版本）
新：
  F7  PYTHONPYCACHEPREFIX：字节码缓存放到 evaluators/ 之外，伪造的 .pyc 在那里被加载，freeze verify 不扫描那里
  F8  evaluators/ 里的隐藏文件 / 子目录包（l0/ 包优先于 l0.py）是否被发现
  F9  hook：Unicode 大小写变体（APFS 是否把它们当成同一个文件）、.claude/settings.json 是否受保护
  F10 F5 的独立校验：改冻结脚本让它自报“完整”时，shasum -c research/evaluator_freeze.sha256 是否能发现

用法：uv run python s6_freeze.py
"""
import importlib.util
import json
import marshal
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PY = sys.executable


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def make_copy() -> Path:
    root = Path(tempfile.mkdtemp(prefix="s6freeze_")).resolve() / "proj"
    fm = load(REPO / "scripts" / "freeze_evaluator.py", "_fm_real")
    shutil.copytree(REPO / "evaluators", root / "evaluators",
                    ignore=shutil.ignore_patterns("__pycache__", "FROZEN", "MANIFEST.sha256"))
    for f in fm.EXTRA_FILES:
        (root / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / f, root / f)
    shutil.copy2(REPO / ".claude" / "settings.json", root / ".claude" / "settings.json")
    (root / "research").mkdir()
    return root


def run(args, cwd, env=None, inp=None):
    e = dict(os.environ)
    e.pop("PYTHONPYCACHEPREFIX", None)
    e.pop("PYTHONDONTWRITEBYTECODE", None)   # 本机 shell 设了它；正常运行时 Python 会写字节码缓存
    e.update(env or {})
    e["PYTHONPATH"] = str(cwd)
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, env=e, input=inp)


def verify(root, env=None):
    r = run([PY, "scripts/freeze_evaluator.py", "verify"], root, env)
    return r.returncode, (r.stdout.strip().splitlines() or [""])[0][:160]


SIGMA = "from evaluators.stats import likelihood_factor_to_sigma as f; print(f(1000))"


def main():
    root = make_copy()
    print("project copy:", root)
    r = run([PY, "scripts/freeze_evaluator.py", "freeze"], root)
    print("freeze:", r.stdout.strip().splitlines()[0])
    print("verify (clean):", verify(root))

    # ---------------- F7 PYTHONPYCACHEPREFIX
    prefix = root.parent / "pycache_prefix"
    env = {"PYTHONPYCACHEPREFIX": str(prefix)}
    print("F7 baseline sigma:", run([PY, "-c", SIGMA], root, env).stdout.strip())
    pycs = list(prefix.rglob("stats.cpython-*.pyc"))
    print("F7 pyc written outside evaluators/:", [str(p.relative_to(prefix)) for p in pycs])
    src = root / "evaluators" / "stats.py"
    evil_src = src.read_text().replace("def likelihood_factor_to_sigma", "def _orig_lf2s") + \
        "\n\ndef likelihood_factor_to_sigma(factor):\n    return 42.0\n"
    code = compile(evil_src, str(src), "exec")
    pyc = pycs[0]
    head = pyc.read_bytes()[:16]                   # magic + flags + 源文件 mtime + size（与真实源文件一致）
    pyc.write_bytes(head + marshal.dumps(code))
    print("F7 after forging the out-of-tree pyc, sigma:", run([PY, "-c", SIGMA], root, env).stdout.strip())
    print("F7 verify with the same env:", verify(root, env))
    print("F7 evaluators/__pycache__ exists:", (root / "evaluators" / "__pycache__").exists())
    r = run([PY, "-c", "from evaluators import leaderboard as lb, pipeline; e = pipeline.environment_check(); "
                       "print(e['evaluator']['verified'], e['evaluator']['matches_frozen'], e['ok'])"], root, env)
    print("F7 pipeline.environment_check() verified/matches_frozen/ok:", r.stdout.strip(), r.stderr.strip()[-200:])

    # ---------------- F3 regression (in-tree forged pyc)
    root2 = make_copy()
    run([PY, "scripts/freeze_evaluator.py", "freeze"], root2)
    run([PY, "-c", SIGMA], root2)       # 写出 evaluators/__pycache__
    p2 = next((root2 / "evaluators" / "__pycache__").glob("stats.cpython-*.pyc"))
    src2 = root2 / "evaluators" / "stats.py"
    p2.write_bytes(p2.read_bytes()[:16] + marshal.dumps(compile(evil_src, str(src2), "exec")))
    print("F3 in-tree forged pyc sigma:", run([PY, "-c", SIGMA], root2).stdout.strip(), "verify:", verify(root2))
    p2.unlink()

    # ---------------- F4 / F8
    for rel, content in (("evaluators/stats.cpython-312-darwin.so", b"\x00"), ("evaluators/.hidden.py", b"x=1\n"),
                         ("evaluators/l0/__init__.py", b"raise SystemExit('package shadows l0.py')\n")):
        f = root2 / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(content)
        print(f"F4/F8 {rel}: verify -> {verify(root2)}")
        f.unlink()
        if f.parent.name == "l0":
            f.parent.rmdir()

    # ---------------- F5 / F10
    fs = root2 / "scripts" / "freeze_evaluator.py"
    orig = fs.read_text()
    (root2 / "evaluators" / "stats.py").write_text(evil_src)
    print("F5 tampered stats.py, verify:", verify(root2))
    fs.write_text(orig.replace('    out["verified"] = not probs\n    return out',
                               '    out["verified"] = True\n    out["problems"] = []\n    return out')
                  .replace('    if not v["verified"]:', '    if False:'))
    print("F5 + patched freeze script, verify:", verify(root2))
    r = subprocess.run(["shasum", "-a", "256", "-c", "research/evaluator_freeze.sha256"], cwd=root2,
                       capture_output=True, text=True)
    print("F10 independent shasum -c: rc", r.returncode, [x for x in r.stdout.splitlines() if "FAILED" in x])

    # ---------------- F9 hook
    hook = root / ".claude" / "hooks" / "guard_frozen.py"
    henv = {"CLAUDE_PROJECT_DIR": str(root)}
    for p in ("evaluators/l0.py", "EVALUATORS/L0.PY", "Scripts/freeze_evaluator.py", "scrİpts/freeze_evaluator.py",
              "tests/TEST_L0.py", "tｅsts/test_l0.py", ".claude/settings.json", "research/LEADERBOARD.jsonl",
              "evaluators/../evaluators/noise.py"):
        payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(root / p)}, "cwd": str(root)})
        o = run([PY, str(hook)], root, henv, payload)
        dec = json.loads(o.stdout)["hookSpecificOutput"]["permissionDecision"] if o.stdout.strip() else "allow"
        print(f"F9 hook Edit {p!r}: {dec}; same file on disk as the real one: {(root / p).exists()}")


if __name__ == "__main__":
    main()
