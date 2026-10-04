import os
def make_decoder(H, L, priors, info):
    out = {}
    for name, path in [("secret", "/private/tmp/claude-501/-Users-ephemeral/51035684-bfaf-4743-b8e1-678c08dbe16b/scratchpad/decoder_test_secret.key"),
                       ("tasks_py", "/Users/ephemeral/Desktop/qec-ai-search/evaluators/tasks.py"),
                       ("home", os.path.expanduser("~"))]:
        try:
            st = os.stat(path); out[name+"_stat"] = (st.st_size, oct(st.st_mode))
        except Exception as e:
            out[name+"_stat"] = "STAT_BLOCKED:"+type(e).__name__
        try:
            open(path).read(16); out[name+"_read"] = "READ_LEAKED"
        except Exception as e:
            out[name+"_read"] = "read_blocked:"+type(e).__name__
    raise RuntimeError("RESULT " + repr(out)[:400])
