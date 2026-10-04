"""解码器候选的沙箱会话（父进程侧；从 search/llm_evolve/sandbox.py 复制并扩展，随评估器冻结，评估器不依赖 search/）。

一个 `DecoderSession` = 一个子进程 = 一个 sector 的一个解码器实例：子进程只收到**本 sector** 的 H / L / priors / info
与本 sector 的 syndrome，拿不到另一个 sector 的任何数据，也拿不到种子或密钥（它们只在父进程里）。

隔离（两层）：
  1. 内核级（macOS，`/usr/bin/sandbox-exec` 存在时默认启用；`use_os_sandbox=True` 时缺失即报错）：SBPL 配置禁止网络、
     禁止在工作目录以外写文件、禁止读家目录 / 项目根目录（worktree 与主目录）/ 系统临时目录（venv 与本会话工作目录除外）
     和密钥文件、禁止 POSIX / SysV 共享内存与信号量、禁止 fork、禁止给其他进程发信号、禁止查询其他进程信息。
  2. Python audit hook（_decoder_runner.py，非 macOS 时是唯一一层）：同样的路径规则 + 禁止 socket / 子进程 / ctypes /
     mmap / mkfifo / 改 rlimit，禁止 import psutil、ctypes、multiprocessing、_posixshmem、socket、subprocess 等。
  另有：`python -I -B`、环境变量白名单（拿不到任何密钥）、全新临时工作目录（0700，结束后删除）、RLIMIT_CPU /
  RLIMIT_FSIZE / 禁 core、内存看门狗、独立进程组（结束时整组 SIGKILL）。

计时：父进程用 psutil 读子进程的累计 CPU 时间（user+system，含所有线程）。第 i 个 shot 的时间 = 收到第 i 个答案时的
累计 CPU − 收到第 i−1 个答案（或 make_decoder 完成）时的累计 CPU，所以两次请求之间后台线程做的功也算进下一个 shot，
没有“躲开计时”的空隙。构建时间（make_decoder）单独记录、单独设上限。
"""
from __future__ import annotations

import json
import os
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import psutil

from evaluators.decoder_problem import project_roots, secret_path

RUNNER = Path(__file__).with_name("_decoder_runner.py")
SANDBOX_EXEC = "/usr/bin/sandbox-exec"
DEFAULT_PREIMPORT = ["math", "itertools", "functools", "collections", "heapq", "random", "numpy", "scipy",
                     "scipy.sparse", "scipy.sparse.csgraph", "ldpc", "relay_bp", "pymatching"]
DENY_IMPORTS = ["psutil", "_psutil_osx", "_psutil_posix", "ctypes", "_ctypes", "cffi", "_cffi_backend",
                "multiprocessing", "_multiprocessing", "_posixshmem", "mmap", "socket", "_socket", "ssl", "_ssl",
                "subprocess", "_posixsubprocess", "asyncio", "concurrent", "selectors", "select", "fcntl",
                "termios", "pty", "sqlite3", "_sqlite3", "dbm", "shelve", "urllib", "http", "ftplib", "smtplib",
                "webbrowser", "importlib.metadata", "pip", "uv", "evaluators", "search", "baselines", "tests",
                "scripts"]
MAX_LINE = 1 << 20        # 子进程一行回复的上限（字节）；超出 = 协议错误


def os_sandbox_available() -> bool:
    return sys.platform == "darwin" and os.path.exists(SANDBOX_EXEC)


def _sb_quote(p: str) -> str:
    return '"' + p.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _real(p) -> str:
    return os.path.realpath(os.fspath(p))


def deny_roots() -> list[str]:
    """沙箱禁止读的目录（venv 与工作目录另行放行）。"""
    roots = [str(r) for r in project_roots()]
    roots.append(_real(Path.home()))
    for t in {tempfile.gettempdir(), "/tmp", "/private/tmp", "/var/tmp", "/private/var/tmp"}:
        roots.append(_real(t))
    roots.append(_real(Path(secret_path()).parent))
    out = []
    for r in roots:
        if r not in out:
            out.append(r)
    return out


