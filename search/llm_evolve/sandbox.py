"""在独立子进程中执行候选程序（best-effort 隔离）。

已做到：
* ``python -I -B`` 启动：忽略 PYTHON* 环境变量与用户 site，脚本目录/cwd 不进 sys.path，
  因此候选程序不能直接 ``import evaluators``；
* 子进程环境变量白名单（**不继承 ANTHROPIC_API_KEY 等任何密钥**）；
* 在全新临时目录中运行，结束后删除；
* 墙钟超时：超时后 SIGKILL 整个进程组；
* 内存：先尝试 RLIMIT_AS（Linux 有效）；失败时（macOS 不支持）启用峰值 RSS 看门狗线程兜底；
* RLIMIT_CPU / RLIMIT_FSIZE / 禁 core dump；
* audit hook：禁止写临时目录以外的路径、禁止读项目目录（venv/标准库除外）、
  禁止 socket / 子进程 / fork / ctypes 动态加载。

做不到（详见 README）：没有内核级网络/文件系统隔离；audit hook 可以被 C 扩展绕过；
看门狗只能在分配之后发现超限；不限制 CPU 核数（numpy 多线程）等。
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

RUNNER = Path(__file__).with_name("_sandbox_runner.py")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PREIMPORT = ["math", "itertools", "functools", "collections", "heapq", "random", "numpy"]


@dataclass
class SandboxResult:
    ok: bool
    outputs: list[Any] | None = None
    error_type: str | None = None  # 例如 Timeout / MemoryLimitExceeded / ZeroDivisionError
    error: str | None = None
    traceback: str = ""
    stderr: str = ""
    elapsed: float = 0.0
    returncode: int | None = None
    limits: dict[str, Any] = field(default_factory=dict)

    def diagnostics(self, max_chars: int = 1500) -> str:
        """给 LLM 看的失败说明：异常类型 + 截断后的 traceback 尾部。"""
        if self.ok:
            return ""
        head = f"{self.error_type}: {self.error}"
        tb = self.traceback.strip()
        text = head if not tb else f"{head}\n{tb}"
        return truncate_middle(text, max_chars)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def truncate_middle(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    keep = max_chars - 40
    head = keep // 3
    tail = keep - head
    return f"{text[:head]}\n...[truncated {len(text) - keep} chars]...\n{text[-tail:]}"


def _child_env(workdir: str) -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": workdir,
        "TMPDIR": workdir,
        "LANG": "C.UTF-8",
        # 限制数值库线程数，避免候选程序吃满所有核
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "VECLIB_MAXIMUM_THREADS": "1",
    }


def run_in_sandbox(
    src: str,
    func_name: str,
    calls: list[list[Any]],
    *,
    timeout_s: float = 10.0,
    mem_mb: int | None = 1024,
    cpu_s: int | None = None,
    fsize_mb: int | None = 10,
    max_traceback_chars: int = 4000,
    max_stderr_chars: int = 2000,
    deny_roots: list[str] | None = None,
    preimport: list[str] | None = None,
    python: str | None = None,
) -> SandboxResult:
    """在子进程里 exec(src)，然后对 calls 中每组参数调用 ``func_name(*args)``。

    参数与返回值都必须可 JSON 序列化（返回值里的 numpy 数组/整数会被转成 list/int）。
    ``deny_roots`` 默认是项目根目录（禁止候选程序读取评估器等源码；venv 例外）。
    """
    if cpu_s is None:
        cpu_s = max(1, int(timeout_s) + 1)
    deny = [str(PROJECT_ROOT)] if deny_roots is None else list(deny_roots)
    with tempfile.TemporaryDirectory(prefix="llm_evolve_sbx_") as workdir:
        req = {
            "src": src, "func": func_name, "calls": calls, "workdir": workdir,
            "mem_mb": mem_mb, "cpu_s": cpu_s, "fsize_mb": fsize_mb,
            "deny_roots": deny, "allow_roots": [sys.prefix, sys.base_prefix, sys.exec_prefix],
            "preimport": DEFAULT_PREIMPORT if preimport is None else preimport,
        }
        t0 = time.perf_counter()
        proc = subprocess.Popen(
            [python or sys.executable, "-I", "-B", str(RUNNER)],
            cwd=workdir, env=_child_env(workdir),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True,  # 独立进程组，超时可整组杀掉
        )
        timed_out = False
        try:
            out, err = proc.communicate(json.dumps(req).encode(), timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_group(proc)
            out, err = proc.communicate()
        elapsed = time.perf_counter() - t0
        _kill_group(proc)  # 清理候选程序可能遗留的后代进程（正常情况下 fork 已被禁止）

    stderr = truncate_middle(err.decode(errors="replace"), max_stderr_chars)
    if timed_out:
        return SandboxResult(ok=False, error_type="Timeout",
                             error=f"exceeded wall-clock limit of {timeout_s:.1f}s (process killed)",
                             stderr=stderr, elapsed=elapsed, returncode=proc.returncode)
    line = out.decode(errors="replace").strip().splitlines()
    if not line:
        rc = proc.returncode
        reason = "killed by signal " + signal.Signals(-rc).name if rc is not None and rc < 0 else f"exit code {rc}"
        if rc is not None and rc < 0 and -rc == signal.SIGXCPU:
            etype = "CPULimitExceeded"
        elif rc is not None and rc < 0 and -rc in (signal.SIGKILL, signal.SIGSEGV):
            etype = "Crashed"
        else:
            etype = "NoResult"
        return SandboxResult(ok=False, error_type=etype, error=f"runner produced no result ({reason})",
                             stderr=stderr, elapsed=elapsed, returncode=rc)
    try:
        res = json.loads(line[-1])
    except json.JSONDecodeError as e:
        return SandboxResult(ok=False, error_type="ProtocolError", error=f"bad runner output: {e}",
                             stderr=stderr, elapsed=elapsed, returncode=proc.returncode)
    return SandboxResult(
        ok=bool(res.get("ok")), outputs=res.get("outputs"), error_type=res.get("error_type"),
        error=res.get("error"), traceback=truncate_middle(res.get("traceback", ""), max_traceback_chars),
        stderr=stderr, elapsed=elapsed, returncode=proc.returncode, limits=res.get("limits", {}),
    )


def _kill_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
