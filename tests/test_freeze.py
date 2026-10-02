"""冻结机制（scripts/freeze_evaluator.py）与编辑 hook（.claude/hooks/guard_frozen.py）：auditor G1 F1–F6 的回归测试。

全部在临时目录的项目副本里做，不碰真正的 evaluators/（不会创建 evaluators/FROZEN）。
"""
from __future__ import annotations

import importlib.util
import json
import marshal
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def proj(tmp_path):
    """项目副本：evaluators/、冻结脚本、hook、pyproject.toml、uv.lock、评估器测试。返回 (根目录, 冻结模块)。"""
    root = tmp_path / "proj"
    fm_real = _load(REPO / "scripts" / "freeze_evaluator.py", "_fm_real")
    shutil.copytree(REPO / "evaluators", root / "evaluators",
                    ignore=shutil.ignore_patterns("__pycache__", "FROZEN", "MANIFEST.sha256"))
    for f in fm_real.EXTRA_FILES:
        src = REPO / f
        if src.exists():
            (root / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, root / f)
    (root / "research").mkdir()
    fm = _load(root / "scripts" / "freeze_evaluator.py", f"_fm_{id(root)}")
    return root, fm


def test_hash_covers_all_evaluator_files_and_extra_files(proj):
    root, fm = proj
    names = set(fm.scan()["hashes"])
    assert "evaluators/README.md" in names                      # 不只是 *.py
    for f in ("evaluators/l0.py", "evaluators/pipeline.py", "evaluators/tasks.py", "evaluators/candidate.py",
              "scripts/freeze_evaluator.py", ".claude/hooks/guard_frozen.py", "pyproject.toml", "uv.lock",
              "tests/test_l0.py", "tests/test_g1_attacks.py", "tests/test_pipeline.py", "tests/memory_builder.py"):
        assert f in names, f
    assert fm.scan()["problems"] == []


