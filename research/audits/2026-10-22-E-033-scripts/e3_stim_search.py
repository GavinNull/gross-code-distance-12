"""Auditor E-033: stim heuristic search_for_undetectable_logical_errors on MY circuits (upper-bound check only)."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mylib
ROOT = "/Users/ephemeral/Desktop/qec-ai-search/"
SPEC = {"u11": "search/experiments/e032/u11_spec.json", "ibm": "search/experiments/e033/ibm_gross_spec.json"}
for circ, b, R in [("ibm", "Z", 1), ("ibm", "X", 1), ("ibm", "Z", 3), ("ibm", "X", 3)]:
    c = mylib.memory_circuit(mylib.load_spec(ROOT + SPEC[circ]), b, R, p=1e-3, lam=1.0)
    t0 = time.time()
    e = c.search_for_undetectable_logical_errors(dont_explore_detection_event_sets_with_size_above=4,
        dont_explore_edges_with_degree_above=9999, dont_explore_edges_increasing_symptom_degree=False, canonicalize_circuit_errors=True)
    print(circ, b, R, "stim heuristic min found:", len(e), round(time.time() - t0, 1), "s", flush=True)
