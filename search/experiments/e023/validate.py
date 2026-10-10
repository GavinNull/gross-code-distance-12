"""E-023 method validation.  experimenter.

  (a) sector sampler == stim: per-detector firing rates and observable flip rates of Bernoulli(q_i(p)) sector sampling
      vs stim's compiled detector sampler of the full noisy circuit (projected to the sector), 200k shots each.
  (b) fixed-weight reconstruction vs direct sampling: per sector and decoder, LER_direct(p) (fixedweight --direct)
      vs Σ_w π_w(p) f_w (analyze.sector_curve) at the same p.

    PYTHONPATH=. uv run python -m search.experiments.e023.validate --prob m54_paper,m54_repo --model sd6 --p 0.003
"""
from __future__ import annotations

import argparse
import glob
import json

import numpy as np

from search.experiments.e023.analyze import PGRID, sector_curve
from search.experiments.e023.common import OUT, P_DEC, noisy_circuits, sectors


def sampler_check(prob, model, p, shots=200000, seed=23500):
    out = {}
    rng = np.random.default_rng(seed)
    for (label, c, dr, orr), sec in zip(noisy_circuits(prob, model, p), sectors(prob, model, p)):
        d0, d1 = dr if dr else (0, c.num_detectors)
        o0, o1 = orr if orr else (0, c.num_observables)
        det, obs = c.compile_detector_sampler(seed=seed).sample(shots, separate_observables=True)
        det, obs = det[:, d0:d1], obs[:, o0:o1]
        Hc = sec.H.tocsc().astype(np.int32)
        L = sec.L.tocsc().astype(np.int32)
        ds = np.zeros(sec.ndet)
        os_ = np.zeros(sec.nobs)
        anyo = 0
        for b in range(0, shots, 20000):
            B = (rng.random((20000, sec.ncol)) < sec.q[None, :]).astype(np.int32)
            dd = (B @ Hc.T) % 2
            oo = (B @ L.T) % 2
            ds += np.asarray(dd).sum(0)
            os_ += np.asarray(oo).sum(0)
            anyo += int((np.asarray(oo).sum(1) > 0).sum())
        a, b = det.mean(0), ds / shots
        z = np.abs(a - b) / np.sqrt(np.maximum(a * (1 - a) / shots * 2, 1e-12))
        out[label] = dict(max_abs_z_det=float(z.max()), mean_det_stim=float(a.mean()), mean_det_sector=float(b.mean()),
                          obs_any_stim=float((obs.sum(1) > 0).mean()), obs_any_sector=anyo / shots)
    return out


def direct_rates(prob, model, p, dec, label):
    k = n = 0
    for f in glob.glob(str(OUT / "direct" / f"{prob}_{model}_p{p:.2e}_b*.npz")):
        z = np.load(f)
        k += int(z[f"{label}_{dec}_f"].sum())
        n += len(z[f"{label}_{dec}_f"])
    return k, n


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--prob", required=True)
    ap.add_argument("--model", default="sd6")
    ap.add_argument("--p", type=float, default=0.003)
    ap.add_argument("--decoders", default="bposd,relay")
    ap.add_argument("--sampler", action="store_true")
    a = ap.parse_args(argv)
    res = {}
    rng = np.random.default_rng(23501)
    ip = int(np.argmin(np.abs(PGRID - a.p)))
    assert abs(PGRID[ip] - a.p) < 1e-12
    for prob in a.prob.split(","):
        if a.sampler:
            res[f"{prob}|sampler"] = sampler_check(prob, a.model, a.p)
            print(prob, res[f"{prob}|sampler"], flush=True)
        for si, sec in enumerate(sectors(prob, a.model, P_DEC)):
            for dec in a.decoders.split(","):
                k, n = direct_rates(prob, a.model, a.p, dec, sec.label)
                if n == 0:
                    continue
                c = sector_curve(prob, a.model, si, dec, rng, nboot=300)
                from scipy.stats import beta
                lo, hi = beta.ppf([0.025, 0.975], k + 0.5, n - k + 0.5)
                row = dict(direct_k=k, direct_n=n, direct=k / n, direct_95=[float(lo), float(hi)],
                           recon=float(c["central"][ip]), recon_95=[float(c["lo95"][ip]), float(c["hi95"][ip])])
                res[f"{prob}|{sec.label}|{dec}"] = row
                print(prob, a.model, sec.label, dec, json.dumps(row), flush=True)
    (OUT / f"validate_{a.model}_p{a.p:.0e}.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
