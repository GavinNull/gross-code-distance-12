"""评估器冻结与校验（评估器 v2，2026-10-02；修复 auditor G1 F3–F6）。

    uv run python scripts/freeze_evaluator.py freeze   # 只由 PI 在 G1 批准后执行
    uv run python scripts/freeze_evaluator.py verify   # 每次实验前 / auditor 复核时执行（退出码 0 = 完整）
    uv run python scripts/freeze_evaluator.py hash     # 打印当前评估器哈希（写进 leaderboard）
    uv run python scripts/freeze_evaluator.py list     # 列出纳入哈希的文件

纳入哈希的文件（“评估器”）：
  - evaluators/ 下的**全部文件**（任何扩展名，含 README.md），除了冻结标记 FROZEN 与清单 MANIFEST.sha256 本身；
  - 本脚本、.claude/hooks/guard_frozen.py、pyproject.toml、uv.lock（库版本是裁判的一部分，F6）；
  - 评估器的测试（EXTRA_FILES 里列出的 tests/*.py）。

evaluators/ 里的其他东西：
  - 清单外出现的任何文件（新文件、.so / .pyd / .dylib 扩展模块、符号链接、__pycache__ 里的非 .pyc 文件）一律视为篡改；
  - __pycache__/*.pyc 只有在“由对应的、受清单保护的 .py 源文件编译而来”时才允许：读出 pyc 中的代码对象，与当前源文件
    重新编译的代码对象逐项比较（字节码、常量、名字、行表，递归到嵌套函数），不一致即为篡改（F3：伪造 pyc 头部的
    mtime/size 不再有用）。也可以干脆删掉 __pycache__ 并用 PYTHONDONTWRITEBYTECODE=1 运行。

freeze 写四个文件：evaluators/MANIFEST.sha256、evaluators/FROZEN，以及 evaluators/ 之外的
research/evaluator_freeze.sha256（`shasum -a 256 -c` 可直接校验的清单）与 research/evaluator_freeze.json（哈希与版本）。
PI 冻结后应把它们提交进 git，并用文件系统权限锁住 evaluators/（见 evaluators/README.md §10）。
能改评估器的人也能改本脚本，所以“本脚本报告完整”本身不是证明：外部锚点是 git 里的 research/evaluator_freeze.*，
以及不依赖本脚本的 `shasum -a 256 -c research/evaluator_freeze.sha256`。
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import marshal
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = ROOT / "evaluators"
MANIFEST = EVAL_DIR / "MANIFEST.sha256"
FROZEN = EVAL_DIR / "FROZEN"
EXTERNAL_MANIFEST = ROOT / "research" / "evaluator_freeze.sha256"
EXTERNAL_JSON = ROOT / "research" / "evaluator_freeze.json"

EXTRA_FILES = (
    "scripts/freeze_evaluator.py",
    ".claude/hooks/guard_frozen.py",
    "pyproject.toml",
    "uv.lock",
    "tests/conftest.py",
    "tests/memory_builder.py",
    "tests/schedule_helpers.py",
    "tests/test_candidate.py",
    "tests/test_codes.py",
    "tests/test_distance.py",
    "tests/test_freeze.py",
    "tests/test_g1_attacks.py",
    "tests/test_l0.py",
    "tests/test_l2.py",
    "tests/test_leaderboard.py",
    "tests/test_noise.py",
    "tests/test_pipeline.py",
    "tests/test_stats.py",
    "tests/test_v21_audit_fixes.py",
    "tests/test_distance_tasks.py",
    "tests/v21_helpers.py",
    "tests/test_decoder_eval.py",          # 解码器任务（H-005）
)
_SELF_FILES = {MANIFEST.name, FROZEN.name}
_NATIVE_SUFFIXES = (".so", ".pyd", ".dylib", ".dll")
_PYC = re.compile(r"^(?P<mod>[A-Za-z_][A-Za-z0-9_]*)\.cpython-(?P<ver>\d+)(?:\.opt-(?P<opt>[12]))?\.pyc$")


def _rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def _eval_files() -> tuple[list[Path], list[Path], list[str]]:
    """evaluators/ 下的 (受保护文件, __pycache__ 里的 .pyc, 立即判为篡改的问题)。"""
    tracked, pycs, problems = [], [], []
    for p in sorted(EVAL_DIR.rglob("*")):
        rel = _rel(p)
        if p.is_symlink():
            problems.append(f"symlink not allowed under evaluators/: {rel}")
            continue
        if p.is_dir():
            continue
        if p.parent == EVAL_DIR and p.name in _SELF_FILES:
            continue
        if p.name.lower().endswith(_NATIVE_SUFFIXES):
            problems.append(f"native extension module not allowed under evaluators/ (would shadow the .py source): "
                            f"{rel}")
            continue
        if "__pycache__" in p.parts:
            if p.parent.name == "__pycache__" and _PYC.match(p.name):
                pycs.append(p)
            else:
                problems.append(f"unexpected file in __pycache__: {rel}")
            continue
        if p.suffix == ".pyc":
            problems.append(f"stray .pyc outside __pycache__: {rel}")
            continue
        tracked.append(p)
    return tracked, pycs, problems


def tracked_files() -> list[Path]:
    files, _, _ = _eval_files()
    return sorted(files + [ROOT / f for f in EXTRA_FILES if (ROOT / f).exists()])


def file_hashes(paths=None) -> dict[str, str]:
    paths = tracked_files() if paths is None else paths
    return {_rel(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def combined_hash(hashes: dict[str, str]) -> str:
    h = hashlib.sha256()
    for path, digest in sorted(hashes.items()):
        h.update(f"{path}:{digest}\n".encode())
    return h.hexdigest()[:16]


def _check_pyc(pyc: Path, protected: set[str]) -> str | None:
    """pyc 必须由对应的受保护源文件编译而来（代码对象逐项相等）。返回问题或 None。"""
    m = _PYC.match(pyc.name)
    src = pyc.parent.parent / f"{m['mod']}.py"
    rel = _rel(pyc)
    if _rel(src) not in protected or not src.exists():
        return f"{rel}: no protected source file {_rel(src)}"
    if int(m["ver"]) != sys.version_info.major * 100 + sys.version_info.minor and \
            m["ver"] != f"{sys.version_info.major}{sys.version_info.minor}":
        return f"{rel}: compiled for another Python version"
    data = pyc.read_bytes()
    if len(data) < 16:
        return f"{rel}: truncated"
    try:
        code = marshal.loads(data[16:])
    except Exception as e:  # noqa: BLE001
        return f"{rel}: unreadable ({e})"
    opt = int(m["opt"] or 0)
    for fname in (str(src), str(src.resolve())):
        try:
            ref = compile(src.read_bytes(), fname, "exec", dont_inherit=True, optimize=opt)
        except SyntaxError as e:
            return f"{rel}: source does not compile ({e})"
        if code == ref:
            return None
    return (f"{rel}: bytecode does not match {_rel(src)} (forged or stale .pyc); delete evaluators/__pycache__ "
            f"and re-run")


def scan() -> dict:
    """当前评估器的状态：{"hash", "hashes", "problems"}（problems = 不依赖清单就能判定的篡改迹象）。"""
    files, pycs, problems = _eval_files()
    hashes = file_hashes(sorted(files + [ROOT / f for f in EXTRA_FILES if (ROOT / f).exists()]))
    protected = set(hashes)
    for pyc in pycs:
        msg = _check_pyc(pyc, protected)
        if msg:
            problems.append(msg)
    missing_extra = [f for f in EXTRA_FILES if not (ROOT / f).exists()]
    for f in missing_extra:
        problems.append(f"protected file missing: {f}")
    return {"hash": combined_hash(hashes), "hashes": hashes, "problems": problems}


def _read_manifest(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text().splitlines():
        if line.strip():
            digest, p = line.split("  ", 1)
            out[p] = digest
    return out


def frozen_hash() -> str | None:
    if not FROZEN.exists():
        return None
    for line in FROZEN.read_text().splitlines():
        if line.startswith("evaluator_hash="):
            return line.split("=", 1)[1].strip()
    return None


def verify_tree() -> dict:
    """{"frozen", "hash", "frozen_hash", "verified", "problems"}。未冻结时 verified=None（只报告 scan 的问题）。"""
    st = scan()
    out = {"frozen": FROZEN.exists(), "hash": st["hash"], "frozen_hash": frozen_hash(), "problems": list(st["problems"])}
    if not FROZEN.exists():
        out["verified"] = None
        return out
    probs = out["problems"]
    if not MANIFEST.exists():
        probs.append("evaluators/MANIFEST.sha256 missing")
        out["verified"] = False
        return out
    expected = _read_manifest(MANIFEST)
    actual = st["hashes"]
    for p in sorted(expected.keys() | actual.keys()):
        if p not in actual:
            probs.append(f"protected file deleted: {p}")
        elif p not in expected:
            probs.append(f"file not in the frozen manifest (new file = tampering): {p}")
        elif expected[p] != actual[p]:
            probs.append(f"file modified since freeze: {p}")
    if EXTERNAL_MANIFEST.exists():
        if _read_manifest(EXTERNAL_MANIFEST) != expected:
            probs.append("evaluators/MANIFEST.sha256 differs from research/evaluator_freeze.sha256")
    else:
        probs.append("external manifest research/evaluator_freeze.sha256 missing")
    if EXTERNAL_JSON.exists():
        try:
            ext = json.loads(EXTERNAL_JSON.read_text())
            if ext.get("evaluator_hash") != out["frozen_hash"]:
                probs.append("evaluators/FROZEN hash differs from research/evaluator_freeze.json")
        except json.JSONDecodeError:
            probs.append("research/evaluator_freeze.json is not valid JSON")
    else:
        probs.append("research/evaluator_freeze.json missing")
    if out["frozen_hash"] != st["hash"]:
        probs.append(f"combined hash {st['hash']} != frozen {out['frozen_hash']}")
    out["verified"] = not probs
    return out


def freeze() -> int:
    st = scan()
    if st["problems"]:
        print("拒绝冻结：评估器目录里有不允许的文件：")
        for p in st["problems"]:
            print(f"  {p}")
        return 1
    hashes = st["hashes"]
    text = "".join(f"{d}  {p}\n" for p, d in sorted(hashes.items()))
    MANIFEST.write_text(text)
    EXTERNAL_MANIFEST.write_text(text)
    h = combined_hash(hashes)
    FROZEN.write_text(f"evaluator_hash={h}\n")
    try:
        import importlib.metadata as md
        versions = {pkg: md.version(pkg) for pkg in ("stim", "sinter", "ldpc", "pymatching", "numpy", "scipy",
                                                      "ortools", "python-sat")}
    except Exception:  # noqa: BLE001
        versions = {}
    EXTERNAL_JSON.write_text(json.dumps({"evaluator_hash": h, "num_files": len(hashes),
                                         "time": _dt.datetime.now(_dt.UTC).isoformat(),
                                         "python": sys.version.split()[0], "versions": versions}, indent=2) + "\n")
    print(f"已冻结 {len(hashes)} 个文件，评估器哈希 {h}")
    print("下一步（PI）：git add evaluators/FROZEN evaluators/MANIFEST.sha256 research/evaluator_freeze.sha256 "
          "research/evaluator_freeze.json && git commit；然后锁定 evaluators/（见 evaluators/README.md §10）")
    return 0


def verify() -> int:
    v = verify_tree()
    if not v["frozen"]:
        print(f"评估器尚未冻结；当前哈希 {v['hash']}")
        for p in v["problems"]:
            print(f"  问题：{p}")
        return 1
    if not v["verified"]:
        print("评估器与冻结时不一致：")
        for p in v["problems"]:
            print(f"  {p}")
        return 1
    print(f"评估器完整，哈希 {v['hash']}（外部锚点：git 中的 research/evaluator_freeze.*；独立校验："
          f"shasum -a 256 -c research/evaluator_freeze.sha256）")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if cmd == "freeze":
        sys.exit(freeze())
    elif cmd == "verify":
        sys.exit(verify())
    elif cmd == "hash":
        print(scan()["hash"])
    elif cmd == "list":
        for p in sorted(scan()["hashes"]):
            print(p)
    else:
        sys.exit(__doc__)
