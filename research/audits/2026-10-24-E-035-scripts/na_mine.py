"""Auditor E-035: own neutral-atom noise model, written from the model STATED in experiments/E-035-neutral-atom-ler.yaml
(noise_model.channels / timing), applied while building the circuit from the auditors' own encoder (E-030 / E-033
auditor mylib: own code, own logicals, own unroll incl. wrapping checks).  No import of search/ or evaluators/.

Per template layer t (mylib.unroll layers; layer 0 also holds the data reset; final data readout is its own layer):
  time   tau = move + wait;  move = (#distinct (type, BB monomial) groups among the layer's CX) * t_step  [seq]
                                    or t_step if the layer has any CX                                   [par]
         wait = t_meas if the layer has an ancilla measurement; final readout layer: tau = 0, no scatter.
  noise  (1) Z_ERROR(s * (1 - exp(-tau/T2))/2) on every qubit;  (2) mid-circuit readout layer: DEPOLARIZE1(s p_ro)
         on every qubit not measured in the layer;  (3) unpaired (stress): DEPOLARIZE1(s p_unp) on every qubit that is
         not reset/measured in the layer and not in a CX of the pulse (par: 1 pulse per layer; seq: 1 pulse per group);
         (4) resets: flip s p_prep after, ancillas + DEPOLARIZE1(s p_tr);  (5) CX: DEPOLARIZE1(s p_1q) on the target
         before and after, DEPOLARIZE2(s p_cz) after;  (6) measurement: ancillas DEPOLARIZE1(s p_tr), flip s p_meas,
         then measure; final data readout: flip s p_meas only.
Parameter values are typed in here from the yaml (not imported)."""
from __future__ import annotations
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import stim

ROOT = Path("/Users/ephemeral/Desktop/qec-ai-search")
AUD = ROOT / "research/audits"


