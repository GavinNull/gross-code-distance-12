"""E-035 neutral-atom circuit-level noise model, applied by post-processing the NOISELESS evaluator template circuit
(evaluators.candidate.memory_circuit, read-only use; evaluators/ is not modified).  experimenter.

Physical picture (all assumptions are listed in experiments/E-035-neutral-atom-ler.yaml, every number has an arXiv id):
  * data atoms sit in static traps in the entangling zone; X-ancilla and Z-ancilla sub-arrays are held in AOD tweezers
    and translated rigidly next to their data partners (2506.20661 surface-code layout; qSIEVE 2311.16980 and
    Xu et al. 2308.08648 for BB/LP codes), then one global Rydberg CZ pulse.
  * one "step" = one rigid translation of one ancilla sub-array that realises one BB term (one (check type, term)
    group) + CZ pulse + local single-qubit gates; duration t_step.
      timing "seq": the steps of a template layer are executed one after another (qSIEVE routes X and Z checks
                    separately): layer time = (#distinct (type, term) groups in the layer) * t_step.
      timing "par": all groups of a layer move simultaneously: layer time = t_step if the layer has any CX.
  * CX = H(target) CZ H(target): DEPOLARIZE1(p_1q) on the target before, DEPOLARIZE2(p_cz) after, DEPOLARIZE1(p_1q)
    on the target after (exact rewrite of the H.CZ.H noise since depolarizing channels are Clifford invariant).
  * state preparation: X_ERROR (R) / Z_ERROR (RX) with p_prep; ancillas additionally DEPOLARIZE1(p_tr) after
    preparation (pick-up transfer into the AOD).
  * measurement: ancillas DEPOLARIZE1(p_tr) (transfer out to the readout zone) then flip p_meas; final data readout
    flip p_meas only.
  * time noise: every atom (data and ancillas, gated or not, since moves dominate the time) dephases during the layer:
    Z_ERROR(p_z(tau)) with p_z(tau) = (1 - exp(-tau/T2))/2, applied once per layer before its operations.
    (idle_kind "dep": DEPOLARIZE1 with the same total probability, sensitivity only.)
  * readout window: if a template layer contains mid-circuit measurements, the other atoms wait t_meas (critical path)
    -> extra Z_ERROR(p_z(t_meas)), and receive imaging scatter DEPOLARIZE1(p_ro) (per readout event, whether or not
    the wait is on the critical path).  The final data readout layer gets no time noise (nothing follows it).
  * "scale": uniform multiplier of every error probability (including the time-noise probabilities).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace, asdict

import stim

from evaluators.noise import split_layers

ANN = {"DETECTOR", "OBSERVABLE_INCLUDE", "QUBIT_COORDS", "SHIFT_COORDS", "MPAD"}


@dataclass(frozen=True)
class NAParams:
    name: str
    p_cz: float
    p_1q: float
    p_prep: float
    p_meas: float
    p_tr: float
    T2_s: float
    t_step_us: float
    t_meas_us: float      # readout wait on the critical path per mid-circuit measurement layer
    p_ro: float           # imaging scatter on non-measured atoms per mid-circuit readout layer
    timing: str = "seq"   # "seq" | "par"
    idle_kind: str = "Z"  # "Z" | "dep"
    p_unpaired: float = 0.0  # error on atoms in the entangling zone not paired in a CZ pulse (fault-mass probe only)
    scale: float = 1.0

    def scaled(self, s: float) -> "NAParams":
        return replace(self, scale=s, name=f"{self.name}x{s:g}")

    def pz(self, tau_us: float) -> float:
        if tau_us <= 0 or math.isinf(self.T2_s):
            return 0.0
        return 0.5 * (1.0 - math.exp(-tau_us * 1e-6 / self.T2_s))

    def as_dict(self):
        return asdict(self)


# ---- parameter sets (sources: experiments/E-035-neutral-atom-ler.yaml) ----
CUR = NAParams("cur", p_cz=5.0e-3, p_1q=9.0e-4, p_prep=6.8e-3, p_meas=5.8e-3, p_tr=1.0e-3,
               T2_s=1.0, t_step_us=200.0, t_meas_us=1000.0, p_ro=6.8e-4)
CUR_CZ = replace(CUR, name="cur_cz", p_cz=6.5e-3)
CUR_SLOW = replace(CUR, name="cur_slow", t_step_us=470.0, t_meas_us=2570.0)
CUR_PAR = replace(CUR, name="cur_par", timing="par")
PROJ = NAParams("proj", p_cz=3.0e-3, p_1q=3.0e-4, p_prep=4.0e-3, p_meas=2.0e-3, p_tr=1.0e-3,
                T2_s=10.0, t_step_us=200.0, t_meas_us=0.0, p_ro=3.4e-4)
PROJ_T2PAR = replace(PROJ, name="proj_t2par", T2_s=1.0, timing="par")
# stress variant (ASSUMPTION, no literature value): unpaired atoms in the Rydberg pulse get DEPOLARIZE1(p_cz / 2)
CUR_PAR_UNP = replace(CUR, name="cur_par_unp", timing="par", p_unpaired=2.5e-3)
CUR_UNP = replace(CUR, name="cur_unp", p_unpaired=2.5e-3)
SETS = {s.name: s for s in (CUR, CUR_CZ, CUR_SLOW, CUR_PAR, PROJ, PROJ_T2PAR, CUR_PAR_UNP, CUR_UNP)}


def get_params(tag: str) -> NAParams:
    """'cur', 'cur_cz', ..., optionally with 'x<scale>' suffix, e.g. 'curx0.5'."""
    if "x" in tag and tag.split("x")[-1].replace(".", "").isdigit():
        base, s = tag.rsplit("x", 1)
        return SETS[base].scaled(float(s))
    return SETS[tag]


def _q(inst):
    return [t.value for t in inst.targets_copy() if t.is_qubit_target]


class Roles:
    """qubit roles of the evaluator template layout (data 0..n-1, X ancillas, Z ancillas) and BB grid geometry."""

    def __init__(self, n: int, mx: int, mz: int, l: int, m: int):
        self.n, self.mx, self.mz, self.l, self.m = n, mx, mz, l, m
        self.nh = n // 2

    def is_anc(self, q):
        return q >= self.n

    def group(self, a: int, b: int):
        """(type, term) group of a CX pair: displacement between the check's grid position and the data qubit."""
        if a >= self.n:          # X ancilla -> data
            typ, i, d = "X", a - self.n, b
        else:                    # data -> Z ancilla
            typ, i, d = "Z", b - self.n - self.mx, a
        blk, j = divmod(d, self.nh)
        ia, ib = divmod(i, self.m)
        ja, jb = divmod(j, self.m)
        return (typ, blk, (ja - ia) % self.l, (jb - ib) % self.m)


