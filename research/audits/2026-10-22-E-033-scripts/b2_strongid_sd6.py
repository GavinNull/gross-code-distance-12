"""Auditor E-033 claim 3: for the lam1 rows merged with E-026 ('sd6' metadata), rebuild the E-033 lam1 circuit,
reproduce the E-033 strong_id (to learn sinter's DEM options), then recompute it with E-026's metadata
{"noise":"sd6"} and compare with the E-026 csv strong_id.  Also checks the u11 lam0 circuit through the same path."""
import sys, json
sys.path[:0] = ["/Users/ephemeral/Desktop/qec-ai-search", "/Users/ephemeral/Desktop/qec-ai-search/tests"]
import sinter
from search.experiments.e033.common import noisy

def sid(c, dec, meta, **kw):
    t = sinter.Task(circuit=c, decoder=dec, json_metadata=meta,
                    detector_error_model=c.detector_error_model(**kw))
    return t.strong_id()[:12]

OPTS = [dict(decompose_errors=False, allow_gauge_detectors=False, approximate_disjoint_errors=True),
        dict(decompose_errors=True, allow_gauge_detectors=False, approximate_disjoint_errors=True),
        dict(decompose_errors=False), dict(decompose_errors=False, approximate_disjoint_errors=True)]
want = {("X", 0.002, "bposd"): ("e7b7cdc7e9cc", "d19fb6966d3e"), ("Z", 0.002, "bposd"): ("9c2cd29d710d", "faf9b5dba3aa"),
        ("X", 0.002, "relay5"): ("a4b507caf958", "d3d6db0a39b1"), ("Z", 0.002, "relay5"): ("02d78dabc100", "c166c4c8ce3b"),
        ("X", 0.004, "bposd"): ("aaa0106daed2", "33f34eca5c54"), ("Z", 0.004, "bposd"): ("80f5fb1eebe2", "5135a991d3e1")}
for (b, p, dec), (new, old) in want.items():
    c = noisy("ibm", b, 12, p, "lam1")
    for o in OPTS:
        try:
            s_new = sid(c, dec, dict(circ="ibm", basis=b, p=p, R=12, noise="lam1"), **o)
        except Exception as e:
            continue
        if s_new == new:
            s_old = sid(c, dec, dict(circ="ibm", basis=b, p=p, R=12, noise="sd6"), **o)
            print(b, p, dec, "E033 id reproduced with", o, "| sd6-meta id", s_old, "E-026 csv", old, "MATCH" if s_old == old else "MISMATCH")
            break
    else:
        print(b, p, dec, "could not reproduce E033 id")