def allow_roots() -> list[str]:
    out = []
    for p in (sys.prefix, sys.exec_prefix, sys.base_prefix):
        rp = _real(p)
        if rp not in out:
            out.append(rp)
        if p not in out:
            out.append(os.path.abspath(p))
    return out


def sandbox_profile(workdir: str) -> str:
    """macOS SBPL 配置（后面的规则优先）。"""
    w = _real(workdir)
    lines = ["(version 1)", "(allow default)", "(deny network*)",
             f"(deny file-write* (require-not (subpath {_sb_quote(w)})))",
             '(allow file-write* (literal "/dev/null"))']
    for r in deny_roots():
        lines.append(f"(deny file-read* (subpath {_sb_quote(r)}))")
    # stat / realpath 需要读路径上各级目录的元数据（不含内容、不含目录列表）
    lines.append("(allow file-read-metadata)")
    for r in allow_roots():
        lines.append(f"(allow file-read* (subpath {_sb_quote(r)}))")
    lines.append(f"(allow file-read* (subpath {_sb_quote(w)}))")
    lines.append(f"(allow file-read* (literal {_sb_quote(_real(RUNNER))}))")   # 执行器脚本本身（不含秘密）
    sp_ = _real(secret_path())
    lines.append(f"(deny file-read* (literal {_sb_quote(sp_)}))")
    lines += ["(deny ipc-posix-shm*)", "(deny ipc-posix-sem*)", "(deny ipc-sysv*)", "(deny process-fork)",
              "(deny signal (target others))", "(deny process-info* (target others))"]
    return "\n".join(lines) + "\n"


def _child_env(workdir: str) -> dict[str, str]:
    return {"PATH": "/usr/bin:/bin", "HOME": workdir, "TMPDIR": workdir, "LANG": "C.UTF-8",
            "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
            "VECLIB_MAXIMUM_THREADS": "1", "RAYON_NUM_THREADS": "1", "NUMBA_NUM_THREADS": "1"}


class SessionError(RuntimeError):
    """会话已不可用（超时被杀、崩溃、协议错误、内存超限）。"""

    def __init__(self, kind: str, message: str):
        super().__init__(f"{kind}: {message}")
        self.kind = kind


@dataclass
class ShotReply:
    output: Any = None          # 子进程返回的原始输出（父进程再严格校验）
    error: str | None = None    # 候选 decode 抛异常 / 会话死亡的说明
    cpu_s: float = 0.0          # 本 shot 的 CPU 时间（见模块说明）
    wall_s: float = 0.0
    killed: bool = False        # 超过墙钟上限被杀（会话随之结束）