def layer_info(nl: stim.Circuit, roles: Roles | None):
    """per template layer: list of ops, #groups, has mid-circuit measurement, is final readout."""
    layers = split_layers(nl)
    allq = set()
    for L in layers:
        for i in L:
            if i.name not in ANN:
                allq.update(_q(i))
    info = []
    for li, L in enumerate(layers):
        groups, mid_meas, final = set(), False, False
        ncx = 0
        for i in L:
            if i.name == "CX":
                qs = _q(i)
                for a, b in zip(qs[::2], qs[1::2]):
                    ncx += 1
                    groups.add(roles.group(a, b) if roles is not None else ("L", li))
            elif i.name in ("M", "MX", "MR", "MRX"):
                qs = _q(i)
                if roles is None:
                    if i.name in ("M", "MX"):   # surface-code sanity circuit: plain M only in the final readout
                        final = True
                    else:
                        mid_meas = True
                elif all(not roles.is_anc(q) for q in qs) and len(qs) == roles.n:
                    final = True
                else:
                    mid_meas = True
        info.append(dict(ngroups=len(groups), ncx=ncx, mid_meas=mid_meas, final=final))
    return layers, sorted(allq), info


def layer_time_us(P: NAParams, inf) -> tuple[float, float]:
    """(move/gate time, readout wait) of a template layer in microseconds."""
    if inf["final"]:
        return 0.0, 0.0
    if P.timing == "seq":
        tm = inf["ngroups"] * P.t_step_us
    else:
        tm = P.t_step_us if inf["ngroups"] > 0 else 0.0
    tw = P.t_meas_us if inf["mid_meas"] else 0.0
    return tm, tw


