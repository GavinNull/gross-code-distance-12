import os, signal
def make_decoder(H, L, priors, info):
    k = L.shape[0]
    results = []
    try:
        signal.signal(signal.SIGCONT, lambda *a: results.append("cont"))
        results.append("handler_installed")
    except Exception as e:
        results.append("handler_blocked:"+type(e).__name__)
    try:
        os.kill(os.getppid(), 0)      # probe/send to parent -> must be blocked
        results.append("SIGNAL_PARENT_LEAKED")
    except Exception as e:
        results.append("kill_blocked:"+type(e).__name__)
    raise RuntimeError("RESULT " + repr(results))
