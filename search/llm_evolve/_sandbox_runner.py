"""候选程序执行器（在 ``python -I`` 子进程中运行，只依赖标准库）。

协议：stdin 读入一个 JSON 请求
    {"src", "func", "calls": [[args...], ...], "workdir", "mem_mb", "cpu_s",
     "fsize_mb", "deny_roots": [...], "allow_roots": [...], "preimport": [...]}
原始 stdout 只写一行 JSON 结果；候选程序自己的 print 被重定向到 stderr。

这是 best-effort 隔离，局限见 README（audit hook 可被 ctypes/C 扩展绕过等）。
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
    except ImportError:  # 非 POSIX
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
    """macOS 不执行 RLIMIT_AS，用线程轮询峰值 RSS 兜底（超限即 os._exit）。"""
    if not mem_mb:
        return
    import resource

    limit = int(mem_mb) * 1024 * 1024
    scale = 1 if sys.platform == "darwin" else 1024  # ru_maxrss: macOS 字节, Linux KB

    def loop():
        while True:
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * scale
            if rss > limit:
                try:
                    real_out.write(json.dumps({
                        "ok": False, "error_type": "MemoryLimitExceeded",
                        "error": f"peak RSS {rss / 2**20:.0f} MiB > limit {mem_mb} MiB",
                        "traceback": "",
                    }) + "\n")
                    real_out.flush()
                finally:
                    os._exit(3)
            time.sleep(0.02)

    threading.Thread(target=loop, daemon=True, name="mem-watchdog").start()


def _install_audit_hook(workdir, deny_roots, allow_roots):
    real = os.path.realpath
    workdir = real(workdir)
    deny_roots = [real(p) for p in deny_roots]
    allow_roots = [real(p) for p in allow_roots] + [workdir]

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
        if rp is not None and under(rp, deny_roots) and not under(rp, allow_roots):
            raise PermissionError(f"sandbox: {event} of {rp} is denied (protected project directory)")

    def check_write(p, event):
        rp = resolve(p)
        if rp is not None and not under(rp, [workdir]):
            raise PermissionError(f"sandbox: {event} outside the sandbox workdir is denied: {rp}")

    write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
    blocked = {
        "socket.connect", "socket.bind", "socket.sendto", "socket.sendmsg", "socket.getaddrinfo",
        "socket.gethostbyname", "socket.__new__",
        "subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork",
        "os.forkpty", "os.kill", "os.killpg", "pty.spawn",
        "ctypes.dlopen", "ctypes.dlsym", "ctypes.addressof", "ctypes.cdata",
        "ctypes.call_function", "sys._current_frames", "urllib.Request", "http.client.connect",
        "webbrowser.open",
    }
    path_write_events = {
        "os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.chown", "os.truncate",
        "os.utime", "shutil.rmtree", "shutil.copyfile", "shutil.move",
    }
    two_path_events = {"os.rename", "os.link", "os.symlink"}
    read_events = {"os.listdir", "os.scandir", "glob.glob", "os.chdir"}

    def hook(event, args):
        if event in blocked:
            raise PermissionError(f"sandbox: '{event}' is not allowed")
        if event == "open":
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
    req = json.loads(sys.stdin.read())
    real_out = os.fdopen(os.dup(1), "w")
    os.dup2(2, 1)  # 候选程序的 print -> stderr，避免污染结果通道
    sys.stdout = sys.stderr

    def emit(obj):
        real_out.write(json.dumps(obj, default=_jsonable) + "\n")
        real_out.flush()

    limits = _apply_limits(req.get("mem_mb"), req.get("cpu_s"), req.get("fsize_mb"))
    if not isinstance(limits.get("RLIMIT_AS"), int):
        _start_mem_watchdog(req.get("mem_mb"), real_out)
    for mod in req.get("preimport", []):
        try:
            __import__(mod)
        except Exception:
            pass
    _install_audit_hook(req["workdir"], req.get("deny_roots", []), req.get("allow_roots", []))

    t0 = time.perf_counter()
    try:
        import linecache

        linecache.cache["<candidate>"] = (len(req["src"]), None, req["src"].splitlines(True), "<candidate>")
        code = compile(req["src"], "<candidate>", "exec")
        ns = {"__name__": "candidate"}
        exec(code, ns)
        fn = ns.get(req["func"])
        if not callable(fn):
            emit({"ok": False, "error_type": "MissingFunction",
                  "error": f"program does not define a callable '{req['func']}'",
                  "traceback": "", "limits": limits})
            os._exit(0)
        outputs = []
        for args in req["calls"]:
            outputs.append(fn(*args))
        try:
            payload = json.dumps({"ok": True, "outputs": outputs, "limits": limits,
                                  "elapsed": time.perf_counter() - t0}, default=_jsonable)
        except (TypeError, ValueError) as e:
            emit({"ok": False, "error_type": "OutputNotSerializable", "error": str(e),
                  "traceback": "", "limits": limits})
            os._exit(0)
        real_out.write(payload + "\n")
        real_out.flush()
    except BaseException as e:  # noqa: BLE001 —— 包括 SystemExit / RecursionError / MemoryError
        tb = e.__traceback__
        while tb is not None and tb.tb_frame.f_code.co_filename == __file__:
            tb = tb.tb_next  # 去掉执行器自身的栈帧，只保留候选程序的
        emit({"ok": False, "error_type": type(e).__name__, "error": str(e)[:2000],
              "traceback": "".join(traceback.format_exception(type(e), e, tb)), "limits": limits})
    os._exit(0)  # 不运行候选程序注册的 atexit / 不等待其线程


if __name__ == "__main__":
    main()