def test_freeze_then_verify_ok_and_external_copies(proj):
    root, fm = proj
    assert fm.freeze() == 0
    assert (root / "evaluators" / "FROZEN").exists()
    assert (root / "research" / "evaluator_freeze.json").exists()
    assert fm.verify_tree()["verified"] is True
    ext = json.loads((root / "research" / "evaluator_freeze.json").read_text())
    assert ext["evaluator_hash"] == fm.frozen_hash() == fm.scan()["hash"]
    # 外部清单可由系统工具独立校验（不依赖本脚本）
    shasum = shutil.which("shasum") or shutil.which("sha256sum")
    if shasum:
        args = [shasum, "-a", "256", "-c"] if shasum.endswith("shasum") else [shasum, "-c"]
        r = subprocess.run(args + ["research/evaluator_freeze.sha256"], cwd=root, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("victim", ["evaluators/stats.py", "evaluators/README.md", "scripts/freeze_evaluator.py",
                                    ".claude/hooks/guard_frozen.py", "pyproject.toml", "uv.lock", "tests/test_l0.py"])
def test_any_protected_file_change_is_detected(proj, victim):
    """F5 / F6：冻结脚本、hook、pyproject.toml、uv.lock、评估器测试都在清单里。"""
    root, fm = proj
    fm.freeze()
    with open(root / victim, "a") as f:
        f.write("\n# tampered\n")
    v = fm.verify_tree()
    assert v["verified"] is False and any(victim in p for p in v["problems"]), v


def test_new_or_deleted_file_is_tampering(proj):
    root, fm = proj
    fm.freeze()
    (root / "evaluators" / "notes.txt").write_text("hi")
    v = fm.verify_tree()
    assert not v["verified"] and any("evaluators/notes.txt" in p and "not in the frozen manifest" in p
                                     for p in v["problems"])
    (root / "evaluators" / "notes.txt").unlink()
    (root / "tests" / "test_g1_attacks.py").unlink()
    v = fm.verify_tree()
    assert not v["verified"] and any("tests/test_g1_attacks.py" in p for p in v["problems"])


def _write_pyc(pyc: Path, src: Path, code) -> None:
    import importlib._bootstrap_external as be
    st = src.stat()
    pyc.parent.mkdir(exist_ok=True)
    pyc.write_bytes(be._code_to_timestamp_pyc(code, st.st_mtime, st.st_size))


def test_forged_pyc_is_detected_but_genuine_pyc_is_fine(proj):
    """F3：伪造 .pyc（头部写源文件的 mtime / size）。"""
    root, fm = proj
    src = root / "evaluators" / "stats.py"
    tag = sys.implementation.cache_tag
    pyc = root / "evaluators" / "__pycache__" / f"stats.{tag}.pyc"
    _write_pyc(pyc, src, compile(src.read_bytes(), str(src), "exec", dont_inherit=True))
    assert fm.scan()["problems"] == []                        # 由源文件编译的 pyc 允许
    forged_src = src.read_text().replace("return math.sqrt(2 * math.log(factor))", "return 42.0")
    assert forged_src != src.read_text()
    _write_pyc(pyc, src, compile(forged_src, str(src), "exec", dont_inherit=True))
    probs = fm.scan()["problems"]
    assert any("bytecode does not match" in p for p in probs), probs
    assert fm.freeze() == 1                                   # 有伪造文件时拒绝冻结
    pyc.unlink()
    fm.freeze()
    _write_pyc(pyc, src, compile(forged_src, str(src), "exec", dont_inherit=True))
    assert fm.verify_tree()["verified"] is False


@pytest.mark.parametrize("name", ["stats.cpython-312-darwin.so", "stats.abi3.so", "l0.pyd", "__pycache__/junk.txt",
                                  "stray.pyc"])
def test_native_and_unexpected_files_rejected(proj, name):
    """F4：同名扩展模块会优先于 .py 被导入。"""
    root, fm = proj
    p = root / "evaluators" / name
    p.parent.mkdir(exist_ok=True)
    p.write_bytes(b"\x00binary")
    assert fm.scan()["problems"], name


def test_symlink_in_evaluators_rejected(proj):
    root, fm = proj
    os.symlink(root / "pyproject.toml", root / "evaluators" / "link.py")
    assert any("symlink" in p for p in fm.scan()["problems"])


def test_external_record_mismatch_detected(proj):
    root, fm = proj
    fm.freeze()
    j = json.loads((root / "research" / "evaluator_freeze.json").read_text())
    j["evaluator_hash"] = "0" * 16
    (root / "research" / "evaluator_freeze.json").write_text(json.dumps(j))
    assert any("evaluator_freeze.json" in p for p in fm.verify_tree()["problems"])


def test_real_repo_is_not_frozen_by_tests():
    assert not (REPO / "evaluators" / "FROZEN").exists()


# ---------------------------------------------------------------------------
# hook（F1）
# ---------------------------------------------------------------------------

@pytest.fixture()
def hook():
    return _load(REPO / ".claude" / "hooks" / "guard_frozen.py", "_guard")


def _ask(hook, root, path):
    return hook.decide({"tool_input": {"file_path": str(path)}, "cwd": str(root)}, str(root))


def test_hook_case_insensitive_and_symlinks(proj, hook):
    root, fm = proj
    # 未冻结：成绩单和冻结文件永远不能改（大小写变体也不行），评估器可以改
    for p in ("research/leaderboard.jsonl", "research/Leaderboard.jsonl", "Evaluators/FROZEN",
              "evaluators/manifest.SHA256", "research/evaluator_freeze.json"):
        assert _ask(hook, root, root / p), p
    assert _ask(hook, root, root / "evaluators" / "l0.py") is None
    fm.freeze()
    for p in ("evaluators/l0.py", "Evaluators/l0.py", "EVALUATORS/noise.py", "evaluators/new_file.py",
              "scripts/freeze_evaluator.py", "Scripts/Freeze_Evaluator.py", ".claude/hooks/guard_frozen.py",
              "pyproject.toml", "uv.lock", "tests/test_l0.py", "TESTS/test_pipeline.py"):
        assert _ask(hook, root, root / p), p
    # 相对路径
    assert hook.decide({"tool_input": {"file_path": "Evaluators/l2.py"}, "cwd": str(root)}, str(root))
    # 符号链接指向受保护文件
    os.symlink(root / "evaluators" / "l0.py", root / "research" / "innocent.py")
    assert _ask(hook, root, root / "research" / "innocent.py")
    # 硬链接
    os.link(root / "evaluators" / "noise.py", root / "research" / "hard.py")
    assert _ask(hook, root, root / "research" / "hard.py")
    # 普通文件放行
    assert _ask(hook, root, root / "research" / "notes.md") is None
    assert _ask(hook, root, root / "search" / "x.py") is None


def test_hook_main_emits_deny_json(proj, hook):
    root, fm = proj
    fm.freeze()
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(root))
    r = subprocess.run([sys.executable, str(REPO / ".claude" / "hooks" / "guard_frozen.py")],
                       input=json.dumps({"tool_input": {"file_path": str(root / "Evaluators" / "l0.py")}}),
                       capture_output=True, text=True, env=env)
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


# ---------------------------------------------------------------------------
# F6：库版本固定
# ---------------------------------------------------------------------------

def test_pinned_versions_match_pyproject_and_environment():
    import importlib.metadata as md
    from evaluators.tasks import PINNED_VERSIONS
    text = (REPO / "pyproject.toml").read_text()
    pins = dict(re.findall(r'"([A-Za-z0-9_.-]+)==([^"]+)"', text))
    for pkg, ver in PINNED_VERSIONS.items():
        assert pins.get(pkg) == ver, (pkg, pins.get(pkg), ver)
        assert md.version(pkg) == ver, pkg


def test_environment_check_flags_version_drift(monkeypatch):
    from evaluators import pipeline, tasks
    monkeypatch.setitem(tasks.PINNED_VERSIONS, "stim", "0.0.1")
    env = pipeline.environment_check()
    assert not env["ok"] and any("stim" in p for p in env["problems"])
