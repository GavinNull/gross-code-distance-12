"""评估器冻结与校验。

    uv run python scripts/freeze_evaluator.py freeze   # 人在 G1 批准后执行
    uv run python scripts/freeze_evaluator.py verify   # 每次实验前 / auditor 复核时执行
    uv run python scripts/freeze_evaluator.py hash     # 打印当前评估器哈希（写进 leaderboard）

freeze 会写 evaluators/MANIFEST.sha256 和 evaluators/FROZEN。
冻结后 .claude/hooks/guard_frozen.py 会拦截 agent 对 evaluators/ 的编辑；
verify 用来发现绕过 hook 的修改。解冻只能由人手动删除 evaluators/FROZEN。
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = ROOT / "evaluators"
MANIFEST = EVAL_DIR / "MANIFEST.sha256"
FROZEN = EVAL_DIR / "FROZEN"


def tracked_files():
    return sorted(p for p in EVAL_DIR.rglob("*.py") if "__pycache__" not in p.parts)


def file_hashes():
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked_files()}


def combined_hash(hashes):
    h = hashlib.sha256()
    for path, digest in sorted(hashes.items()):
        h.update(f"{path}:{digest}\n".encode())
    return h.hexdigest()[:16]


def freeze():
    hashes = file_hashes()
    MANIFEST.write_text("".join(f"{d}  {p}\n" for p, d in sorted(hashes.items())))
    FROZEN.write_text(f"evaluator_hash={combined_hash(hashes)}\n")
    print(f"已冻结 {len(hashes)} 个文件，评估器哈希 {combined_hash(hashes)}")


def verify():
    if not FROZEN.exists():
        print("评估器尚未冻结")
        return 1
    expected = {}
    for line in MANIFEST.read_text().splitlines():
        digest, path = line.split("  ", 1)
        expected[path] = digest
    actual = file_hashes()
    bad = sorted(p for p in expected.keys() | actual.keys() if expected.get(p) != actual.get(p))
    if bad:
        print("评估器被修改，以下文件与冻结时不一致：")
        for p in bad:
            print(f"  {p}")
        return 1
    print(f"评估器完整，哈希 {combined_hash(actual)}")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if cmd == "freeze":
        freeze()
    elif cmd == "verify":
        sys.exit(verify())
    elif cmd == "hash":
        print(combined_hash(file_hashes()))
    else:
        sys.exit(__doc__)