@dataclass
class DecoderSession:
    src: str
    problem: dict
    info: dict
    func: str = "make_decoder"
    mem_mb: int = 2048
    build_wall_s: float = 300.0
    cpu_s_limit: int | None = None          # RLIMIT_CPU（整个会话），None = 不设
    fsize_mb: int = 16
    use_os_sandbox: bool | None = None      # None = 可用就用
    preimport: list = field(default_factory=lambda: list(DEFAULT_PREIMPORT))

    proc: Any = None
    build_cpu_s: float = 0.0
    build_wall_s_used: float = 0.0
    alive: bool = False
    _ps: Any = None
    _buf: bytes = b""
    _last_cpu: float = 0.0
    _workdir: str | None = None
    _errdir: str | None = None
    _sel: Any = None
    os_sandboxed: bool = False

    # ------------------------------------------------------------------
    def start(self) -> dict:
        """启动子进程并构建解码器。返回 {"ok": bool, "error_type", "error", "traceback", "build_cpu_s", ...}。"""
        use_os = os_sandbox_available() if self.use_os_sandbox is None else bool(self.use_os_sandbox)
        if use_os and not os_sandbox_available():
            raise RuntimeError("OS-level sandbox (sandbox-exec) requested but not available")
        self._workdir = tempfile.mkdtemp(prefix="qec_dec_sbx_")
        os.chmod(self._workdir, 0o700)
        self._errdir = tempfile.mkdtemp(prefix="qec_dec_err_")
        os.chmod(self._errdir, 0o700)
        errf = open(os.path.join(self._errdir, "stderr.txt"), "wb")
        argv = [sys.executable, "-I", "-B", str(RUNNER)]
        if use_os:
            prof = os.path.join(self._errdir, "profile.sb")
            with open(prof, "w") as f:
                f.write(sandbox_profile(self._workdir))
            argv = [SANDBOX_EXEC, "-f", prof] + argv
        self.os_sandboxed = use_os
        cpu_lim = self.cpu_s_limit
        req = {"src": self.src, "func": self.func, "problem": self.problem, "info": self.info,
               "workdir": _real(self._workdir), "mem_mb": self.mem_mb, "cpu_s": cpu_lim, "fsize_mb": self.fsize_mb,
               "deny_roots": deny_roots(), "allow_roots": allow_roots(), "deny_files": [_real(secret_path())],
               "preimport": self.preimport, "deny_imports": DENY_IMPORTS}
        t0 = time.perf_counter()
        self.proc = subprocess.Popen(argv, cwd=self._workdir, env=_child_env(self._workdir), stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=errf, start_new_session=True, bufsize=0)
        errf.close()
        self._ps = psutil.Process(self.proc.pid)
        os.set_blocking(self.proc.stdout.fileno(), False)
        self._sel = selectors.DefaultSelector()
        self._sel.register(self.proc.stdout, selectors.EVENT_READ)
        try:
            self.proc.stdin.write((json.dumps(req) + "\n").encode())
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            self.close()
            return {"ok": False, "error_type": "Crashed", "error": f"could not send the problem: {e}",
                    "stderr": self.stderr_tail()}
        try:
            line = self._readline(self.build_wall_s)
        except SessionError as e:
            cpu = self._cpu()
            self.close()
            return {"ok": False, "error_type": e.kind, "error": str(e), "build_cpu_s": cpu,
                    "stderr": self.stderr_tail()}
        self.build_wall_s_used = time.perf_counter() - t0
        self.build_cpu_s = self._last_cpu = self._cpu()
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            self.close()
            return {"ok": False, "error_type": "ProtocolError", "error": "bad ready line", "stderr": self.stderr_tail()}
        if msg.get("fatal"):
            self.close()
            return {"ok": False, "error_type": msg["fatal"], "error": msg.get("error", ""), "stderr": self.stderr_tail()}
        if not msg.get("ready"):
            self.close()
            return {"ok": False, "error_type": msg.get("error_type"), "error": msg.get("error"),
                    "traceback": msg.get("traceback", ""), "build_cpu_s": self.build_cpu_s,
                    "stderr": self.stderr_tail()}
        self.alive = True
        return {"ok": True, "build_cpu_s": self.build_cpu_s, "build_wall_s": self.build_wall_s_used,
                "limits": msg.get("limits"), "os_sandbox": self.os_sandboxed}

    def _cpu(self) -> float:
        try:
            t = self._ps.cpu_times()
            return float(t.user + t.system)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return self._last_cpu

    def _readline(self, timeout: float) -> str:
        deadline = time.perf_counter() + timeout
        while True:
            i = self._buf.find(b"\n")
            if i >= 0:
                line, self._buf = self._buf[:i], self._buf[i + 1:]
                return line.decode(errors="replace")
            if len(self._buf) > MAX_LINE:
                raise SessionError("ProtocolError", f"reply longer than {MAX_LINE} bytes")
            left = deadline - time.perf_counter()
            if left <= 0:
                raise SessionError("Timeout", f"no reply within {timeout:.3g}s wall clock (process killed)")
            ev = self._sel.select(timeout=min(left, 1.0))
            if not ev:
                if self.proc.poll() is not None:
                    raise SessionError("Crashed", f"process exited with code {self.proc.returncode}")
                continue
            try:
                chunk = os.read(self.proc.stdout.fileno(), 1 << 16)
            except BlockingIOError:
                continue
            if not chunk:
                rc = self.proc.wait(timeout=5)
                kind = "Crashed"
                if rc is not None and rc < 0 and -rc == signal.SIGXCPU:
                    kind = "CPULimitExceeded"
                raise SessionError(kind, f"process exited (code {rc})")
            self._buf += chunk

    def decode(self, shot_id: int, fired: list[int], wall_limit_s: float) -> ShotReply:
        """发一个 shot，等回复。超过 wall_limit_s 墙钟则杀掉会话（ShotReply.killed=True）。"""
        if not self.alive:
            return ShotReply(error="session is not alive", killed=True)
        t0 = time.perf_counter()
        try:
            self.proc.stdin.write((json.dumps({"id": shot_id, "s": fired}) + "\n").encode())
            self.proc.stdin.flush()
            line = self._readline(wall_limit_s)
        except (BrokenPipeError, OSError) as e:
            cpu = self._cpu()
            self.close()
            return ShotReply(error=f"Crashed: {e}", cpu_s=cpu - self._last_cpu, wall_s=time.perf_counter() - t0,
                             killed=True)
        except SessionError as e:
            cpu = self._cpu()
            self.close()
            return ShotReply(error=str(e), cpu_s=max(0.0, cpu - self._last_cpu), wall_s=time.perf_counter() - t0,
                             killed=True)
        cpu = self._cpu()
        dt = max(0.0, cpu - self._last_cpu)
        self._last_cpu = cpu
        wall = time.perf_counter() - t0
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            self.close()
            return ShotReply(error="ProtocolError: reply is not JSON", cpu_s=dt, wall_s=wall, killed=True)
        if not isinstance(msg, dict):
            self.close()
            return ShotReply(error="ProtocolError: reply is not an object", cpu_s=dt, wall_s=wall, killed=True)
        if msg.get("fatal"):
            self.close()
            return ShotReply(error=f"{msg['fatal']}: {msg.get('error', '')}", cpu_s=dt, wall_s=wall, killed=True)
        if msg.get("id") != shot_id:
            self.close()
            return ShotReply(error=f"ProtocolError: reply id {msg.get('id')!r} != {shot_id}", cpu_s=dt, wall_s=wall,
                             killed=True)
        if "err" in msg:
            return ShotReply(error=str(msg["err"])[:400], cpu_s=dt, wall_s=wall)
        if "o" not in msg:
            return ShotReply(error="ProtocolError: reply has no output", cpu_s=dt, wall_s=wall)
        return ShotReply(output=msg["o"], cpu_s=dt, wall_s=wall)

    def total_cpu(self) -> float:
        return self._last_cpu

    def stderr_tail(self, n: int = 1500) -> str:
        if not self._errdir:
            return ""
        try:
            with open(os.path.join(self._errdir, "stderr.txt"), "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - n))
                return f.read().decode(errors="replace")
        except OSError:
            return ""

    def close(self) -> None:
        self.alive = False
        if self.proc is not None:
            try:
                self.proc.stdin.close()
            except OSError:
                pass
            try:
                self.proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                pass
            try:
                os.killpg(self.proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            if self._sel is not None:
                try:
                    self._sel.close()
                except Exception:  # noqa: BLE001
                    pass
                self._sel = None
        if self._workdir:
            shutil.rmtree(self._workdir, ignore_errors=True)
            self._workdir = None

    def cleanup(self) -> None:
        self.close()
        if self._errdir:
            shutil.rmtree(self._errdir, ignore_errors=True)
            self._errdir = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.cleanup()