def _load(name, path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


LIB = {"bb90": _load("mylib90", AUD / "2026-10-22-E-030-scripts/mylib.py"),
       "gross": _load("mylib144", AUD / "2026-10-22-E-033-scripts/mylib.py")}
SPECS = {"c11": ("bb90", "search/experiments/e030/c11_spec.json"),
         "ibm90": ("bb90", "search/experiments/e030/ibm90_spec.json"),
         "u11": ("gross", "search/experiments/e032/u11_spec.json"),
         "ibm": ("gross", "search/experiments/e033/ibm_gross_spec.json"),
         "fig12": ("gross", "search/experiments/e033/fig12_gross_spec.json")}
RNDS = {"gross": 12, "bb90": 10}

BASE = dict(p_cz=5.0e-3, p_1q=9.0e-4, p_prep=6.8e-3, p_meas=5.8e-3, p_tr=1.0e-3, T2=1.0, t_step=200.0,
            t_meas=1000.0, p_ro=6.8e-4, timing="seq", p_unp=0.0, s=1.0)
PROJ = dict(BASE, p_cz=3.0e-3, p_1q=3.0e-4, p_prep=4.0e-3, p_meas=2.0e-3, p_tr=1.0e-3, T2=10.0, t_step=200.0,
            t_meas=0.0, p_ro=3.4e-4)
MODELS = {"cur": BASE, "curx0.5": dict(BASE, s=0.5), "cur_cz": dict(BASE, p_cz=6.5e-3),
          "cur_slow": dict(BASE, t_step=470.0, t_meas=2570.0), "cur_par": dict(BASE, timing="par"),
          "proj": PROJ, "proj_t2par": dict(PROJ, T2=1.0, timing="par"),
          "cur_par_unp": dict(BASE, timing="par", p_unp=2.5e-3), "cur_unp": dict(BASE, p_unp=2.5e-3)}


def spec(name):
    fam, p = SPECS[name]
    return fam, json.load(open(ROOT / p))


def group_of(lib, typ, anc_index, data_col):
    """BB monomial realised by the CX: check at grid (ia, ib) touching data column in block blk at (ja, jb)."""
    n2 = lib.N2
    blk, j = divmod(data_col, n2)
    ia, ib = divmod(anc_index, lib.M_)
    ja, jb = divmod(j, lib.M_)
    return (typ, blk, (ja - ia) % lib.L_, (jb - ib) % lib.M_)


def layer_meta(lib, layers):
    out = []
    for t, L in enumerate(layers):
        groups = {}
        for a, b in L["CX"]:
            if a >= lib.QX0 and a < lib.QZ0:   # X ancilla -> data
                g = group_of(lib, "X", a - lib.QX0, b)
            else:                               # data -> Z ancilla
                g = group_of(lib, "Z", b - lib.QZ0, a)
            groups.setdefault(g, []).append((a, b))
        anc_meas = bool(L["M"] or L["MX"])
        out.append(dict(groups=groups, anc_meas=anc_meas))
    return out


def times(P, meta):
    res = []
    for m in meta:
        if P["timing"] == "seq":
            mv = len(m["groups"]) * P["t_step"]
        else:
            mv = P["t_step"] if m["groups"] else 0.0
        res.append((mv, P["t_meas"] if m["anc_meas"] else 0.0))
    return res


def build(name, basis, R, model, P=None):
    fam, d = spec(name)
    lib = LIB[fam]
    P = P or MODELS[model]
    s = P["s"]
    HX, HZ, LX, LZ = lib.code_with_logicals()
    H, Lg = (HZ, LZ) if basis == "Z" else (HX, LX)
    layers, st, info, meas_at = lib.unroll(d, R)
    meta = layer_meta(lib, layers)
    tl = times(P, meta)
    N = lib.N
    allq = list(range(N + 2 * lib.N2))
    isanc = lambda q: q >= N
    c = stim.Circuit()
    rec, nm = {}, 0
    stats = dict(unp=0, pulses=0, unp_probe=0)
    for t, L in enumerate(layers):
        if t > 0:
            c.append("TICK")
        mv, wt = tl[t]
        tau = mv + wt
        if tau > 0 and math.isfinite(P["T2"]):
            c.append("Z_ERROR", allq, s * 0.5 * (1 - math.exp(-tau * 1e-6 / P["T2"])))
        measured = set(L["M"]) | set(L["MX"])
        if meta[t]["anc_meas"] and P["p_ro"] > 0:
            c.append("DEPOLARIZE1", [q for q in allq if q not in measured], s * P["p_ro"])
        resets = [("R" if basis == "Z" else "RX", list(range(N)))] if t == 0 else []
        resets += [(g, sorted(L[g])) for g in ("RX", "R") if L[g]]
        busy = set(measured)
        for g, qs in resets:
            busy.update(qs)
        if meta[t]["groups"]:
            pulses = list(meta[t]["groups"].values()) if P["timing"] == "seq" else \
                [[pr for v in meta[t]["groups"].values() for pr in v]]
            for prs in pulses:
                paired = {a for pr in prs for a in pr}
                un = [q for q in allq if q not in busy and q not in paired]
                stats["pulses"] += 1; stats["unp"] += len(un); stats["unp_probe"] += len(allq) - len(paired)
                if P["p_unp"] > 0 and un:
                    c.append("DEPOLARIZE1", un, s * P["p_unp"])
        for g, qs in resets:
            c.append(g, qs)
            c.append("X_ERROR" if g == "R" else "Z_ERROR", qs, s * P["p_prep"])
            an = [q for q in qs if isanc(q)]
            if an and P["p_tr"] > 0:
                c.append("DEPOLARIZE1", an, s * P["p_tr"])
        if L["CX"]:
            prs = sorted(L["CX"])
            tg = [b for a, b in prs]
            if P["p_1q"] > 0:
                c.append("DEPOLARIZE1", tg, s * P["p_1q"])
            c.append("CX", [a for pr in prs for a in pr])
            c.append("DEPOLARIZE2", [a for pr in prs for a in pr], s * P["p_cz"])
            if P["p_1q"] > 0:
                c.append("DEPOLARIZE1", tg, s * P["p_1q"])
        for g, fl in (("M", "X_ERROR"), ("MX", "Z_ERROR")):
            qs = sorted(L[g])
            if qs:
                if P["p_tr"] > 0:
                    c.append("DEPOLARIZE1", qs, s * P["p_tr"])
                c.append(fl, qs, s * P["p_meas"])
                c.append(g, qs)
                for q in qs:
                    rec[q] = rec.get(q, []) + [nm]; nm += 1
    c.append("TICK")
    g = "M" if basis == "Z" else "MX"
    c.append("X_ERROR" if basis == "Z" else "Z_ERROR", list(range(N)), s * P["p_meas"])
    c.append(g, list(range(N)))
    data = {q: nm + q for q in range(N)}
    nm += N
    q0 = lib.QZ0 if basis == "Z" else lib.QX0
    tgt = lambda a: stim.target_rec(a - nm)
    for j in range(R):
        for i in range(lib.N2):
            r = rec[q0 + i]
            c.append("DETECTOR", [tgt(r[j])] + ([tgt(r[j - 1])] if j else []), [i, j])
    for i in range(lib.N2):
        c.append("DETECTOR", [tgt(data[x]) for x in np.flatnonzero(H[i])] + [tgt(rec[q0 + i][R - 1])], [i, R])
    for k in range(Lg.shape[0]):
        c.append("OBSERVABLE_INCLUDE", [tgt(data[x]) for x in np.flatnonzero(Lg[k])], k)
    return c, dict(stats, time_move=sum(a for a, _ in tl), time_wait=sum(b for _, b in tl),
                   moves=sum(len(m["groups"]) for m in meta), readouts=sum(m["anc_meas"] for m in meta),
                   pulses_par=sum(1 for m in meta if m["groups"]), layers=layers, meta=meta)