def apply(nl: stim.Circuit, P: NAParams, roles: Roles | None, *, anc_set=None) -> stim.Circuit:
    """noiseless template circuit -> neutral-atom noisy circuit.  anc_set: qubits that are ancillas (for transfer
    errors); defaults to roles.is_anc."""
    s = P.scale
    isanc = (lambda q: q in anc_set) if anc_set is not None else (lambda q: roles.is_anc(q))
    layers, allq, info = layer_info(nl, roles)
    out = stim.Circuit()
    for li, (L, inf) in enumerate(zip(layers, info)):
        if li > 0:
            out.append("TICK")
        measured = set()
        for i in L:
            if i.name in ("M", "MX", "MR", "MRX"):
                measured.update(_q(i))
        tm, tw = layer_time_us(P, inf)
        pz = P.pz(tm + tw)
        if pz > 0:
            pz *= s
            out.append("Z_ERROR" if P.idle_kind == "Z" else "DEPOLARIZE1", allq,
                       pz if P.idle_kind == "Z" else 1.5 * pz)
        if inf["mid_meas"] and P.p_ro > 0:
            others = [q for q in allq if q not in measured]
            out.append("DEPOLARIZE1", others, P.p_ro * s)
        if P.p_unpaired > 0 and inf["ncx"] > 0:
            # atoms in the entangling zone that are not paired in a Rydberg pulse (ASSUMPTION, no literature value):
            # eligible = every qubit not prepared or measured in this layer; "par": one pulse per layer,
            # "seq": one pulse per (type, term) group, unpaired = eligible minus that group's pairs.
            busy = set()
            pulses = {}
            for i in L:
                if i.name in ("R", "RX", "M", "MX", "MR", "MRX"):
                    busy.update(_q(i))
                elif i.name == "CX":
                    qs = _q(i)
                    for a, b in zip(qs[::2], qs[1::2]):
                        g = roles.group(a, b) if (P.timing == "seq" and roles is not None) else "all"
                        pulses.setdefault(g, set()).update((a, b))
            elig = [q for q in allq if q not in busy]
            for g, paired in sorted(pulses.items(), key=lambda kv: str(kv[0])):
                un = [q for q in elig if q not in paired]
                if un:
                    out.append("DEPOLARIZE1", un, P.p_unpaired * s)
        for i in L:
            n = i.name
            if n in ANN:
                out.append(i)
                continue
            qs = _q(i)
            if n in ("R", "RX"):
                out.append(i)
                out.append("X_ERROR" if n == "R" else "Z_ERROR", qs, P.p_prep * s)
                anc = [q for q in qs if isanc(q)]
                if anc and P.p_tr > 0:
                    out.append("DEPOLARIZE1", anc, P.p_tr * s)
            elif n == "CX":
                tg = qs[1::2]
                if P.p_1q > 0:
                    out.append("DEPOLARIZE1", tg, P.p_1q * s)
                out.append(i)
                out.append("DEPOLARIZE2", qs, P.p_cz * s)
                if P.p_1q > 0:
                    out.append("DEPOLARIZE1", tg, P.p_1q * s)
            elif n == "H":  # only in the surface-code sanity circuit (stim generated)
                out.append(i)
                out.append("DEPOLARIZE1", qs, P.p_1q * s)
            elif n in ("MR", "MRX"):  # only in the surface-code sanity circuit: measure, then reset
                anc = [q for q in qs if isanc(q)]
                if anc and P.p_tr > 0:
                    out.append("DEPOLARIZE1", anc, P.p_tr * s)
                out.append("X_ERROR" if n == "MR" else "Z_ERROR", qs, P.p_meas * s)
                out.append(i)
                out.append("X_ERROR" if n == "MR" else "Z_ERROR", qs, P.p_prep * s)
                if anc and P.p_tr > 0:
                    out.append("DEPOLARIZE1", anc, P.p_tr * s)
            elif n in ("M", "MX"):
                anc = [q for q in qs if isanc(q)]
                if anc and P.p_tr > 0:
                    out.append("DEPOLARIZE1", anc, P.p_tr * s)
                out.append("X_ERROR" if n == "M" else "Z_ERROR", qs, P.p_meas * s)
                out.append(i)
            else:
                raise NotImplementedError(n)
    return out


def round_time_us(nl: stim.Circuit, P: NAParams, roles: Roles, period: int, rounds: int):
    """bulk time per round: (total time over layers excluding the final readout) / rounds, plus split."""
    _, _, info = layer_info(nl, roles)
    tm = tw = 0.0
    for inf in info:
        a, b = layer_time_us(P, inf)
        tm += a
        tw += b
    return tm, tw
