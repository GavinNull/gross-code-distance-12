"""E-036: find a bulk weight-w witness (all faults in rounds 2..R-1, R = 5) for a non-wrapping circuit -> d_circ <= w
for every R >= 5 by periodicity (R < 5 computed directly)."""
import sys, json
import stim
from search.experiments.e036.common import OUT, dem_mechs, sd6
from search.experiments.e036.dcirc import get_spec

variant, name, w = sys.argv[1], sys.argv[2], int(sys.argv[3])
R = 5
spec = get_spec(variant, name)
P = spec.period
out = {}
for basis in ("Z", "X"):
    c = sd6(spec, variant, basis, R)
    mechs, nd = dem_mechs(c)
    # tick range of each mechanism (min over representative errors)
    dem = c.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    ex = c.explain_detector_error_model_errors(dem_filter=None, reduce_to_one_representative_error=False)
    ticks = {}
    for e in ex:
        d = 0; o = 0
        for t in e.dem_error_terms:
            if t.dem_target.is_relative_detector_id(): d ^= 1 << t.dem_target.val
            else: o ^= 1 << t.dem_target.val
        ticks[(d, o)] = [loc.tick_offset for loc in e.circuit_error_locations]
    first_round_end = P  # template: round 0 occupies layers 0..P-1 (first CNOT >= 1, meas at P-1 or so)
    lo, hi = P, P * (R - 1)
    bulk = [i for i, m in enumerate(mechs) if any(lo <= t < hi for t in ticks.get(m, []))]
    sub = [mechs[i] for i in bulk]
    # exhaustive weight-w witness in the bulk subset
    from search.experiments.e036.common import min_weight
    ww, wit = min_weight(sub, w)
    rec = {"basis": basis, "R": R, "bulk_mechs": len(sub), "all_mechs": len(mechs), "bulk_min_w": ww}
    if wit:
        rec["witness_ticks"] = [sorted(t for t in ticks[sub[i]] if lo <= t < hi)[:3] for i in wit]
    out[basis] = rec
    print(json.dumps(rec))
with open(OUT / "bulkwit.jsonl", "a") as f:
    f.write(json.dumps({"variant": variant, "circuit": name, **out}) + "\n")
