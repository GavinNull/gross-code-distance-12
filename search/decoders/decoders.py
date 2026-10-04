"""E-006 decoder set for one sector. All decoders map syndrome -> error vector on the sector columns
(pymatching: -> observable prediction only).

  bposd   : E-002 / IBM setting (min-sum, adaptive scaling ms=0, max_iter 1e4, parallel, OSD-CS order 7)
            -- identical to evaluators.l2._SectorDecoder (same matrix, same column order, same params)
  lsd     : same BP, LSD-CS order 7 post-processing (ldpc BpLsdDecoder)
  serial  : bposd with serial BP schedule
  relay5  : IBM Relay-BP (relay_bp 0.2.2, arXiv:2506.01779), F64, README sinter-example parameters
            (gamma0=0.1, pre_iter=80, set_max_iter=60, gamma_dist_interval=(-0.24, 0.66)) with num_sets=300 and
            stop_nconv=5 ("Relay-BP-5"); fixed seed.  Output that does not satisfy the syndrome = failure.
  relay1  : the README sinter example exactly (num_sets=60, stop_nconv=1)
  ref     : exact most-likely-error decoder (HiGHS MILP, search/decoders/exact.py)
"""
from __future__ import annotations

import numpy as np

from search.decoders.common import IBM_BPOSD
from search.decoders.exact import MilpMLE


RELAY = {
    "relay5": dict(gamma0=0.1, pre_iter=80, num_sets=300, set_max_iter=60, gamma_dist_interval=(-0.24, 0.66),
                   stop_nconv=5),
    "relay1": dict(gamma0=0.1, pre_iter=80, num_sets=60, set_max_iter=60, gamma_dist_interval=(-0.24, 0.66),
                   stop_nconv=1),
}


class RelayWrap:
    """ldpc-like interface: decode(syndrome) -> error vector; .converge."""
    def __init__(self, sec, params, seed=20261003):
        import relay_bp
        self.d = relay_bp.RelayDecoderF64(sec.H, error_priors=np.asarray(sec.priors, dtype=np.float64), seed=seed,
                                          **params)
        self.converge = True

    def decode(self, syn):
        r = self.d.decode_detailed(np.asarray(syn, dtype=np.uint8))
        self.converge = bool(r.success)
        return np.asarray(r.decoding, dtype=np.uint8)


def make(sec, names=("bposd", "lsd", "relay5")):
    from ldpc import BpLsdDecoder, BpOsdDecoder
    out = {}
    pr = list(sec.priors)
    for n in names:
        if n == "bposd":
            out[n] = BpOsdDecoder(sec.H, error_channel=pr, **IBM_BPOSD)
        elif n == "serial":
            out[n] = BpOsdDecoder(sec.H, error_channel=pr, **dict(IBM_BPOSD, schedule="serial"))
        elif n == "lsd":
            out[n] = BpLsdDecoder(sec.H, error_channel=pr, max_iter=10000, bp_method="minimum_sum",
                                  ms_scaling_factor=0, schedule="parallel", lsd_method="lsd_cs", lsd_order=7)
        elif n in RELAY:
            out[n] = RelayWrap(sec, RELAY[n])
        else:
            raise ValueError(n)
    return out


def make_ref(sec):
    return MilpMLE(sec.H, sec.weights)


def pymatching_sector_decoders(model):
    """pymatching per sector exactly as evaluators.l2 (graphlike decomposition of the sector circuit)."""
    from evaluators.l2 import DecoderConfig, _BatchRunner
    br = _BatchRunner(model.circuit, model.nz, model.oz, DecoderConfig("pymatching"))
    return br.decoders
