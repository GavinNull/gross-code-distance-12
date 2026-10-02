"""search/llm_evolve 的沙箱、哈希、提取、数据库单元测试（不调用任何网络 API）。"""

import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from search.llm_evolve.database import (
    Program,
    ProgramDatabase,
    normalize_source,
    program_hash,
)
from search.llm_evolve.mutation import mutate_program
from search.llm_evolve.prompt import build_prompt, extract_program
from search.llm_evolve.sandbox import PROJECT_ROOT, run_in_sandbox


# ----------------------------------------------------------------------------- sandbox
def test_sandbox_ok_and_print_does_not_corrupt_result():
    src = "import numpy as np\ndef f(x):\n    print('noise on stdout')\n    return np.arange(x)\n"
    r = run_in_sandbox(src, "f", [[3], [1]], timeout_s=5)
    assert r.ok, r.diagnostics()
    assert r.outputs == [[0, 1, 2], [0]]
    assert "noise on stdout" in r.stderr


def test_sandbox_exception_gives_truncated_traceback():
    src = "def f(x):\n    return helper(x)\n\ndef helper(x):\n    return 1 / 0\n"
    r = run_in_sandbox(src, "f", [[1]], timeout_s=5, max_traceback_chars=400)
    assert not r.ok and r.error_type == "ZeroDivisionError"
    assert "<candidate>" in r.traceback and "1 / 0" in r.traceback
    assert "_sandbox_runner" not in r.traceback  # 执行器自身的栈帧被剥掉
    long = "def f(x):\n    raise ValueError('x' * 10000)\n"
    r2 = run_in_sandbox(long, "f", [[1]], timeout_s=5, max_traceback_chars=400)
    assert len(r2.diagnostics(max_chars=500)) <= 500


def test_sandbox_timeout_kills_process():
    r = run_in_sandbox("def f(x):\n    while True:\n        pass\n", "f", [[1]], timeout_s=1.0)
    assert not r.ok and r.error_type == "Timeout"
    assert r.elapsed < 5


def test_sandbox_memory_limit():
    src = ("def f(x):\n    a = bytearray(1500 * 1024 * 1024)\n"
           "    a[::4096] = b'\\x01' * len(a[::4096])\n    return 1\n")
    r = run_in_sandbox(src, "f", [[1]], timeout_s=10, mem_mb=256)
    assert not r.ok
    assert r.error_type in {"MemoryLimitExceeded", "MemoryError", "Crashed", "NoResult"}


@pytest.mark.parametrize("src,needle", [
    (f"def f(x):\n    open({str(PROJECT_ROOT / 'pwned.txt')!r}, 'w').write('x')\n", "write-open"),
    (f"def f(x):\n    return open({str(PROJECT_ROOT / 'CLAUDE.md')!r}).read()\n", "protected"),
    (f"import os\ndef f(x):\n    return os.listdir({str(PROJECT_ROOT)!r})\n", "protected"),
    ("import socket\ndef f(x):\n    socket.create_connection(('example.com', 80))\n", "socket"),
    ("import subprocess\ndef f(x):\n    subprocess.run(['echo', 'hi'])\n", "subprocess"),
    ("import os\ndef f(x):\n    os.system('echo hi')\n", "os.system"),
])
def test_sandbox_blocks_dangerous_operations(src, needle):
    r = run_in_sandbox(src, "f", [[1]], timeout_s=5)
    assert not r.ok and r.error_type == "PermissionError", r.diagnostics()
    assert needle in r.error
    assert not (PROJECT_ROOT / "pwned.txt").exists()


def test_sandbox_can_use_its_own_tempdir_and_cannot_import_project():
    r = run_in_sandbox("def f(x):\n    open('t.txt', 'w').write('ok')\n    return open('t.txt').read()\n",
                       "f", [[1]], timeout_s=5)
    assert r.ok and r.outputs == ["ok"]
    r = run_in_sandbox("def f(x):\n    import evaluators\n    return 1\n", "f", [[1]], timeout_s=5)
    assert not r.ok and r.error_type == "ModuleNotFoundError"


