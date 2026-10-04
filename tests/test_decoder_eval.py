"""解码器任务（H-005）的评估器测试：任务、电路、参考一致性、沙箱攻击、速度预算、格式、种子保密、成绩单、mp_rule。

大多数测试用自检任务 selftest-surface-d5-dec（表面码 d=5，公开种子 / 临时密钥），每次评估 1 个 worker、500 shot。
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

from evaluators import decoder_problem as dp
from evaluators.decoder_eval import evaluate_decoder, validate_output
from evaluators.decoder_refs import program_for
from evaluators.decoder_sandbox import os_sandbox_available, sandbox_profile
from evaluators.tasks import RELAY_BP_PAPER, TASKS, get_task

ST = "selftest-surface-d5-dec"
N = 500
HAVE_OS_SB = os_sandbox_available()


@pytest.fixture(scope="module", autouse=True)
def temp_secret(tmp_path_factory):
    """测试用密钥（在 repo 外的临时目录，0600）。"""
    d = tmp_path_factory.mktemp("secret")
    p = d / "decoder_secret.key"
    p.write_text("ab" * 32 + "\n")
    os.chmod(p, 0o600)
    old = os.environ.get(dp.SECRET_ENV)
    os.environ[dp.SECRET_ENV] = str(p)
    yield p
    if old is None:
        os.environ.pop(dp.SECRET_ENV, None)
    else:
        os.environ[dp.SECRET_ENV] = old


def ev(src, split="public", shots=N, **kw):
    kw.setdefault("num_workers", 1)
    return evaluate_decoder(ST, src, split=split, shots=shots, submit=False, **kw)


def direct(src, sector_data, inst, sector):
    ns = {"__name__": "direct"}
    exec(compile(src, "<direct>", "exec"), ns)
    P = inst.sectors[sector]
    dec = ns["make_decoder"](P.H, P.L, P.priors, inst.info(sector))
    dets, obs = sector_data
    return np.array([(np.asarray(dec(dets[i].astype(np.uint8))).astype(bool) != obs[i]).any()
                     for i in range(len(dets))])


# ---------------------------------------------------------------------------
# 任务与电路
# ---------------------------------------------------------------------------

def test_existing_task_hashes_unchanged():
    want = {
        "gross-sd6-p4e-3": "8d0ae4516e3716b10effbae69ab5ee62fa2e386cde64bddf7c99b775754ac221",
        "selftest-surface-d3-sd6-paper": "3f82067f504e3cb2b66e2a3558f4ddad90e65c0b3e47ae8b1ae2f62869bff8c8",
        "selftest-surface-d3-sd6-diff": "9f8c6287a7fbca9fd588b98313bd981171511e3e7ab938c134fe901cc8d680b6",
        "bb72-dcirc": "6f4af1031955b5a9f3fa27fdfc221e5034533b3b04d4a8875bdfdf92f0d02f2d",
        "bb90-dcirc": "7ef6ce7f9891be4deb6c74584a49251c6526cdf6af5772c58a6df02d33eed491",
        "bb108-dcirc": "4f3b6a6b894190b6d321e446f17ad9e3c0257c5460907cbc15a897aed0aefc19",
        "bb120-dcirc": "1a7e159b0c07661e2811fd9e1bc3e57c9f248cf50af8e592845beeb76fe9fed6",
        "cp126-dcirc": "af78ec6ef1e56350c5424d287f5ace6d2e81daf55c7b1991d7ddf9b493567bf0",
        "gross-dcirc": "03a69a4fc219feadd129b17cbe2aa7b05b290fc6210eb73d37d1033c60a94a67",
    }
    for tid, h in want.items():
        assert TASKS[tid].hash() == h, tid


def test_decoder_tasks_registered_and_validated():
    for tid in ("bb72-dec-p3e-3", "bb90-dec-p3e-3", "bb72-mp-p3e-3", ST):
        t = get_task(tid)
        assert t.kind == "decoder" and t.noise_model == "sd6" and t.boundary == "paper"
        assert t.decoder["reference"]["name"] in ("relay_bp", "mp_relay")
        assert t.num_workers <= 3
    assert get_task("bb72-dec-p3e-3").rounds == 6 and get_task("bb90-dec-p3e-3").rounds == 10
    assert get_task("bb72-dec-p3e-3").decoder["reference"]["params"] == RELAY_BP_PAPER


@pytest.mark.parametrize("which", ["bb72", "gross"])
def test_ibm_schedule_matches_baselines(which):
    from baselines.bb_code import BBCode
    from baselines.schedule import ibm_depth8
    from schedule_helpers import from_baseline
    l, m = (6, 6) if which == "bb72" else (12, 6)
    A, B = ["x^3", "y", "y^2"], ["y^3", "x", "x^2"]
    mine = dp.ibm_schedule(l, m, A, B)
    theirs = from_baseline(ibm_depth8(BBCode(l, m, A, B)))
    assert mine.canonical().hash() == theirs.canonical().hash()


def test_instance_structure_bb72():
    inst = dp.build_instance(get_task("bb72-dec-p3e-3"))
    for s in "ZX":
        P = inst.sectors[s]
        assert P.num_det == 36 * 7 and P.num_obs == 12
        assert P.H.shape[1] == P.L.shape[1] == len(P.priors)
        assert (np.asarray(P.H.sum(axis=0)).ravel() > 0).all()
        info = inst.info(s)
        assert info["sector"] == s and len(info["detector_coords"]) == P.num_det
        assert "seed" not in json.dumps(info).lower()


# ---------------------------------------------------------------------------
# 参考一致性：表面码 pymatching、Relay-BP
# ---------------------------------------------------------------------------

def test_pymatching_candidate_matches_direct_pymatching():
    import pymatching
    t = get_task(ST)
    inst = dp.build_instance(t)
    rep = ev(program_for("pymatching", {}))
    assert rep.status == "searched"
    d = dp.sample_batch(inst, dp.split_root(ST, t.hash(), "public"), 0, N)
    fails = {}
    for s in "ZX":
        P = inst.sectors[s]
        p = np.clip(P.priors, 1e-15, 0.5)
        m = pymatching.Matching.from_check_matrix(P.H, weights=np.log((1 - p) / p), faults_matrix=P.L)
        pred = m.decode_batch(d[s][0].astype(np.uint8)).astype(bool)
        fails[s] = (pred != d[s][1]).any(axis=1)
    assert rep.counts["fail_Z"] == int(fails["Z"].sum())
    assert rep.counts["fail_X"] == int(fails["X"].sum())
    assert rep.counts["fail_any"] == int((fails["Z"] | fails["X"]).sum())
    assert rep.sectors["Z"]["timeout"] == rep.sectors["X"]["timeout"] == 0


def test_relay_candidate_matches_official_package_and_reference():
    import relay_bp
    t = get_task(ST)
    inst = dp.build_instance(t)
    rep = ev(program_for("relay_bp", RELAY_BP_PAPER))
    assert rep.status == "searched"
    # 与参考（同一程序、同一 shot、同一 worker 划分）逐 shot 相同
    assert rep.counts == rep.reference["counts"]
    d = dp.sample_batch(inst, dp.split_root(ST, t.hash(), "public"), 0, N)
    fails = {}
    for s in "ZX":
        P = inst.sectors[s]
        p = RELAY_BP_PAPER
        dec = relay_bp.RelayDecoderF64(P.H.tocsr(), error_priors=P.priors, alpha=None, gamma0=p["gamma0"],
                                       pre_iter=p["pre_iter"], num_sets=p["num_sets"], set_max_iter=p["set_max_iter"],
                                       gamma_dist_interval=tuple(p["gamma_dist_interval"]), stop_nconv=p["stop_nconv"],
                                       seed=p["seed"])
        run = relay_bp.ObservableDecoderRunner(dec, P.L.tocsc(), include_decode_result=False)
        pred = np.array([run.decode_observables(d[s][0][i].astype(np.uint8)) for i in range(N)]).astype(bool)
        fails[s] = (pred != d[s][1]).any(axis=1)
    assert rep.counts["fail_Z"] == int(fails["Z"].sum())
    assert rep.counts["fail_X"] == int(fails["X"].sum())
    assert rep.counts["fail_any"] == int((fails["Z"] | fails["X"]).sum())


# ---------------------------------------------------------------------------
# 沙箱攻击
# ---------------------------------------------------------------------------

ATTACK_WRAPPER = '''\
import os
def make_decoder(H, L, priors, info):
    try:
{body}
    except BaseException as e:
        raise RuntimeError("BLOCKED " + type(e).__name__ + ": " + str(e)[:200])
    raise RuntimeError("LEAKED")
'''


def _attack(body: str) -> str:
    return ATTACK_WRAPPER.format(body="\n".join("        " + ln for ln in body.strip().splitlines()))


def _attacks(secret: Path) -> dict:
    roots = dp.project_roots()
    main = roots[-1]
    tmp_root = os.path.realpath(tempfile.gettempdir())
    return {
        "read_evaluator_source": f"open({str(dp.EVAL_DIR / 'tasks.py')!r}).read()",
        "read_main_checkout": f"open({str(main / 'CLAUDE.md')!r}).read()",
        "read_main_evaluators": f"os.listdir({str(main / 'evaluators')!r})",
        "read_secret": f"open({str(secret)!r}).read()",
        "read_home": f"os.listdir({os.path.expanduser('~')!r})",
        "list_temp_root_for_other_sector": f"os.listdir({tmp_root!r})",
        "write_outside_workdir": "open('/tmp/qec_dec_leak_test.txt', 'w').write('x')",
        "symlink_outside": "os.symlink('/etc/hosts', '/tmp/qec_dec_leak_link')",
        "mkfifo_channel": "os.mkfifo('/tmp/qec_dec_fifo')",
        "import_psutil": "import psutil\npsutil.Process(os.getppid()).cmdline()",
        "import_ctypes": "import ctypes",
        "ctypes_via_sys_modules": "import sys\nc = sys.modules.get('ctypes') or sys.modules.get('_ctypes')\nassert c is None, 'ctypes reachable'\nraise PermissionError('not reachable')",
        "ctypes_dlopen_via_numpy": "import numpy._core._internal as ni\nni.ctypes.CDLL(None).getpid()",
        "shared_memory": "from multiprocessing import shared_memory\nshared_memory.SharedMemory(name='qecleak', create=True, size=64)",
        "posixshmem": "import _posixshmem",
        "mmap": "import mmap\nmmap.mmap(-1, 4096)",
        "socket": "import socket\nsocket.socket()",
        "subprocess": "import subprocess\nsubprocess.run(['true'])",
        "os_system": "os.system('true')",
        "fork": "os.fork()",
        "signal_parent": "os.kill(os.getppid(), 0)",
        "import_evaluator": "import evaluators.decoder_problem",
        "env_secret": "assert 'QEC_DECODER_SECRET_FILE' not in os.environ and 'ANTHROPIC_API_KEY' not in os.environ\nraise PermissionError('env clean')",
        "raise_rlimit": "import resource\nresource.setrlimit(resource.RLIMIT_CPU, (10**6, 10**6))",
    }


ATTACK_NAMES = list(_attacks(Path("/x")).keys())


@pytest.mark.parametrize("name", ATTACK_NAMES)
@pytest.mark.parametrize("os_sb", [True, False] if HAVE_OS_SB else [False])
def test_sandbox_attack_blocked(name, os_sb, temp_secret):
    src = _attack(_attacks(temp_secret)[name])
    rep = ev(src, shots=N, use_os_sandbox=os_sb)
    text = rep.to_text()
    assert rep.status == "rejected", text
    assert "LEAKED" not in text, text
    assert "BLOCKED" in text, text
    assert not os.path.exists("/tmp/qec_dec_leak_test.txt")
    assert not os.path.lexists("/tmp/qec_dec_leak_link")
    assert not os.path.exists("/tmp/qec_dec_fifo")


@pytest.mark.skipif(not HAVE_OS_SB, reason="needs macOS sandbox-exec")
def test_os_sandbox_profile_blocks_independently_of_python(temp_secret, tmp_path):
    """内核级一层不依赖 audit hook：sandbox-exec + 同一配置下 /bin/cat 读不到密钥 / 评估器源码，写不了工作目录外。"""
    w = tmp_path / "w"
    w.mkdir()
    prof = tmp_path / "p.sb"
    prof.write_text(sandbox_profile(str(w)))
    for target in (str(temp_secret), str(dp.EVAL_DIR / "tasks.py"), str(dp.project_roots()[-1] / "CLAUDE.md")):
        r = subprocess.run(["/usr/bin/sandbox-exec", "-f", str(prof), "/bin/cat", target], capture_output=True)
        assert r.returncode != 0 and b"Operation not permitted" in r.stderr, target
    r = subprocess.run(["/usr/bin/sandbox-exec", "-f", str(prof), "/usr/bin/touch", str(tmp_path / "outside")],
                       capture_output=True)
    assert r.returncode != 0 and not (tmp_path / "outside").exists()
    r = subprocess.run(["/usr/bin/sandbox-exec", "-f", str(prof), "/usr/bin/touch", str(w / "inside")],
                       capture_output=True)
    assert r.returncode == 0 and (w / "inside").exists()


def test_sectors_never_run_concurrently_and_see_only_their_own_data():
    """每个 sector 的程序只拿到自己 sector 的 info；一个 sector 运行时另一个 sector 的进程处于暂停状态。"""
    src = '''\
import os, time
def make_decoder(H, L, priors, info):
    k = L.shape[0]
    assert info["sector"] in ("Z", "X") and H.shape[0] == info["num_detectors"]
    assert "other" not in str(info).lower()
    def decode(s):
        assert len(s) == H.shape[0]
        return [0] * k
    return decode
'''
    import psutil

    from evaluators import decoder_eval as de
    inst = dp.build_instance(get_task(ST))
    t = get_task(ST)
    runner = de._ProgramRunner(src, inst, t, workers=2, use_os_sandbox=None)
    try:
        d = dp.sample_batch(inst, dp.split_root(ST, t.hash(), "public"), 0, 50)
        ids = np.arange(50)
        runner.run_round("Z", [(ids, d["Z"][0], d["Z"][1])] * 2)
        seen = {}

        orig = de._Worker.run

        def spy(self, sector, *a, **k):
            other = "X" if sector == "Z" else "Z"
            s = self.sessions.get(other)
            if s is not None and s.alive:
                seen.setdefault(sector, []).append(psutil.Process(s.proc.pid).status())
            return orig(self, sector, *a, **k)

        de._Worker.run = spy
        try:
            runner.run_round("X", [(ids, d["X"][0], d["X"][1])] * 2)
            runner.run_round("Z", [(ids, d["Z"][0], d["Z"][1])] * 2)
        finally:
            de._Worker.run = orig
        assert seen["X"] and all(x == psutil.STATUS_STOPPED for x in seen["X"]), seen
        assert seen["Z"] and all(x == psutil.STATUS_STOPPED for x in seen["Z"]), seen
        assert all(w.dead["Z"] is None and w.dead["X"] is None for w in runner.workers)
    finally:
        runner.close()


def test_numpy_global_random_state_does_not_affect_sampling():
    t = get_task(ST)
    inst = dp.build_instance(t)
    root = dp.split_root(ST, t.hash(), "public")
    np.random.seed(0)
    a = dp.sample_batch(inst, root, 3, 200)
    np.random.seed(12345)
    import random
    random.seed(7)
    b = dp.sample_batch(inst, root, 3, 200)
    for s in "ZX":
        assert np.array_equal(a[s][0], b[s][0]) and np.array_equal(a[s][1], b[s][1])


def test_candidate_randomness_cannot_guess_observables():
    """候选在子进程里重设 numpy / random 的种子去“复现”评估器的采样：拿不到种子，只能瞎猜，表现远差于真实解码。"""
    src = '''\
import numpy as np
def make_decoder(H, L, priors, info):
    k = L.shape[0]
    rng = np.random.default_rng(20261003)
    np.random.seed(0)
    def decode(s):
        return (rng.random(k) < 0.02).astype(np.uint8)
    return decode
'''
    rep = ev(src)
    ref = rep.reference["counts"]
    assert rep.counts["fail_any"] > 3 * max(ref["fail_any"], 1)


# ---------------------------------------------------------------------------
# 输出格式、异常、超时、预算
# ---------------------------------------------------------------------------

def test_validate_output_strict():
    assert validate_output([0, 1, True, False], 4)[1] is None
    for bad in ([0, 1, 2, 0], [0, 1], [0, 1, 0, 1, 0], [0.0, 1, 0, 0], ["0", 1, 0, 0], [[0], 1, 0, 0],
                {"a": 1}, "0101", None, 5):
        assert validate_output(bad, 4)[1] is not None, bad


@pytest.mark.parametrize("ret,kind", [
    ("[2] * k", "format"), ("[0] * (k + 1)", "format"), ("['0'] * k", "format"), ("[0.0] * k", "format"),
    ("{'bits': [0] * k}", "format"), ("[[0]] * k", "format"), ("None", "format"),
    ("np.zeros(k, dtype=bool)", "ok"), ("np.zeros(k, dtype=np.uint8)", "ok"),
])
def test_output_format_attacks_count_as_failures(ret, kind):
    src = f'''\
import numpy as np
def make_decoder(H, L, priors, info):
    k = L.shape[0]
    def decode(s):
        return {ret}
    return decode
'''
    rep = ev(src, shots=N)
    for s in "ZX":
        st = rep.sectors[s]
        if kind == "format":
            assert st["format"] == N and st["failures"] == N
        else:
            assert st["format"] == 0
    if kind == "format":
        assert rep.counts["fail_any"] == N


def test_huge_output_is_protocol_error_and_fails():
    src = '''\
def make_decoder(H, L, priors, info):
    return lambda s: [0] * 3_000_000
'''
    rep = ev(src, shots=N)
    assert rep.counts["fail_any"] == N


def test_forged_reply_lines_on_raw_stdout_fail():
    """候选直接往原始 stdout 的 fd 写“答案”行（id 对不上）：协议错误，shot 失败，不能抢答。"""
    src = '''\
import os
def make_decoder(H, L, priors, info):
    k = L.shape[0]
    def decode(s):
        for fd in range(3, 12):
            try:
                os.write(fd, b'{"id": 999999999, "o": [0]}\\n')
            except OSError:
                pass
        return [0] * k
    return decode
'''
    rep = ev(src, shots=N)
    assert rep.status in ("rejected", "searched")
    assert rep.counts["fail_any"] >= rep.reference["counts"]["fail_any"]


def test_exceptions_count_as_failures():
    src = '''\
def make_decoder(H, L, priors, info):
    k = L.shape[0]
    def decode(s):
        if s.sum() % 2:
            raise ValueError("odd")
        return [0] * k
    return decode
'''
    rep = ev(src)
    assert rep.status == "searched"
    assert rep.sectors["Z"]["error"] > 0 and rep.sectors["X"]["error"] > 0


def test_wall_clock_timeout_kills_and_counts_as_failure():
    """在两个最重的 syndrome 上 sleep：墙钟超限被杀、会话重启，这两个 shot 按失败计，其余照常。"""
    t = get_task(ST)
    inst = dp.build_instance(t)
    d = dp.sample_batch(inst, dp.split_root(ST, t.hash(), "public"), 0, N)
    def key(v):
        return ",".join(map(str, np.flatnonzero(v).tolist()))
    slow = {}
    for s in "ZX":
        order = np.argsort(-d[s][0].sum(axis=1), kind="stable")[:2]
        slow[s] = sorted({key(d[s][0][i]) for i in order})
    n_slow = {s: sum(key(d[s][0][i]) in slow[s] for i in range(N)) for s in "ZX"}
    assert all(1 <= v <= 3 for v in n_slow.values()), n_slow
    src = f'''\
import time
import numpy as np
SLOW = {slow!r}
def make_decoder(H, L, priors, info):
    k = L.shape[0]
    slow = set(SLOW[info["sector"]])
    def decode(s):
        if ",".join(map(str, np.flatnonzero(s).tolist())) in slow:
            time.sleep(120)
        return [0] * k
    return decode
'''
    import dataclasses
    import time

    from evaluators import decoder_eval as de
    t2 = dataclasses.replace(t, decoder=dict(t.decoder, speed=dict(t.decoder["speed"], shot_wall_s=2.0)))
    runner = de._ProgramRunner(src, inst, t2, workers=1, use_os_sandbox=None)
    t0 = time.perf_counter()
    try:
        for s in "ZX":
            (st, co, cp, ms), = runner.run_round(s, [(np.arange(N), d[s][0], d[s][1])])
            assert int((st == de._ST["timeout"]).sum()) == n_slow[s]
            assert runner.restarts(s) == n_slow[s] and runner.dead[s] is None
            assert int((st == de._ST["dead"]).sum()) == 0          # 其余 shot 照常运行
    finally:
        runner.close()
    assert time.perf_counter() - t0 < 60


def test_cpu_over_cap_counts_as_timeout():
    src = '''\
import time
def make_decoder(H, L, priors, info):
    k = L.shape[0]
    n = [0]
    def decode(s):
        n[0] += 1
        if n[0] % 50 == 0:
            t = time.process_time()
            while time.process_time() - t < 0.3:
                pass
        return [0] * k
    return decode
'''
    rep = ev(src, shots=N)
    for s in "ZX":
        # 0.3 s CPU 远超上限；墙钟也可能超限而被杀（会话重启后计数器归零，所以次数 < 10）
        assert rep.sectors[s]["timeout"] >= 4, rep.to_text()


def test_background_thread_work_is_charged():
    """在 shot 之间用后台线程“偷算”：CPU 时间按“上一个回复到这一个回复”的累计 CPU 计，照样算进 shot。"""
    src = '''\
import threading, time
def make_decoder(H, L, priors, info):
    k = L.shape[0]
    stop = []
    def burn():
        while not stop:
            pass
    threading.Thread(target=burn, daemon=True).start()
    def decode(s):
        return [0] * k
    return decode
'''
    rep = ev(src, shots=N)
    for s in "ZX":
        st = rep.sectors[s]
        assert st["timeout"] + st["budget"] + st["dead"] > N // 2, rep.to_text()


def test_build_budget_enforced():
    """make_decoder 超过构建 CPU 预算：整个 sector 失败（用一个构建预算 1 s 的任务副本直接驱动执行器）。"""
    import dataclasses

    from evaluators import decoder_eval as de
    t = get_task(ST)
    t2 = dataclasses.replace(t, decoder=dict(t.decoder, speed=dict(t.decoder["speed"], build_cpu_s=1.0)))
    src = '''\
import time
def make_decoder(H, L, priors, info):
    t = time.process_time()
    while time.process_time() - t < 2.5:
        pass
    return lambda s: [0] * L.shape[0]
'''
    inst = dp.build_instance(t)
    d = dp.sample_batch(inst, dp.split_root(ST, t.hash(), "public"), 0, 20)
    runner = de._ProgramRunner(src, inst, t2, workers=1, use_os_sandbox=None)
    try:
        (st, co, cp, ms), = runner.run_round("Z", [(np.arange(20), d["Z"][0], d["Z"][1])])
        assert "build budget" in (runner.dead["Z"] or "")
        assert (st == de._ST["dead"]).all() and not co.any()
    finally:
        runner.close()


# ---------------------------------------------------------------------------
# 种子保密
# ---------------------------------------------------------------------------

def test_splits_differ_and_need_the_secret(temp_secret, monkeypatch):
    t = get_task(ST)
    roots = {s: dp.split_root(ST, t.hash(), s) for s in dp.SPLITS}
    assert len(set(roots.values())) == 3
    monkeypatch.setenv(dp.SECRET_ENV, str(temp_secret.parent / "missing.key"))
    with pytest.raises(dp.SecretError):
        dp.split_root(ST, t.hash(), "holdout")
    dp.split_root(ST, t.hash(), "public")      # 公开 split 不需要密钥


def test_secret_permissions_and_location_enforced(tmp_path, monkeypatch):
    p = tmp_path / "k"
    p.write_text("cd" * 32)
    os.chmod(p, 0o644)
    monkeypatch.setenv(dp.SECRET_ENV, str(p))
    with pytest.raises(dp.SecretError, match="chmod 600"):
        dp.load_secret()
    inside = dp.ROOT / "research" / "decoder_secret_test.key"
    monkeypatch.setenv(dp.SECRET_ENV, str(inside))
    with pytest.raises(dp.SecretError, match="outside the repo"):
        dp.load_secret()


def test_holdout_seed_not_leaked_in_reports(temp_secret):
    t = get_task(ST)
    root = dp.split_root(ST, t.hash(), "holdout")
    rep = ev(program_for("pymatching", {}), split="holdout", shots=None)
    blob = json.dumps(rep.to_dict(), default=str) + rep.to_text()
    assert str(root) not in blob and str(root)[:20] not in blob
    assert temp_secret.read_text().strip() not in blob
    for b in range(3):
        assert str(dp.batch_seed(root, b)) not in blob
    assert rep.seed_commitment and rep.seed_commitment != str(root)


def test_search_set_memorisation_does_not_transfer_to_holdout(temp_secret):
    """“对搜索集过拟合”的极端情形：程序内嵌搜索集每个 syndrome 的正确答案（假设搜索集完全泄露）。
    搜索集上满分，留出集上与瞎猜一样差。"""
    t = get_task(ST)
    inst = dp.build_instance(t)
    root = dp.split_root(ST, t.hash(), "search")
    bs = t.decoder["search"]["batch_size"]
    table = {"Z": {}, "X": {}}
    for b in range(t.decoder["search"]["shots"] // bs):
        d = dp.sample_batch(inst, root, b, bs)
        for s in "ZX":
            for i in range(bs):
                table[s][",".join(map(str, np.flatnonzero(d[s][0][i])))] = d[s][1][i].astype(int).tolist()
    src = f'''\
import numpy as np
TABLE = {json.dumps(table)}
def make_decoder(H, L, priors, info):
    T = TABLE[info["sector"]]
    k = L.shape[0]
    def decode(s):
        return T.get(",".join(map(str, np.flatnonzero(s).tolist())), [0] * k)
    return decode
'''
    srch = ev(src, split="search", shots=None)
    hold = ev(src, split="holdout", shots=None)
    assert srch.counts["fail_any"] <= 2
    assert hold.counts["fail_any"] > 3 * max(hold.reference["counts"]["fail_any"], 1)


# ---------------------------------------------------------------------------
# 成绩单
# ---------------------------------------------------------------------------

def _fake_record(rep, t, src):
    from evaluators.decoder_eval import decoder_record
    return decoder_record(rep, t, src)


def test_decoder_record_semantic_checks(temp_secret):
    from evaluators import leaderboard as lb
    t = get_task(ST)
    src = program_for("pymatching", {})
    rep = ev(src, split="holdout", shots=None)
    rec = json.loads(lb._canonical(_fake_record(rep, t, src)))
    probs = lb.entry_problems(rec)
    # 自检任务的计数达不到 1000，只能有这一条（以及无关的 purpose 问题之外没有别的问题）
    assert all("fewer than" in p for p in probs), probs
    forged = json.loads(json.dumps(rec))
    forged["rates"]["P_any"]["best"] /= 10
    forged["score"]["P_any"] = forged["rates"]["P_any"]
    assert any("not what the counts give" in p for p in lb.entry_problems(forged))
    f2 = json.loads(json.dumps(rec))
    f2["program"] += "\n# changed"
    assert any("program_hash" in p for p in lb.entry_problems(f2))
    f3 = json.loads(json.dumps(rec))
    f3["split"] = "search"
    assert any("held-out" in p for p in lb.entry_problems(f3))
    f4 = json.loads(json.dumps(rec))
    f4["seed_commitment"] = "0" * 64
    assert any("seed commitment" in p for p in lb.entry_problems(f4))
    f5 = json.loads(json.dumps(rec))
    f5["counts"]["fail_any"] = 0
    assert any("self-consistent" in p for p in lb.entry_problems(f5))


def test_search_split_never_written(tmp_path):
    path = tmp_path / "board.jsonl"
    rep = evaluate_decoder(ST, program_for("pymatching", {}), split="search", shots=N, leaderboard_path=path,
                           num_workers=1)
    assert rep.leaderboard_record is None and not path.exists()


def test_official_leaderboard_unchanged():
    from evaluators import leaderboard as lb
    before = lb.DEFAULT_PATH.read_bytes() if lb.DEFAULT_PATH.exists() else None
    ev(program_for("pymatching", {}), shots=N)
    after = lb.DEFAULT_PATH.read_bytes() if lb.DEFAULT_PATH.exists() else None
    assert before == after


# ---------------------------------------------------------------------------
# mp_rule：规则白名单与引擎
# ---------------------------------------------------------------------------

def test_mp_relay_rules_validate_and_match_schedule():
    from evaluators.decoder_mp import validate_rules
    t = get_task("bb72-mp-p3e-3")
    src = program_for("mp_relay", t.decoder["reference"]["params"])
    s = validate_rules(src)
    assert s["first_iters"] == 80 and s["leg_iters"] == 60 and s["stop_solutions"] == 5


BAD_RULES = {
    "attribute_escape": "x = np.abs.__class__",
    "global_sum": "x = np.sum(m)",
    "axis0": "x = np.sum(m, axis=0, keepdims=True)",
    "subscript": "x = m[0]",
    "import_os": "import os",
    "builtin_call": "x = open('/etc/passwd')",
    "loop": "for i in [1]:\n        x = m",
    "lambda": "x = (lambda: 1)()",
    "string": "x = 'a'",
    "transpose": "x = m.T",
    "np_not_whitelisted": "x = np.roll(m, 1)",
    "kwargs_extra": "x = np.sort(m, axis=1, kind='stable')",
    "rebind_np": "np = 1",
}


@pytest.mark.parametrize("name", list(BAD_RULES))
def test_mp_rule_whitelist_rejects(name):
    from evaluators.decoder_mp import RuleError, validate_rules
    t = get_task("bb72-mp-p3e-3")
    good = program_for("mp_relay", t.decoder["reference"]["params"])
    bad = BAD_RULES[name]
    if bad.startswith("import"):
        src = bad + "\n" + good
    else:
        src = good.replace('    a = np.abs(m)\n', "    " + bad + "\n    a = np.abs(m)\n")
    with pytest.raises(RuleError):
        validate_rules(src)


def test_mp_engine_enforces_iteration_cap():
    """规则永远不收敛（输出全 0 消息）、SCHEDULE 要 64 段 × 10000 次：引擎在 max_total_iters 次后停止。"""
    from evaluators.decoder_mp import wrap_rules
    t = get_task("bb72-mp-p3e-3")
    rules = '''\
import numpy as np
SCHEDULE = {"first_iters": 10000, "leg_iters": 10000, "max_legs": 64, "gamma0": 0.0, "gamma_low": 0.0,
            "gamma_high": 0.0, "stop_solutions": 64, "reset_messages": True}
def check_rule(m, sgn):
    return np.zeros_like(m)
def var_rule(prior, inc, gamma, prev):
    return np.full_like(prior, 1.0), np.zeros_like(inc)
'''
    full = wrap_rules(rules, t)
    calls = {"n": 0}
    ns = {"__name__": "x"}
    exec(compile(full, "<p>", "exec"), ns)
    inst = dp.build_instance(t)
    P = inst.sectors["Z"]
    dec = ns["make_decoder"](P.H, P.L, P.priors, inst.info("Z"))
    # 计数：包一层 var_rule
    orig = ns["_load_rules"]

    def counting():
        c, v = orig()

        def v2(*a):
            calls["n"] += 1
            return v(*a)
        return c, v2
    ns["_load_rules"] = counting
    dec = ns["make_decoder"](P.H, P.L, P.priors, inst.info("Z"))
    syn = np.zeros(P.num_det, dtype=np.uint8)
    syn[[3, 40]] = 1
    dec(syn)
    assert calls["n"] == t.decoder["mp"]["max_total_iters"]


def test_mp_engine_relay_close_to_official_relay():
    """引擎跑的 Relay 规则与官方包在 BB72 上的失败数同量级（不要求逐位相同：γ 的抽样与段间细节不同）。"""
    from evaluators.decoder_mp import wrap_rules
    t = get_task("bb72-mp-p3e-3")
    inst = dp.build_instance(t)
    d = dp.sample_batch(inst, dp.split_root("bb72-mp-test", "x", "public"), 0, 300)
    eng = direct(wrap_rules(program_for("mp_relay", t.decoder["reference"]["params"]), t), d["Z"], inst, "Z")
    off = direct(program_for("relay_bp", RELAY_BP_PAPER), d["Z"], inst, "Z")
    assert abs(int(eng.sum()) - int(off.sum())) <= max(6, off.sum())


def test_mp_rules_end_to_end_through_evaluator():
    """mp_rule 任务的完整路径：规则 → 白名单 → 引擎 → 沙箱 → 计时；与参考相同的规则得到与参考相同的计数。"""
    t = get_task("bb72-mp-p3e-3")
    rules = program_for("mp_relay", t.decoder["reference"]["params"])
    rep = evaluate_decoder("bb72-mp-p3e-3", rules, split="search", shots=500, submit=False, num_workers=1)
    assert rep.status == "searched", rep.to_text()
    assert rep.counts == rep.reference["counts"]


def test_mp_task_rejects_full_programs_as_rules():
    rep = evaluate_decoder("bb72-mp-p3e-3", program_for("relay_bp", RELAY_BP_PAPER), split="search", shots=500,
                           submit=False, num_workers=1)
    assert rep.status == "rejected" and "rules rejected" in rep.to_text()


# ---------------------------------------------------------------------------
# 近最优参考（CP-SAT MLE）
# ---------------------------------------------------------------------------

def test_near_optimal_gap_on_surface_code():
    from evaluators.decoder_eval import near_optimal_gap
    g = near_optimal_gap(ST, shots=60, first_batch=5)
    for s in "ZX":
        sec = g["sectors"][s]
        assert sec["proved_optimal"] == 60
        refs = sec["references"]
        assert set(refs) == {"relay_bp", "pymatching"}
        # MLE 不会比参考差很多（小样本，允许 2 个的统计波动）
        assert sec["near_optimal_fail"] <= min(r["fail"] for r in refs.values()) + 2


def test_cpsat_mle_finds_minimum_weight_solution_on_tiny_problem():
    import scipy.sparse as sp

    from evaluators.decoder_mle import CpSatMLE
    from evaluators.decoder_problem import SectorProblem
    # 重复码：3 个机制，2 个 detector；syndrome [1,1] 的最可能解是中间一个
    H = sp.csc_matrix(np.array([[1, 1, 0], [0, 1, 1]], dtype=np.uint8))
    L = sp.csr_matrix(np.array([[0, 1, 0]], dtype=np.uint8))
    P = SectorProblem("Z", H, L, np.array([0.01, 0.01, 0.01]), [[0, 0, 1], [1, 0, 1]], 0)
    r = CpSatMLE(time_limit_s=5).decode(P, np.array([1, 1], dtype=np.uint8))
    assert r.optimal and r.observables.tolist() == [1]
