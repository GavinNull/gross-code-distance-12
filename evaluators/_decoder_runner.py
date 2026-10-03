"""解码器候选的执行器（在沙箱子进程里运行；从 search/llm_evolve/_sandbox_runner.py 复制并扩展，随评估器冻结）。

协议（逐行 JSON，stdin / 原始 stdout）：
  1. 父进程 → 子进程，第一行：
       {"src", "func": "make_decoder", "problem": {num_det, num_obs, num_mech, H_cols, L_cols, priors}, "info",
        "workdir", "mem_mb", "cpu_s", "fsize_mb", "deny_roots", "allow_roots", "deny_files", "preimport",
        "deny_imports"}
     子进程构造 H（scipy.sparse.csc_matrix, uint8）、L（csr, uint8）、priors（float64），装好 audit hook，
     exec 候选源码，调用 make_decoder(H, L, priors, info) 得到 decode 函数，回一行
       {"ready": true} 或 {"ready": false, "error_type", "error", "traceback"}。
  2. 循环：父进程发 {"id": i, "s": [触发的 detector 下标]}，子进程调用 decode(syndrome)（uint8 数组，长度 num_det），
     回 {"id": i, "o": 输出} 或 {"id": i, "err": "..."}。父进程严格校验输出（长度 k、元素只能是 0/1），这里只做
     JSON 化。一次只发一个 shot：候选在给出第 i 个答案之前看不到第 i+1 个 syndrome。
  3. 父进程关闭 stdin → 子进程退出（os._exit，不跑候选注册的 atexit）。

候选自己的 print 被重定向到 stderr（父进程把 stderr 接到文件，截断后作诊断）。
隔离（父进程另外用 macOS sandbox-exec 做内核级限制，见 decoder_sandbox.py）：audit hook 禁止写工作目录以外的路径、
禁止读 deny_roots（家目录、项目根目录（worktree 与主目录）、系统临时目录，venv 与工作目录除外）与 deny_files（密钥），
禁止 socket / 子进程 / fork / exec / ctypes / 信号 / 共享内存，禁止 import deny_imports 里的模块（psutil、ctypes、
multiprocessing、_posixshmem、mmap、socket、subprocess 等）。
"""

import json
import os
import sys
import threading
import time
import traceback


def _apply_limits(mem_mb, cpu_s, fsize_mb):
    applied = {}
    try:
        import resource
    except ImportError:
        return {"resource": "unavailable"}

    def _set(name, value):
        lim = getattr(resource, name, None)
        if lim is None:
            applied[name] = "unsupported"
            return
        try:
            _soft, hard = resource.getrlimit(lim)
            if hard != resource.RLIM_INFINITY and value > hard:
                value = hard
            resource.setrlimit(lim, (value, hard))
            applied[name] = value
        except (ValueError, OSError) as e:
            applied[name] = f"failed: {e}"

    if mem_mb:
        _set("RLIMIT_AS", int(mem_mb) * 1024 * 1024)
    if cpu_s:
        _set("RLIMIT_CPU", int(cpu_s))
    if fsize_mb is not None:
        _set("RLIMIT_FSIZE", int(fsize_mb) * 1024 * 1024)
    _set("RLIMIT_CORE", 0)
    return applied


def _start_mem_watchdog(mem_mb, real_out):
    if not mem_mb:
        return
    import resource

    limit = int(mem_mb) * 1024 * 1024
    scale = 1 if sys.platform == "darwin" else 1024

    def loop():
        while True:
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * scale
            if rss > limit:
                try:
                    real_out.write(json.dumps({"fatal": "MemoryLimitExceeded",
                                               "error": f"peak RSS {rss / 2**20:.0f} MiB > limit {mem_mb} MiB"}) + "\n")
                    real_out.flush()
                finally:
                    os._exit(3)
            time.sleep(0.02)

    threading.Thread(target=loop, daemon=True, name="mem-watchdog").start()


def _install_audit_hook(workdir, deny_roots, allow_roots, deny_files, deny_imports):
    real = os.path.realpath
    workdir = real(workdir)
    deny_roots = [real(p) for p in deny_roots]
    allow_roots = [real(p) for p in allow_roots] + [workdir]
    deny_files = [real(p) for p in deny_files]
    deny_imports = set(deny_imports)

    def under(path, roots):
        return any(path == r or path.startswith(r.rstrip(os.sep) + os.sep) for r in roots)

    def resolve(p):
        if isinstance(p, int):
            return None
        if isinstance(p, bytes):
            p = os.fsdecode(p)
        try:
            return real(os.fspath(p))
        except TypeError:
            return None

    def check_read(p, event):
        rp = resolve(p)
        if rp is None:
            return
        if under(rp, deny_files) or (under(rp, deny_roots) and not under(rp, allow_roots)):
            raise PermissionError(f"sandbox: {event} of {rp} is denied")

    def check_write(p, event):
        rp = resolve(p)
        if rp is not None and not under(rp, [workdir]):
            raise PermissionError(f"sandbox: {event} outside the sandbox workdir is denied: {rp}")

    write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
    blocked = {
        "socket.connect", "socket.bind", "socket.sendto", "socket.sendmsg", "socket.getaddrinfo",
        "socket.gethostbyname", "socket.__new__",
        "subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork",
        "os.forkpty", "os.kill", "os.killpg", "pty.spawn", "signal.pthread_kill",
        "ctypes.dlopen", "ctypes.dlsym", "ctypes.addressof", "ctypes.cdata", "ctypes.cdata/buffer",
        "ctypes.call_function", "ctypes.string_at", "ctypes.wstring_at", "ctypes.create_string_buffer",
        "sys._current_frames", "urllib.Request", "http.client.connect", "webbrowser.open", "mmap.__new__",
        "os.mkfifo", "os.mknod", "resource.setrlimit", "resource.prlimit",
    }
    path_write_events = {
        "os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.chown", "os.truncate",
        "os.utime", "shutil.rmtree", "shutil.copyfile", "shutil.move", "os.chflags", "os.lchflags",
        "os.setxattr", "os.removexattr",
    }
    two_path_events = {"os.rename", "os.link", "os.symlink"}
    read_events = {"os.listdir", "os.scandir", "glob.glob", "os.chdir", "os.listxattr", "os.getxattr"}

    def hook(event, args):
        if event in blocked:
            raise PermissionError(f"sandbox: '{event}' is not allowed")
        if event == "import":
            name = args[0] if args else ""
            if name in deny_imports or (isinstance(name, str) and name.split(".")[0] in deny_imports):
                raise PermissionError(f"sandbox: importing {name!r} is not allowed")
        elif event == "open":
            path, mode, flags = args[0], args[1], args[2]
            writing = (mode is not None and any(c in str(mode) for c in "wax+")) or (
                isinstance(flags, int) and flags & write_flags)
            if writing:
                check_write(path, "write-open")
            else:
                check_read(path, "open")
        elif event in path_write_events:
            check_write(args[0], event)
        elif event in two_path_events:
            check_write(args[0], event)
            check_write(args[1], event)
        elif event in read_events and args:
            check_read(args[0], event)

    sys.addaudithook(hook)


