"""E-045 audit, Part A: Crocker's Tesseract CZ-compiled gross files.  auditor (no import of search/experiments/e045).

Reads results/E-045-crocker/data/bb144_{Z,X}.stim (copies of the zip's circuit text) and, as TEXT only, the zip's
SHA256SUMS.txt, data/dem_fingerprints.txt and witnesses/bb144_*_w10_p1.txt.  Nothing from the zip is run or imported.

  summary   sha256 vs zip SHA256SUMS; stim DEM written as text and fingerprinted by my own parser (dem_canon logic:
            sorted SET of "E dets | obs" + sorted "D k coords" with %g); projection onto memory-basis detectors
            (type A = coordinate parity of round-0 detectors); hypothesis H; projected column list saved.
  witness   (i) E-045's witness: its 10 full mechanisms must be mechanisms of MY full DEM, XOR to zero on all 1728
            detectors, flip a nonzero observable set; (ii) Crocker's own witness file, same test; (iii) injection of
            one representative circuit fault per mechanism (stim explain_detector_error_model_errors) into the
            noiseless circuit, simulated with stim's TableauSimulator-free frame sampler at p = 1.

  uv run python -m search.experiments.e045_audit.tess_audit summary
  uv run python -m search.experiments.e045_audit.tess_audit witness
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import stim

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "results/E-045-crocker/data"
ZIP = Path("/private/tmp/claude-501/-Users-ephemeral/51035684-bfaf-4743-b8e1-678c08dbe16b/scratchpad/crocker_zip/release_circ_gross")
OUT = ROOT / "results/E-045-audit"


def zip_sha(name):
    for line in (ZIP / "SHA256SUMS.txt").read_text().splitlines():
        h, f = line.split(None, 1)
        if f.strip() == name:
            return h
    return None


def zip_fp(basis):
    for line in (ZIP / "data/dem_fingerprints.txt").read_text().splitlines():
        p = line.split()
        if p[-1] == f"tesseract/bb144_{basis}.dem":
            return p[0], int(p[1].split("=")[1]), int(p[2].split("=")[1])


def load(basis):
    p = DATA / f"bb144_{basis}.stim"
    return stim.Circuit.from_file(str(p)), hashlib.sha256(p.read_bytes()).hexdigest()


def dem_text(c):
    return str(c.detector_error_model(decompose_errors=False).flattened())


def parse(text):
    errs, dets, ninst = [], {}, 0
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("error("):
            ninst += 1
            toks = line.split(")", 1)[1].split()
            assert not any(t.startswith("^") for t in toks)
            d, o = set(), set()
            for t in toks:
                (d if t[0] == "D" else o).symmetric_difference_update({int(t[1:])})
            errs.append((tuple(sorted(d)), tuple(sorted(o))))
        elif line.startswith("detector("):
            a, rest = line[len("detector("):].split(")", 1)
            dets[int(rest.split()[0][1:])] = tuple(float(x) for x in a.split(","))
    return errs, dets, ninst


def fingerprint(errs, dets):
    h = hashlib.sha256()
    for d, o in sorted(set(errs)):
        h.update(("E %s | %s\n" % (" ".join(map(str, d)), " ".join(map(str, o)))).encode())
    for k in sorted(dets):
        h.update(("D %d %s\n" % (k, " ".join("%g" % x for x in dets[k]))).encode())
    return h.hexdigest()


def project(errs, dets):
    nd = len(dets)
    r0 = [k for k in dets if dets[k][2] == 0]
    pars = {(int(dets[k][0]) % 2, int(dets[k][1]) % 2) for k in r0}
    assert len(pars) == 1
    p0 = pars.pop()
    isA = {k: (int(dets[k][0]) % 2, int(dets[k][1]) % 2) == p0 for k in dets}
    full = set(errs)
    viol, okH, pureB, restricted, proj = 0, 0, 0, set(), set()
    nodet_obs = sum(1 for d, o in full if not d and o)
    for d, o in full:
        a = tuple(x for x in d if isA[x])
        b = [x for x in d if not isA[x]]
        if not a and not o:
            pureB += 1
            continue
        proj.add((a, o))
        if b:
            okH += (a, o) in full
            viol += (a, o) not in full
        else:
            restricted.add((a, o))
    A = sorted(k for k in dets if isA[k])
    return dict(isA=isA, A=A, proj=proj, restricted=restricted,
                H=dict(violations=viol, ok=okH, pureB=pureB, nodet_obs=nodet_obs, projA_empty_obs=sum(1 for a, o in proj if not a),
                       restricted_eq_projected=(restricted == proj), ncols=len(proj), nA=len(A), nB=nd - len(A)))


def summary():
    OUT.mkdir(parents=True, exist_ok=True)
    res = {}
    for b in ("Z", "X"):
        c, sha = load(b)
        txt = dem_text(c)
        errs, dets, ninst = parse(txt)
        fp = fingerprint(errs, dets)
        zfp = zip_fp(b)
        P = project(errs, dets)
        res[b] = dict(sha256=sha, zip_sha256=zip_sha(f"circuits/tesseract/bb144_{b}.stim"),
                      fingerprint=fp, zip_fingerprint=zfp, fp_match=(fp, len(set(errs)), len(dets)) == zfp,
                      error_lines=ninst, distinct=len(set(errs)), detectors=len(dets), nobs=c.num_observables,
                      ticks=c.num_ticks, gates=sorted({i.name for i in c.flattened()}), **P["H"])
        print(b, json.dumps(res[b]), flush=True)
        # save projected columns with (x, y, t) coords of A detectors for the isomorphism check
        Ai = {k: i for i, k in enumerate(P["A"])}
        cols = sorted((tuple(Ai[x] for x in a), o) for a, o in P["proj"])
        (OUT / f"tess_proj_{b}.json").write_text(json.dumps(dict(cols=cols, coords=[dets[k] for k in P["A"]],
                                                                  nobs=c.num_observables)))
    (OUT / "tess_summary.json").write_text(json.dumps(res, indent=1))


def check_set(full, mechs, nd):
    acc_d, acc_o = set(), set()
    for d, o in mechs:
        assert (tuple(d), tuple(o)) in full, ("not a mechanism", d, o)
        acc_d ^= set(d); acc_o ^= set(o)
    return len(acc_d), sorted(acc_o)


def simulate(c, mechs):
    """build noiseless flattened circuit with injected Paulis right after the noise instruction they came from."""
    flat = c.flattened()
    ex = flat.explain_detector_error_model_errors(dem_filter=_flt(mechs), reduce_to_one_representative_error=True)
    assert len(ex) == len(mechs)
    after = {}
    mflip = set()
    for e in ex:
        loc = e.circuit_error_locations[0]
        assert len(loc.stack_frames) == 1, "flattened circuit expected"
        off = loc.stack_frames[0].instruction_offset
        if loc.flipped_measurement is not None:
            mflip.add(loc.flipped_measurement.measurement_record_index)
            assert not loc.flipped_pauli_product
        else:
            after.setdefault(off, []).append([(t.gate_target.pauli_type, t.gate_target.value) for t in loc.flipped_pauli_product])
    out = stim.Circuit()
    nm = 0
    noise = {"DEPOLARIZE1", "DEPOLARIZE2", "X_ERROR", "Y_ERROR", "Z_ERROR", "PAULI_CHANNEL_1", "PAULI_CHANNEL_2"}
    for i, inst in enumerate(flat):
        if inst.name in noise:
            pass
        elif stim.gate_data(inst.name).produces_measurements:
            k = len(inst.targets_copy())
            for j, t in enumerate(inst.targets_copy()):
                if nm + j in mflip:
                    # flip the outcome: Pauli before the measurement that anticommutes with its basis
                    q = t.value
                    out.append({"M": "X_ERROR", "MX": "Z_ERROR", "MY": "X_ERROR", "MR": "X_ERROR", "MRX": "Z_ERROR"}[inst.name], [q], 1.0)
                out.append(inst.name, [t])
            nm += k
        else:
            out.append(inst)
        for ps in after.get(i, []):
            # apply the Pauli product as single-qubit gates (a Pauli product is a product of single-qubit Paulis)
            # as p = 1 noise channels (a deterministic Pauli gate would be absorbed into stim's reference sample)
            for p, q in ps:
                out.append(p + "_ERROR", [q], 1.0)
    s = out.compile_detector_sampler()
    d, o = s.sample(1, separate_observables=True)
    return int(d.sum()), np.flatnonzero(o[0]).tolist(), out


def _flt(mechs):
    f = stim.DetectorErrorModel()
    for d, o in mechs:
        f.append("error", 0.1, [stim.target_relative_detector_id(x) for x in d] + [stim.target_logical_observable_id(x) for x in o])
    return f


def crocker_witness(basis):
    p = ZIP / f"witnesses/bb144_{basis}_w10_p1.txt"
    mechs = []
    for line in p.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        a, h = line.split("|")
        d = tuple(sorted(int(t[1:]) for t in a.split()))
        hv = int(h.strip(), 16)
        o = tuple(i for i in range(12) if hv >> i & 1)
        mechs.append((d, o))
    return mechs


def witness():
    OUT.mkdir(parents=True, exist_ok=True)
    W = {json.loads(l)["basis"]: json.loads(l) for l in (ROOT / "results/E-045-crocker/witness/witness.jsonl").read_text().splitlines() if l.strip()}
    res = []
    for b in ("Z", "X"):
        c, _ = load(b)
        errs, dets, _ = parse(dem_text(c))
        full = set(errs)
        cand = {"E045": [tuple(map(tuple, m)) for m in W[b]["full_mechanisms"]]}
        try:
            cand["crocker"] = crocker_witness(b)
        except FileNotFoundError:
            pass
        for name, mechs in cand.items():
            r = dict(basis=b, source=name, weight=len(mechs), distinct=len(set(mechs)))
            try:
                nd, obs = check_set(full, mechs, len(dets))
                r.update(dem_detectors_left=nd, dem_obs=obs)
                fired, flipped, _ = simulate(c, mechs)
                r.update(sim_fired=fired, sim_obs=flipped)
                drops = []
                for k in range(len(mechs)):
                    f2, o2, _ = simulate(c, mechs[:k] + mechs[k + 1:])
                    drops.append(f2)
                r["drop_one_min_fired"] = min(drops)
                r["ok"] = nd == 0 and bool(obs) and fired == 0 and flipped == obs and min(drops) > 0
            except AssertionError as e:
                r["error"] = str(e)
                r["ok"] = False
            print(json.dumps(r), flush=True)
            res.append(r)
    (OUT / "tess_witness.jsonl").write_text("".join(json.dumps(r) + "\n" for r in res))


if __name__ == "__main__":
    {"summary": summary, "witness": witness}[sys.argv[1]]()
