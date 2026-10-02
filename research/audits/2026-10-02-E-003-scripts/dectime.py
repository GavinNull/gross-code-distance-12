"""Decoder timing on 40 shots per circuit (Z basis, p=0.005), several decoder settings."""
import time
import numpy as np
from ldpc import BpOsdDecoder, BpLsdDecoder
from common import code_and_scheds, memory, dem_matrices

DECS = {
    "A_ibm_default": ("osd", dict(max_iter=10000, bp_method="minimum_sum", ms_scaling_factor=0, osd_method="osd_cs", osd_order=7)),
    "B_iter100": ("osd", dict(max_iter=100, bp_method="minimum_sum", ms_scaling_factor=0, osd_method="osd_cs", osd_order=7)),
    "C_ms0.625_osd10": ("osd", dict(max_iter=100, bp_method="minimum_sum", ms_scaling_factor=0.625, osd_method="osd_cs", osd_order=10)),
    "D_lsd7": ("lsd", dict(max_iter=100, bp_method="minimum_sum", ms_scaling_factor=0, lsd_method="lsd_cs", lsd_order=7)),
    "E_ps_iter1000_osd4": ("osd", dict(max_iter=1000, bp_method="product_sum", osd_method="osd_cs", osd_order=4)),
}
code, S = code_and_scheds()
for name, sched in S.items():
    c = memory(code, sched, name, 12, "Z", 0.005)
    H, L, pri = dem_matrices(c)
    dets, obs = c.compile_detector_sampler(seed=7).sample(40, separate_observables=True)
    for dn, (kind, kw) in DECS.items():
        cls = BpOsdDecoder if kind == "osd" else BpLsdDecoder
        dec = cls(H.tocsc(), error_channel=list(pri), **kw)
        t0 = time.process_time(); fails = 0; nconv = 0
        for s in range(len(dets)):
            e = dec.decode(dets[s].astype(np.uint8))
            nconv += bool(dec.converge)
            fails += bool(((L @ e) % 2 != obs[s]).any())
        print(name, dn, f"{(time.process_time()-t0)/len(dets):.3f} s/shot", "fails", fails, "bp_conv", nconv, flush=True)