def _jsonable(o):
    if hasattr(o, "tolist"):
        return o.tolist()
    if hasattr(o, "__index__"):
        return int(o)
    if hasattr(o, "__float__"):
        return float(o)
    if isinstance(o, (set, frozenset, tuple)):
        return list(o)
    raise TypeError(f"output of type {type(o).__name__} is not JSON-serializable")


def main():
    stdin = sys.stdin
    real_out = os.fdopen(os.dup(1), "w")
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    _dumps = json.dumps          # 本地引用：候选之后改 json 模块不影响协议（改了也只会弄坏自己的答案）
    _loads = json.loads

    def emit(obj):
        real_out.write(_dumps(obj, default=_jsonable) + "\n")
        real_out.flush()

    req = _loads(stdin.readline())
    limits = _apply_limits(req.get("mem_mb"), req.get("cpu_s"), req.get("fsize_mb"))
    if not isinstance(limits.get("RLIMIT_AS"), int):
        _start_mem_watchdog(req.get("mem_mb"), real_out)
    for mod in req.get("preimport", []):
        try:
            __import__(mod)
        except Exception:
            pass
    import numpy as np
    import scipy.sparse as sp

    P = req["problem"]
    nd, no, nm = int(P["num_det"]), int(P["num_obs"]), int(P["num_mech"])
    rows = [r for col in P["H_cols"] for r in col]
    cols = [j for j, col in enumerate(P["H_cols"]) for _ in col]
    H = sp.csc_matrix((np.ones(len(rows), dtype=np.uint8), (rows, cols)), shape=(nd, nm))
    orows = [r for col in P["L_cols"] for r in col]
    ocols = [j for j, col in enumerate(P["L_cols"]) for _ in col]
    L = sp.csr_matrix((np.ones(len(orows), dtype=np.uint8), (orows, ocols)), shape=(no, nm))
    priors = np.asarray(P["priors"], dtype=np.float64)
    info = req.get("info") or {}
    del P, req["problem"]

    _install_audit_hook(req["workdir"], req.get("deny_roots", []), req.get("allow_roots", []),
                        req.get("deny_files", []), req.get("deny_imports", []))
    try:
        import linecache

        linecache.cache["<candidate>"] = (len(req["src"]), None, req["src"].splitlines(True), "<candidate>")
        code = compile(req["src"], "<candidate>", "exec")
        ns = {"__name__": "candidate"}
        exec(code, ns)
        fn = ns.get(req["func"])
        if not callable(fn):
            emit({"ready": False, "error_type": "MissingFunction",
                  "error": f"program does not define a callable '{req['func']}'", "traceback": ""})
            os._exit(0)
        decode = fn(H, L, priors, info)
        if not callable(decode):
            emit({"ready": False, "error_type": "BadDecoder",
                  "error": f"{req['func']} must return a callable decode(syndrome)", "traceback": ""})
            os._exit(0)
    except BaseException as e:  # noqa: BLE001
        tb = e.__traceback__
        while tb is not None and tb.tb_frame.f_code.co_filename == __file__:
            tb = tb.tb_next
        emit({"ready": False, "error_type": type(e).__name__, "error": str(e)[:2000],
              "traceback": "".join(traceback.format_exception(type(e), e, tb))[-4000:]})
        os._exit(0)
    emit({"ready": True, "limits": limits})

    zeros = np.zeros
    uint8 = np.uint8
    readline = stdin.readline
    while True:
        line = readline()
        if not line:
            break
        try:
            msg = _loads(line)
            sid = msg["id"]
            syn = zeros(nd, dtype=uint8)
            syn[msg["s"]] = 1
        except Exception as e:  # noqa: BLE001
            emit({"fatal": "ProtocolError", "error": str(e)[:500]})
            break
        try:
            out = decode(syn)
            payload = _dumps({"id": sid, "o": out}, default=_jsonable)
        except BaseException as e:  # noqa: BLE001
            payload = _dumps({"id": sid, "err": f"{type(e).__name__}: {str(e)[:300]}"})
        real_out.write(payload + "\n")
        real_out.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