def test_sandbox_does_not_leak_secrets(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-should-not-leak")
    r = run_in_sandbox("import os\ndef f(x):\n    return dict(os.environ)\n", "f", [[1]], timeout_s=5)
    assert r.ok
    assert "ANTHROPIC_API_KEY" not in r.outputs[0]
    assert all("sk-test" not in v for v in r.outputs[0].values())


def test_sandbox_missing_function_and_syntax_error():
    r = run_in_sandbox("def g(x):\n    return 1\n", "f", [[1]], timeout_s=5)
    assert not r.ok and r.error_type == "MissingFunction"
    r = run_in_sandbox("def f(x) return 1\n", "f", [[1]], timeout_s=5)
    assert not r.ok and r.error_type == "SyntaxError"
    r = run_in_sandbox("import sys\ndef f(x):\n    sys.exit(0)\n", "f", [[1]], timeout_s=5)
    assert not r.ok and r.error_type == "SystemExit"


# ----------------------------------------------------------------------------- hashing / prompt
def test_normalized_hash_ignores_comments_whitespace_docstrings():
    a = "def solve(p):\n    return sorted(p)\n"
    b = 'def solve(p):\n    """doc"""\n    # comment\n\n    return sorted( p )   \n'
    c = "def solve(p):\n    return sorted(p, reverse=True)\n"
    assert program_hash(a) == program_hash(b)
    assert program_hash(a) != program_hash(c)
    assert normalize_source("def broken(:\n  x  \n\n") == "def broken(:\n  x"


def test_extract_program_prefers_last_valid_block_defining_function():
    text = ("first try:\n```python\ndef solve(p):\n    return 1\n```\nhelper:\n```python\ndef other():\n    pass\n```\n"
            "final:\n```python\nimport math\n\ndef solve(p):\n    return 2\n```\n")
    assert extract_program(text, "solve").endswith("return 2")
    assert extract_program("no code here", "solve") is None
    assert extract_program("```python\ndef solve(p) return 1\n```", "solve") == "def solve(p) return 1"
    assert extract_program("def solve(p):\n    return 3", "solve") == "def solve(p):\n    return 3"


def test_build_prompt_contains_parents_scores_and_diagnostics():
    ps = [Program(hash="a", src="def solve(p):\n    return 1", score=0.5, diagnostics="hook error at layer 3"),
          Program(hash="b", src="def solve(p):\n    return 2", score=0.9, diagnostics="")]
    pr = build_prompt("TASK DESCRIPTION", "solve", ps)
    assert "TASK DESCRIPTION" in pr and "score 0.5" in pr and "score 0.9" in pr
    assert "hook error at layer 3" in pr
    assert pr.index("return 1") < pr.index("return 2")
    assert "COMPLETE program" in pr


def test_mutate_program_changes_literals_deterministically():
    src = "def f(x):\n    a = 2.0\n    b = 3\n    return a * x + b\n"
    m1 = mutate_program(src, random.Random(1))
    m2 = mutate_program(src, random.Random(1))
    assert m1 == m2
    outs = {mutate_program(src, random.Random(s)) for s in range(20)}
    assert len(outs) > 5


# ----------------------------------------------------------------------------- database
def _p(h, score, idx=0):
    return Program(hash=h, src=f"def solve(p):\n    return {h!r}\n", score=score, eval_index=idx)


def test_database_capacity_selection_and_best_monotone():
    db = ProgramDatabase(num_islands=2, island_capacity=3)
    for i, s in enumerate([0.1, 0.5, 0.3, 0.9, 0.2]):
        db.add(_p(f"h{i}", s, i), 0)
    assert len(db.islands[0]) == 3
    assert sorted(p.score for p in db.islands[0]) == [0.3, 0.5, 0.9]
    assert db.best.score == 0.9
    rng = random.Random(0)
    for _ in range(20):
        par = db.sample_parents(0, 3, rng)
        assert len({p.hash for p in par}) == len(par) == 3
        assert [p.score for p in par] == sorted(p.score for p in par)
    # 高分更常被选中
    counts = {}
    for _ in range(500):
        h = db.sample_parents(0, 1, rng)[0].hash
        counts[h] = counts.get(h, 0) + 1
    assert counts["h3"] > counts.get("h2", 0)


def test_database_reset_copies_elite_and_roundtrips():
    db = ProgramDatabase(num_islands=4, island_capacity=5)
    for isl, s in enumerate([0.2, 0.8, 0.1, 0.5]):
        db.add(_p(f"i{isl}", s), isl)
    reset = db.reset_worst_islands(num_reset=2)
    assert sorted(reset) == [0, 2]
    assert [p.hash for p in db.islands[0]] == ["i1"] and [p.hash for p in db.islands[2]] == ["i1"]
    assert db.islands[0][0].origin == "migrated"
    db2 = ProgramDatabase.from_state(db.state_dict())
    assert db2.state_dict() == db.state_dict()
