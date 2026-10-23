"""E-035 probe (no LER): validation of the neutral-atom post-processor and per-round fault mass / round time.
  1. reduction test: NAParams with p_1q = p_tr = p_ro = 0, T2 = inf, p_cz = p_prep = p_meas = p must give exactly the
     DEM of e026b lam0 (SD6 without idle) for every circuit and basis.
  2. per-round DEM fault mass (sum of DEM error probabilities, bulk difference R vs R-1) and its split by channel.
  3. bulk time per round under each parameter set (layer durations of the model).
  4. unpaired-atom exposure counts (atoms in the entangling zone not in a CZ during a Rydberg pulse), per round.
"""
from __future__ import annotations
import json
import math
from dataclasses import replace

import stim

from search.experiments.e026b.common import noisy_from
from search.experiments.e035.common import CIRCS, OUT, noiseless, roles, rounds_of, PERIOD
from search.experiments.e035.na_noise import NAParams, SETS, apply, layer_info, layer_time_us


def dem_key(c: stim.Circuit):
    d = {}
    for inst in c.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True).flattened():
        if inst.type != "error":
            continue
        k = tuple(sorted(str(t) for t in inst.targets_copy()))
        p = inst.args_copy()[0]
        d[k] = 1 - ((1 - d.get(k, 0)) * (1 - p)) if k in d else p
    return d


def dem_mass(c):
    m = 0.0
    for inst in c.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True).flattened():
        if inst.type == "error":
            m += inst.args_copy()[0]
    return m


def reduction_test(p=3e-3):
    P0 = NAParams("red", p_cz=p, p_1q=0, p_prep=p, p_meas=p, p_tr=0, T2_s=math.inf, t_step_us=200,
                  t_meas_us=1000, p_ro=0)
    res = {}
    for name in CIRCS:
        for b in "ZX":
            nl = noiseless(name, b, 3)
            a = dem_key(apply(nl, P0, roles(name)))
            r = dem_key(noisy_from(nl, "lam0", p))
            same = a.keys() == r.keys() and max(abs(a[k] - r[k]) / r[k] for k in r) < 1e-12
            res[f"{name}_{b}"] = bool(same)
            assert same, (name, b)
    return res


def per_round(name, P, basis="Z"):
    R = rounds_of(name)
    m2 = dem_mass(apply(noiseless(name, basis, R), P, roles(name)))
    m1 = dem_mass(apply(noiseless(name, basis, R - 1), P, roles(name)))
    return m2 - m1


def channel_split(name, P, basis="Z"):
    """per-round mass with only one channel switched on."""
    z = dict(p_cz=0, p_1q=0, p_prep=0, p_meas=0, p_tr=0, p_ro=0, T2_s=math.inf)
    out = {}
    for ch, kw in (("cz", dict(p_cz=P.p_cz)), ("1q", dict(p_1q=P.p_1q)), ("prep", dict(p_prep=P.p_prep)),
                   ("meas", dict(p_meas=P.p_meas)), ("transfer", dict(p_tr=P.p_tr)),
                   ("readout_scatter", dict(p_ro=P.p_ro)), ("time", dict(T2_s=P.T2_s))):
        Q = replace(P, **{**z, **kw})
        out[ch] = per_round(name, Q, basis)
    return out


def round_time(name, P):
    R = rounds_of(name)
    nl = noiseless(name, "Z", R)
    nl1 = noiseless(name, "Z", R - 1)
    def tot(c):
        _, _, info = layer_info(c, roles(name))
        a = b = 0.0
        for inf in info:
            x, y = layer_time_us(P, inf)
            a += x; b += y
        return a, b
    a2, b2 = tot(nl); a1, b1 = tot(nl1)
    return dict(move_gate_us=a2 - a1, readout_wait_us=b2 - b1, total_us=a2 - a1 + b2 - b1)


def unpaired(name):
    """per round: (pulses_seq, pulses_par, unpaired atom-pulse exposures seq/par) with all data + all ancillas in the
    entangling zone except during readout (upper-bound picture)."""
    R = rounds_of(name)
    r = roles(name)
    res = {}
    for RR in (R, R - 1):
        _, allq, info = layer_info(noiseless(name, "Z", RR), r)
        nq = len(allq)
        seq = par = ps = pp = 0
        for inf in info:
            if inf["ncx"] == 0:
                continue
            # seq: each group is one pulse with ncx/ngroups pairs (TI: equal), unpaired = nq - 2*pairs
            g = inf["ngroups"]
            ps += g; seq += g * nq - 2 * inf["ncx"]
            pp += 1; par += nq - 2 * inf["ncx"]
        res[RR] = (ps, pp, seq, par)
    a, b = res[R], res[R - 1]
    return dict(pulses_seq=a[0] - b[0], pulses_par=a[1] - b[1], unpaired_seq=a[2] - b[2], unpaired_par=a[3] - b[3])


def main():
    out = {"reduction_test_lam0_p3e-3": reduction_test()}
    print("reduction test", out["reduction_test_lam0_p3e-3"], flush=True)
    for name in CIRCS:
        d = {}
        for sname, P in SETS.items():
            d[sname] = dict(round_time=round_time(name, P), mass_Z=per_round(name, P, "Z"),
                            mass_X=per_round(name, P, "X"))
        d["cur_split_Z"] = channel_split(name, SETS["cur"], "Z")
        d["cur_split_X"] = channel_split(name, SETS["cur"], "X")
        d["proj_split_X"] = channel_split(name, SETS["proj"], "X")
        d["unpaired"] = unpaired(name)
        out[name] = d
        print(name, json.dumps(d, indent=None), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "probe.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
