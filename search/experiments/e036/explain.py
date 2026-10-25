"""E-036: print the circuit faults behind a minimal witness (stim explain)."""
import sys
import stim
from search.experiments.e036.common import dem_mechs, min_weight, sd6
from search.experiments.e036.dcirc import get_spec

variant, name, basis, R, w = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
c = sd6(get_spec(variant, name), variant, basis, R)
mechs, _ = dem_mechs(c)
ww, wit = min_weight(mechs, w)
print("min weight", ww)
dem = c.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
for i in wit:
    d, o = mechs[i]
    targets = [stim.target_relative_detector_id(k) for k in range(d.bit_length()) if d >> k & 1]
    targets += [stim.target_logical_observable_id(k) for k in range(o.bit_length()) if o >> k & 1]
    sub = stim.DetectorErrorModel()
    sub.append("error", 0.001, targets)
    ex = c.explain_detector_error_model_errors(dem_filter=sub, reduce_to_one_representative_error=True)
    for e in ex:
        loc = e.circuit_error_locations[0]
        print(f"dets={[k for k in range(d.bit_length()) if d>>k&1]} obs={bin(o)}  tick={loc.tick_offset} "
              f"gate={loc.instruction_targets.gate} flipped={[ (t.gate_target.value, t.gate_target.pauli_type) for t in loc.flipped_pauli_product]}")
